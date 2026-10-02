import { useEffect, useRef, useState } from "react";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { ImportPreview, ImportPromotion, ImportRequest, PartialProfileTemplate, ProfileListing } from "../../api/types";
import { ProfileEditor } from "./ProfileEditor";

const MAX_BYTES = 2 * 1024 * 1024;
const HASH = /^[0-9a-f]{64}$/;
const button = "btn btn-secondary disabled:cursor-not-allowed disabled:opacity-50";

type Draft = {
  format: "" | "csv" | "json";
  profileKey: string;
  sourceId: string;
  kind: "historical" | "artificial";
  revision: string;
  provenance: string;
  clockMode: "" | "naive_legacy" | "iana";
  zone: string;
  date: string;
  time: string;
  positions: string[];
};
const initial: Draft = {
  format: "", profileKey: "", sourceId: "", kind: "historical", revision: "",
  provenance: "", clockMode: "", zone: "", date: "date", time: "time", positions: [],
};

/** Latin-1 is used only as a byte carrier; decoding the file as text would corrupt its identity. */
function readBytes(file: File): Promise<Uint8Array> {
  // FileReader also works on browsers that do not expose Blob.arrayBuffer.
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(file);
  });
}

function encodeBytes(bytes: Uint8Array): string {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  }
  return btoa(binary);
}

function failureMessage(error: unknown, action: string): string {
  if (error instanceof NetworkError) return "No se pudo contactar al servidor local. La solicitud podría haber llegado; comprobá el estado antes de volver a intentarlo.";
  if (error instanceof ApiError && error.status === 409) return "Conflicto: cambiaron los datos o no hay capacidad de cuota. Volvé a revisar el archivo y generá una vista previa nueva antes de intentar guardar.";
  if (error instanceof ApiError && error.status === 413) return "El archivo supera el límite de 2 MiB. Elegí uno más pequeño.";
  if (error instanceof ApiError && error.status === 422) return "El servidor rechazó la solicitud. Revisá el archivo, los campos y la vista previa.";
  return `No se pudo ${action}. Revisá la conexión y los datos antes de intentar de nuevo.`;
}

export function DataPage() {
  const [profiles, setProfiles] = useState<ProfileListing[]>([]);
  const [templates, setTemplates] = useState<PartialProfileTemplate[]>([]);
  const [registering, setRegistering] = useState(false);
  const [profileTotal, setProfileTotal] = useState(0);
  const [profilesLoading, setProfilesLoading] = useState(true);
  const [profilesError, setProfilesError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [draft, setDraft] = useState<Draft>(initial);
  const [preview, setPreview] = useState<{ body: ImportRequest; result: ImportPreview; generation: number } | null>(null);
  const [saved, setSaved] = useState<ImportPromotion | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"preview" | "promote" | null>(null);
  const generation = useRef(0);
  // Preview requests are replaceable; promotion is a mutation whose outcome cannot be cancelled safely.
  const activePreview = useRef<number | null>(null);
  const promotionInFlight = useRef(false);
  const errorRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    let live = true;
    apiClient.getProfiles(0, 100).then((catalog) => {
      if (!live) return;
      setProfiles(catalog.items);
      setTemplates(catalog.templates);
      setProfileTotal(catalog.total);
      setProfilesLoading(false);
    }).catch((cause: unknown) => {
      if (!live) return;
      setProfilesError(failureMessage(cause, "cargar los perfiles"));
      setProfilesLoading(false);
    });
    return () => { live = false; generation.current++; };
  }, []);

  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);

  function invalidate() {
    if (promotionInFlight.current) return;
    generation.current++;
    setPreview(null);
    setSaved(null);
    setError("");
    setBusy(null);
  }
  function change(next: Partial<Draft>) {
    if (promotionInFlight.current) return;
    invalidate();
    setDraft((current) => ({ ...current, ...next }));
  }
  function chooseProfile(key: string) {
    const selected = profiles.find((item) => `${item.profile.profile_id}@${item.profile.revision}` === key);
    change({ profileKey: key, positions: selected
      ? Array.from({ length: selected.profile.positions }, (_, index) => `pos${index + 1}`) : [] });
  }

  async function showPreview(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (promotionInFlight.current || registering || activePreview.current === generation.current) return;
    invalidate();
    if (!file) { setError("Elegí un archivo CSV o JSON."); return; }
    if (!draft.format || !draft.clockMode) { setError("Elegí explícitamente el formato del archivo y la interpretación de su hora."); return; }
    if (file.size > MAX_BYTES) { setError("El archivo supera 2 MiB. Elegí uno más pequeño."); return; }
    const selected = profiles.find((item) => `${item.profile.profile_id}@${item.profile.revision}` === draft.profileKey);
    if (!selected) { setError("Elegí un perfil guardado completo; las plantillas parciales no se pueden importar."); return; }
    const names = [draft.date, draft.time, ...draft.positions];
    if (selected.profile.positions > 30 || names.length !== selected.profile.positions + 2 ||
      names.some((name) => !name || name.trim() !== name) || new Set(names).size !== names.length) {
      setError("Indicá nombres de columnas distintos y sin espacios alrededor para fecha, hora y cada posición (máximo 30 posiciones)."); return;
    }
    if ([draft.sourceId, draft.revision, draft.provenance].some((value) => !value || value.trim() !== value || value.length > 256) ||
      (draft.clockMode === "iana" && !draft.zone.trim())) {
      setError("Completá fuente, revisión, procedencia y, si corresponde, zona IANA; sin espacios alrededor (máximo 256 caracteres por dato de fuente)."); return;
    }
    setBusy("preview");
    const ticket = generation.current;
    activePreview.current = ticket;
    try {
      const bytes = await readBytes(file);
      if (ticket !== generation.current) return;
      if (bytes.length > MAX_BYTES) { setError("El archivo supera 2 MiB. Elegí uno más pequeño."); return; }
      const body: ImportRequest = {
        raw_base64: encodeBytes(bytes), format: draft.format,
        mapping: { date: draft.date, time: draft.time, positions: [...draft.positions] },
        source: { source_id: draft.sourceId, kind: draft.kind, revision: draft.revision, provenance: draft.provenance },
        clock: { mode: draft.clockMode, zone: draft.clockMode === "iana" ? draft.zone.trim() : null },
        profile: selected.profile,
      };
      const result = await apiClient.previewImport(body);
      if (ticket === generation.current) setPreview({ body, result, generation: ticket });
    } catch (cause) {
      if (ticket === generation.current) setError(failureMessage(cause, "obtener la vista previa"));
    } finally {
      if (activePreview.current === ticket) activePreview.current = null;
      if (ticket === generation.current) setBusy(null);
    }
  }

  async function promote() {
    if (promotionInFlight.current || registering || !preview || preview.generation !== generation.current ||
      !preview.result.promotable || !preview.result.dataset_sha256 || !HASH.test(preview.result.dataset_sha256)) return;
    promotionInFlight.current = true;
    setBusy("promote");
    setError("");
    const ticket = generation.current;
    try {
      const result = await apiClient.promoteImport({ ...preview.body, expected_dataset_sha256: preview.result.dataset_sha256 });
      if (ticket === generation.current) {
        setSaved(result);
        setPreview(null);
      }
    } catch (cause) {
      if (ticket === generation.current) {
        setError(failureMessage(cause, "guardar el archivo"));
        // A conflict or uncertain network result must never reuse an old preview.
        setPreview(null);
      }
    } finally {
      promotionInFlight.current = false;
      if (ticket === generation.current) setBusy(null);
    }
  }

  return <div className="max-w-4xl space-y-8">
    <p className="max-w-prose text-text-secondary">Importá sorteos locales y revisá los resultados antes de guardarlos. Los datos importados son artefactos inertes: todavía no se pueden usar para ejecutar experimentos. No existe una lista de datasets guardados en esta versión.</p>
    {profilesLoading && <p role="status">Cargando perfiles guardados…</p>}
    {profilesError && <p role="alert">{profilesError}</p>}
    {!profilesLoading && !profilesError && profiles.length === 0 && <p role="status">No hay perfiles guardados para importar.</p>}
    {profileTotal > 100 && <p role="status">Se muestran los primeros 100 perfiles guardados y los creados ahora. Otros perfiles no se pueden elegir desde esta pantalla.</p>}
    <ProfileEditor templates={templates} profiles={profiles} disabled={profilesLoading || !!profilesError || busy === "promote"}
      onBusyChange={setRegistering} onRegistered={(item) => {
        const key = `${item.profile.profile_id}@${item.profile.revision}`;
        setProfiles((current) => [item, ...current.filter(({ profile }) => `${profile.profile_id}@${profile.revision}` !== key)]);
        setProfileTotal((total) => total + 1);
        invalidate();
        setDraft((current) => ({ ...current, profileKey: key,
          positions: Array.from({ length: item.profile.positions }, (_, index) => `pos${index + 1}`) }));
      }} />
    <form onSubmit={(event) => { void showPreview(event); }}>
      <fieldset disabled={busy === "promote" || registering} className="min-w-0 space-y-7">
      <legend className="sr-only">Configuración de importación</legend>
      <section aria-labelledby="file-heading" className="border-t border-border pt-5 space-y-4">
        <h2 id="file-heading" className="section-header">Archivo y perfil</h2>
        <div className="field"><label htmlFor="import-file" className="field-label">Archivo local CSV o JSON (máximo 2 MiB)</label>
          <input id="import-file" type="file" accept=".csv,.json,text/csv,application/json" className="control h-auto py-2" onChange={(event) => { if (promotionInFlight.current) return; invalidate(); setFile(event.target.files?.[0] ?? null); }} />
          {file && <p className="field-help">Seleccionado: {file.name} · {file.size} bytes</p>}</div>
        <div className="field"><label htmlFor="import-format" className="field-label">Formato del archivo (selección explícita)</label>
          <select id="import-format" className="control" value={draft.format} onChange={(event) => change({ format: event.target.value as Draft["format"] })}><option value="">Elegí un formato</option><option value="csv">CSV</option><option value="json">JSON (lista plana de objetos)</option></select></div>
        <div className="field"><label htmlFor="import-profile" className="field-label">Perfil guardado completo</label>
          <select id="import-profile" className="control" value={draft.profileKey} onChange={(event) => chooseProfile(event.target.value)}><option value="">Elegí un perfil</option>{profiles.map(({ profile, execution_supported }) => <option key={`${profile.profile_id}@${profile.revision}`} value={`${profile.profile_id}@${profile.revision}`}>{profile.profile_id} · revisión {profile.revision}{execution_supported ? " · ejecutable en el motor heredado" : " · perfil registrado"}</option>)}</select>
          <p className="field-help">Las plantillas de catálogo son parciales y no son perfiles guardados. Elegir un perfil no habilita la ejecución de datos importados.</p></div>
      </section>
      <section aria-labelledby="source-heading" className="border-t border-border pt-5 space-y-4">
        <h2 id="source-heading" className="section-header">Fuente y reloj</h2>
        {([ ["sourceId", "Identificador de fuente"], ["revision", "Revisión o corrección"], ["provenance", "Procedencia de los datos"] ] as const).map(([key, label]) => <div className="field" key={key}><label htmlFor={key} className="field-label">{label}</label><input id={key} className="control" maxLength={256} value={draft[key]} onChange={(event) => change({ [key]: event.target.value })} /></div>)}
        <div className="field"><label htmlFor="source-kind" className="field-label">Tipo de fuente</label><select id="source-kind" className="control" value={draft.kind} onChange={(event) => change({ kind: event.target.value as Draft["kind"] })}><option value="historical">Histórica</option><option value="artificial">Artificial</option></select></div>
        <div className="field"><label htmlFor="clock-mode" className="field-label">Interpretación de la hora</label><select id="clock-mode" className="control" value={draft.clockMode} onChange={(event) => change({ clockMode: event.target.value as Draft["clockMode"], zone: "" })}><option value="">Elegí una interpretación</option><option value="naive_legacy">Hora local heredada, sin zona declarada</option><option value="iana">Zona IANA explícita</option></select><p className="field-help">La hora se conserva tal como aparece en el archivo: no se convierte a otra zona.</p></div>
        {draft.clockMode === "iana" && <div className="field"><label htmlFor="clock-zone" className="field-label">Zona IANA (por ejemplo, America/Santo_Domingo)</label><input id="clock-zone" className="control" value={draft.zone} onChange={(event) => change({ zone: event.target.value })} /></div>}
      </section>
      <section aria-labelledby="mapping-heading" className="border-t border-border pt-5 space-y-4">
        <h2 id="mapping-heading" className="section-header">Columnas del archivo</h2>
        <p className="field-help">Nombres sugeridos: date, time y pos1…posN. Cambialos para que coincidan exactamente con tu archivo; posiciones en orden de premio. Fecha YYYY-MM-DD, hora HH:MM. Máximo 10.000 filas y 32 columnas.</p>
        <div className="grid gap-4 sm:grid-cols-2">{([ ["date", "Columna de fecha"], ["time", "Columna de hora"] ] as const).map(([key, label]) => <div key={key}><label htmlFor={`map-${key}`} className="field-label">{label}</label><input id={`map-${key}`} className="control" value={draft[key]} onChange={(event) => change({ [key]: event.target.value })} /></div>)}</div>
        <div className="grid gap-4 sm:grid-cols-2">{draft.positions.map((value, index) => <div key={index}><label htmlFor={`map-position-${index}`} className="field-label">Columna de posición {index + 1}</label><input id={`map-position-${index}`} className="control" value={value} onChange={(event) => change({ positions: draft.positions.map((item, at) => at === index ? event.target.value : item) })} /></div>)}</div>
      </section>
      <button type="submit" className="btn btn-primary disabled:opacity-50" disabled={busy !== null || registering || profilesLoading || !!profilesError}>Generar vista previa</button>
      </fieldset>
    </form>
    {busy === "preview" && <p role="status">Validando archivo…</p>}
    {error && <p ref={errorRef} tabIndex={-1} role="alert" className="border-y border-border py-3 text-text">{error}</p>}
    {preview && <section aria-labelledby="preview-heading" className="border-t border-border pt-5 space-y-4">
      <h2 id="preview-heading" className="section-header">Vista previa · {preview.result.promotable ? "válida" : "no válida"}</h2>
      <p>Filas leídas: {preview.result.rows_seen} · Registros: {preview.result.records_total} · Duplicados idénticos unidos: {preview.result.duplicates_merged} · Errores: {preview.result.error_count}{preview.result.errors_truncated ? " (lista truncada)" : ""}</p>
      {preview.result.errors.length > 0 && <ul aria-label="Errores de importación" className="list-disc space-y-1 pl-5">{preview.result.errors.map((issue, index) => <li key={index}> {issue.row === null ? "Archivo" : `Fila ${issue.row}`} · {issue.code}: {issue.message}</li>)}</ul>}
      {preview.result.sample.length > 0 && <div><h3 className="field-label">Muestra (hasta 20 registros)</h3><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th scope="col" className="p-2">Fecha</th><th scope="col" className="p-2">Hora</th><th scope="col" className="p-2">Posiciones en orden</th></tr></thead><tbody>{preview.result.sample.map((record, index) => <tr key={index} className="border-t border-border"><td className="p-2">{record.date}</td><td className="p-2">{record.time}</td><td className="p-2">{record.numbers.join(", ")}</td></tr>)}</tbody></table></div></div>}
      {preview.result.dataset_sha256 && <p className="break-all text-sm">Hash de dataset previsto: <code>{preview.result.dataset_sha256}</code></p>}
      <p className="field-help">Guardar conserva este archivo y contexto como un artefacto inerte. No lo agrega a experimentos ni a un catálogo navegable.</p>
      <button type="button" className={button} disabled={busy !== null || registering || !preview.result.promotable || !preview.result.dataset_sha256 || !HASH.test(preview.result.dataset_sha256)} onClick={() => { void promote(); }}>Confirmar y guardar importación</button>
    </section>}
    {busy === "promote" && <p role="status">Solicitud de guardado enviada; respuesta pendiente. Todavía no se confirmó si se guardó. No cambies el contexto ni vuelvas a enviarla hasta recibir una respuesta.</p>}
    {saved && <section aria-labelledby="saved-heading" role="status" className="border-t border-border pt-5 space-y-2"><h2 id="saved-heading" className="section-header">{saved.created ? "Importación guardada" : "Dataset ya guardado"}</h2><p className="break-all">Hash guardado: <code>{saved.dataset_sha256}</code></p><p>{saved.duplicate_source_differs ? "Ya existía el mismo dataset con bytes de origen diferentes. Se conserva la primera fuente guardada." : saved.created ? "Se guardó una versión inmutable." : "Ya existía este dataset; no se creó una copia nueva."}</p><p className="field-help">Este artefacto no se puede ejecutar todavía. Esta confirmación no es una lista persistente de datasets.</p></section>}
  </div>;
}
