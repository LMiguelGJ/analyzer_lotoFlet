import { useEffect, useRef, useState } from "react";
import type { ReactNode, RefObject } from "react";
import { Link } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { DatasetListing, HistoryImportPreview, ImportPreview, ImportPromotion, ImportRequest, Page, PartialProfileTemplate, ProfileListing } from "../../api/types";
import { ProfileEditor } from "./ProfileEditor";
import { Block, Loading } from "../../components/ui";

const MAX_BYTES = 2 * 1024 * 1024;
const MAX_HISTORY_BYTES = 32 * 1024 * 1024;
const DATASET_PAGE_SIZE = 20;
const HASH = /^[0-9a-f]{64}$/;
const button = "btn btn-secondary";

type ImportMode = "history" | "records";
type ImportBusy = "preview" | "promote" | null;
type ImportActivity = { busy: ImportBusy; uncertain: boolean };

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
  if (error instanceof NetworkError) return `No se pudo contactar al servidor para ${action}. Iniciá el laboratorio desde el lanzador y volvé a intentar.`;
  if (error instanceof ApiError && error.status === 409) return "Los datos cambiaron o no hay espacio. Generá una vista previa nueva antes de guardar.";
  if (error instanceof ApiError && error.status === 413) return action.includes("historial")
    ? "El historial supera el límite de 32 MB. Elegí uno más pequeño."
    : "El archivo supera el límite de 2 MB. Elegí uno más pequeño.";
  if (error instanceof ApiError && error.status === 422) return "El servidor rechazó la solicitud. Revisá el archivo y los campos.";
  return `No se pudo ${action}. Revisá el archivo y los campos; si persiste, reiniciá el laboratorio desde el lanzador.`;
}

type HistoryMetadata = {
  schema_version: number;
  juego: string;
  origen: string;
  endpoint: string;
  zona_horaria: string;
  cantidad_sorteos: number;
  rango_seleccionado: { desde: string; hasta: string };
};

function boundedText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => typeof reader.result === "string" ? resolve(reader.result) : reject(new Error("invalid text"));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

type ImportEntryProps = {
  profiles: ProfileListing[];
  profilesLoading: boolean;
  profilesError: string;
  onCreateProfile: () => void;
  onRetryProfiles: () => void;
  mode: ImportMode;
  onModeChange: (mode: ImportMode) => void;
  recordsActivity: ImportActivity;
  registering: boolean;
  onHistoryActivity: (activity: ImportActivity) => void;
  onRecordsPreview: (event: React.FormEvent<HTMLFormElement>) => Promise<void>;
  recordsView: ReactNode;
  advanced: RefObject<HTMLDetailsElement>;
};

/** One entry owns mode selection and submission; each adapter retains its native draft. */
function HistoryImportAndLibrary({ profiles, profilesLoading, profilesError, onCreateProfile, onRetryProfiles,
  mode, onModeChange, recordsActivity, registering, onHistoryActivity, onRecordsPreview, recordsView, advanced }: ImportEntryProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [metadata, setMetadata] = useState<HistoryMetadata | null>(null);
  const [profileKey, setProfileKey] = useState("");
  const [sourceConfirmed, setSourceConfirmed] = useState(false);
  const [timezoneConfirmed, setTimezoneConfirmed] = useState(false);
  const [preview, setPreview] = useState<HistoryImportPreview | null>(null);
  const [saved, setSaved] = useState<ImportPromotion | null>(null);
  const [datasets, setDatasets] = useState<Page<DatasetListing> | null>(null);
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"preview" | "promote" | null>(null);
  const [promotionUncertain, setPromotionUncertain] = useState(false);
  const [libraryError, setLibraryError] = useState("");
  const [libraryLoading, setLibraryLoading] = useState(true);
  const generation = useRef(0);
  const fileReadGeneration = useRef(0);
  const mounted = useRef(true);
  const inFlight = useRef(false);
  const errorRef = useRef<HTMLParagraphElement>(null);
  const previewBinding = useRef<{ file: File; profile: ProfileListing; source: string; timezone: string; generation: number } | null>(null);
  const selected = profiles.find((item) => `${item.profile.profile_id}@${item.profile.revision}` === profileKey);

  useEffect(() => {
    let live = true;
    // The previous page stays mounted while the next one loads, so pagination controls keep their place and focus.
    setLibraryError(""); setLibraryLoading(true);
    apiClient.getDatasets(offset, DATASET_PAGE_SIZE).then((page) => {
      if (!live) return;
      setDatasets(page); setLibraryLoading(false);
    }).catch(() => {
      if (!live) return;
      setDatasets(null); setLibraryLoading(false); setLibraryError("No se pudo cargar la biblioteca local. Reintentá.");
    });
    return () => { live = false; };
  }, [offset, retry]);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; generation.current++; fileReadGeneration.current++; };
  }, []);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);

  useEffect(() => { onHistoryActivity({ busy, uncertain: promotionUncertain }); }, [busy, promotionUncertain, onHistoryActivity]);
  const modeLocked = busy !== null || promotionUncertain || recordsActivity.busy !== null || recordsActivity.uncertain || registering;
  function chooseMode(next: ImportMode) {
    if (modeLocked || inFlight.current) return;
    onModeChange(next);
  }
  function invalidate() {
    if (inFlight.current || promotionUncertain) return;
    generation.current++;
    previewBinding.current = null;
    setPreview(null); setSaved(null); setError(""); setBusy(null);
  }
  async function chooseFile(next: File | null) {
    if (inFlight.current || promotionUncertain || mode !== "history" || registering) return;
    invalidate(); const ticket = ++fileReadGeneration.current;
    setFile(next); setMetadata(null); setSourceConfirmed(false); setTimezoneConfirmed(false);
    if (!next) return;
    if (next.size > MAX_HISTORY_BYTES) { setError("El historial supera 32 MiB. Elegí un archivo más pequeño."); return; }
    try {
      // Metadata is parsed only from a size-bounded file. The original File remains the upload body.
      const document: unknown = JSON.parse(await boundedText(next));
      if (!document || typeof document !== "object" || !("metadata" in document) || !("sorteos_por_fecha" in document)) throw new Error();
      const raw = (document as { metadata: unknown }).metadata;
      if (!raw || typeof raw !== "object") throw new Error();
      const meta = raw as Partial<HistoryMetadata>;
      const range = meta.rango_seleccionado;
      if (meta.schema_version !== 1 || typeof meta.juego !== "string" || typeof meta.origen !== "string" ||
        typeof meta.endpoint !== "string" || typeof meta.zona_horaria !== "string" ||
        !Number.isSafeInteger(meta.cantidad_sorteos) || !range || typeof range.desde !== "string" || typeof range.hasta !== "string") throw new Error();
      if (mounted.current && ticket === fileReadGeneration.current) setMetadata(meta as HistoryMetadata);
    } catch {
      if (mounted.current && ticket === fileReadGeneration.current) setError("No se pudo leer el historial. Revisá que sea el JSON correcto.");
    }
  }
  async function showPreview(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || promotionUncertain || mode !== "history" || registering || busy !== null) return;
    invalidate();
    if (!file || !metadata) { setError("Elegí un archivo de historial válido."); return; }
    if (file.size > MAX_HISTORY_BYTES) { setError("El historial supera 32 MB. Elegí un archivo más pequeño."); return; }
    if (!selected) { setError("Elegí un perfil de juego."); return; }
    if (!sourceConfirmed || !timezoneConfirmed) { setError("Confirmá la fuente y la zona horaria."); return; }
    const ticket = generation.current;
    setBusy("preview"); setError("");
    try {
      const result = await apiClient.previewHistoryImport(file, selected, metadata.origen, metadata.zona_horaria);
      if (mounted.current && ticket === generation.current) {
        previewBinding.current = { file, profile: selected, source: metadata.origen, timezone: metadata.zona_horaria, generation: ticket };
        setPreview(result);
      }
    } catch (cause) {
      if (mounted.current && ticket === generation.current) setError(failureMessage(cause, "validar el historial"));
    } finally { if (mounted.current && ticket === generation.current) setBusy(null); }
  }
  async function promote() {
    const binding = previewBinding.current;
    if (inFlight.current || promotionUncertain || mode !== "history" || registering || busy !== null || !binding ||
      binding.generation !== generation.current || binding.file !== file || binding.profile.profile_sha256 !== selected?.profile_sha256 ||
      !preview?.promotable || !preview.dataset_sha256 || !HASH.test(preview.dataset_sha256)) return;
    inFlight.current = true; setBusy("promote"); setError("");
    const ticket = generation.current;
    try {
      const result = await apiClient.promoteHistoryImport(binding.file, binding.profile, binding.source, binding.timezone, preview.dataset_sha256);
      if (mounted.current && ticket === generation.current) { setSaved(result); setPreview(null); setOffset(0); setRetry((value) => value + 1); }
    } catch (cause) {
      if (mounted.current && ticket === generation.current) {
        setError(failureMessage(cause, "guardar el historial"));
        if (cause instanceof NetworkError || cause instanceof ApiError && cause.status >= 200 && cause.status < 300) setPromotionUncertain(true);
        setPreview(null);
      }
    } finally { inFlight.current = false; if (mounted.current && ticket === generation.current) setBusy(null); }
  }
  const bindingChanged = !!preview && previewBinding.current?.profile.profile_sha256 !== selected?.profile_sha256;
  const start = offset + 1;
  const importReason = !file ? "Elegí primero el archivo del historial." : !metadata ? "El archivo no es un historial válido." : !selected ? "Elegí un perfil de juego." : "";
  const importSection = <Block key="import" aria-labelledby="import-entry-title" className="space-y-5">
    <h2 id="import-entry-title" className="section-header">Importar datos</h2>
    <form aria-label="Importar datos" onSubmit={(event) => { void (mode === "history" ? showPreview(event) : onRecordsPreview(event)); }} className="space-y-5">
      <fieldset disabled={modeLocked} className="bf-segmented-fieldset">
        <legend className="field-label">Tipo de importación</legend>
        <label className="control-choice"><input type="radio" name="import-mode" value="history" checked={mode === "history"}
          onChange={() => chooseMode("history")} />Historial ordinario (JSON canónico)</label>
        <label className="control-choice"><input type="radio" name="import-mode" value="records" checked={mode === "records"}
          disabled={modeLocked} onChange={() => chooseMode("records")} />Archivo avanzado CSV o JSON (columnas y contexto explícitos)</label>
      </fieldset>
      <p role="status" aria-live="polite" className="field-help">Modo activo: {mode === "history" ? "historial ordinario" : "archivo avanzado CSV o JSON"}.</p>
      {modeLocked && <p className="field-help">No cambies de modo mientras hay una operación pendiente o un guardado sin confirmar.</p>}
      <section hidden={mode !== "history"} aria-labelledby="history-import-title" className="space-y-5">
    <div><h3 id="history-import-title" className="section-header">Importar historial</h3>
      <p className="field-help max-w-prose">Importar guarda datos, no ejecuta ni calcula pagos.</p></div>
    {datasets?.total === 0 && <ol aria-label="Cómo importar el primer historial" className="list-decimal space-y-1 pl-5 text-sm">
      <li>Elegí el historial JSON.</li>
      <li>Elegí un perfil de juego.</li>
      <li>Confirmá fuente y zona horaria.</li>
    </ol>}
    <fieldset disabled={mode !== "history" || busy === "promote" || promotionUncertain || registering} className="min-w-0 space-y-5">
      <legend className="sr-only">Historial ordinario</legend>
      <div className="field"><label htmlFor="history-file" className="field-label">Archivo del historial (hasta 32 MB)</label>
        <input id="history-file" type="file" accept=".json,application/json" className="control h-auto py-2" disabled={busy === "promote"}
          onChange={(event) => { void chooseFile(event.target.files?.[0] ?? null); }} />
        {file && <p className="field-help">Archivo seleccionado: {file.name}</p>}</div>
      {metadata && <section aria-label="Metadata detectada" className="space-y-2 border-y border-border py-4">
        <h3 className="field-label">Datos del archivo</h3>
        <p>Juego: {metadata.juego} · Origen: <strong>{metadata.origen}</strong> · Zona horaria: <strong>{metadata.zona_horaria}</strong></p>
        <p>Rango: {metadata.rango_seleccionado.desde} – {metadata.rango_seleccionado.hasta} · Sorteos: {metadata.cantidad_sorteos.toLocaleString("es-ES")}</p>
        <label className="control-choice"><input type="checkbox" className="control" checked={sourceConfirmed} disabled={busy === "promote"}
          onChange={(event) => { if (inFlight.current || promotionUncertain || registering || mode !== "history") return; invalidate(); setSourceConfirmed(event.target.checked); }} />Confirmo la fuente: {metadata.origen}</label>
        <label className="control-choice"><input type="checkbox" className="control" checked={timezoneConfirmed} disabled={busy === "promote"}
          onChange={(event) => { if (inFlight.current || promotionUncertain || registering || mode !== "history") return; invalidate(); setTimezoneConfirmed(event.target.checked); }} />Confirmo la zona horaria: {metadata.zona_horaria}</label>
      </section>}
      <div className="field"><label htmlFor="history-profile" className="field-label">Reglas del juego</label>
        <select id="history-profile" className="control" value={profileKey} disabled={busy === "promote" || profilesLoading} onChange={(event) => { if (inFlight.current || promotionUncertain || registering || mode !== "history") return; invalidate(); setProfileKey(event.target.value); }}>
          <option value="">Elegí las reglas del juego</option>{profiles.map(({ profile }) => <option key={`${profile.profile_id}@${profile.revision}`} value={`${profile.profile_id}@${profile.revision}`}>{profile.universe_size} números · {profile.positions} posiciones · {profile.currency}</option>)}
        </select>
        {profilesLoading ? <p role="status" className="field-help">Cargando perfiles…</p> : profilesError ? <><p role="alert" className="field-help">{profilesError}</p><button type="button" className="btn btn-tertiary" onClick={onRetryProfiles}>Reintentar perfiles</button></> : profiles.length === 0 && <div className="field-help space-y-2"><p>No hay perfiles todavía; creá uno para importar este historial.</p><button type="button" className="btn btn-primary" onClick={onCreateProfile}>Crear perfil</button><a className="link ml-3" href="#perfiles">Ver Perfiles de juego</a></div>}</div>
      {!preview && <div>
        <button type="submit" className="btn btn-primary" aria-busy={busy === "preview"} aria-describedby={importReason ? "history-import-reason" : undefined} disabled={busy !== null || promotionUncertain || !file || !metadata || !selected}>Importar historial</button>
        {importReason && <p id="history-import-reason" className="field-help">{importReason}</p>}
      </div>}
    </fieldset>
    {busy === "preview" && <p role="status">Validando historial…</p>}
    {error && <p ref={errorRef} tabIndex={-1} role="alert" className="border-y border-border py-3">{error}</p>}
    {promotionUncertain && <p role="status">No se confirmó el guardado. Comprobá el estado desde la cola antes de reintentar; también podés revisar la biblioteca.</p>}
    {preview && <section aria-labelledby="history-preview-title" className="space-y-3 border-t border-border pt-4">
      <h3 id="history-preview-title" className="section-header">Vista previa · {preview.promotable ? "lista para confirmar" : "no válida"}</h3>
      <p>Filas leídas: {preview.rows_seen.toLocaleString("es-ES")} · Sorteos: {preview.records_total.toLocaleString("es-ES")} · Duplicados: {preview.duplicates_merged.toLocaleString("es-ES")} · Errores: {preview.error_count}</p>
      {preview.errors.length > 0 && <ul aria-label="Errores de importación" className="list-disc pl-5">{preview.errors.map((issue, index) => <li key={index}>{issue.row ?? "Archivo"}: {issue.message}</li>)}</ul>}
      {preview.dataset_sha256 && <details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><p className="break-all text-sm">Huella del historial: <code>{preview.dataset_sha256}</code></p></details>}
      <button type="button" className="btn btn-primary" aria-busy={busy === "promote"} disabled={busy !== null || promotionUncertain || registering || bindingChanged || !preview.promotable || !preview.dataset_sha256 || !HASH.test(preview.dataset_sha256)} onClick={() => { void promote(); }}>Confirmar y guardar historial</button>
      <button type="button" className="btn btn-tertiary" disabled={busy !== null || promotionUncertain || registering} onClick={invalidate}>Cancelar vista previa</button>
    </section>}
    {busy === "promote" && <p role="status">Guardando; esperá la respuesta.</p>}
    {saved && <p role="status" className="border-y border-border py-3">{saved.created ? "Historial guardado." : "Este historial ya estaba guardado."}</p>}
      </section>
      <section aria-labelledby="advanced-title" className="border-t border-border pt-5">
        <h3 id="advanced-title" className="section-header">Más formas de importar</h3>
        <details ref={advanced} open={advancedOpen || mode === "records"} onToggle={(event) => {
          // Active drafts and recovery must not disappear behind a collapsed disclosure.
          if (mode === "records" && !event.currentTarget.open) event.currentTarget.open = true;
          setAdvancedOpen(event.currentTarget.open);
        }}>
          <summary className="disclosure-summary font-medium">Importar archivo CSV o JSON</summary>
          <div hidden={mode !== "records"} className="mt-5 space-y-8">{recordsView}</div>
        </details>
      </section>
    </form>
    </Block>;
  const librarySection = <Block key="library" id="historiales" aria-labelledby="history-library-title" className="space-y-4">
      <div><h2 id="history-library-title" className="section-header">Biblioteca de historiales</h2></div>
      {libraryLoading && !datasets && <Loading rows={3} label="Cargando historiales guardados…" />}
      {libraryError && <div role="alert" className="space-y-2"><p>{libraryError}</p><button type="button" className="btn btn-secondary" onClick={() => setRetry((value) => value + 1)}>Reintentar biblioteca</button></div>}
      {datasets && !libraryError && datasets.total === 0 && <div role="status"><p>Todavía no hay historiales guardados. Importá uno para usar sus sorteos en una simulación.</p><a className="btn btn-primary" href="#import-entry-title" onClick={(event) => {
        if (modeLocked || inFlight.current) { event.preventDefault(); return; }
        chooseMode("history");
      }}>Ir a importar historial</a></div>}
      {datasets && !libraryError && <ul aria-busy={libraryLoading} className="dataset-card-list">{datasets.items.map((item) => <li key={item.dataset_sha256} className="dataset-card">
        <div className="data-card-title"><h3>Historial · {item.records_total.toLocaleString("es-ES")} sorteos</h3><span className="neutral-stamp">{item.profile_execution.ready ? "Disponible" : "Sin reglas"}</span></div>
        <dl className="data-list"><dt>Fuente</dt><dd>{item.source_id}</dd><dt>Rango</dt><dd>{item.first_draw} – {item.last_draw}</dd><dt>Posiciones</dt><dd>{item.positions}</dd></dl>
        <p className="dataset-card-status" role="status">{item.profile_execution.ready ? "Reglas disponibles para usar este historial." : "No se puede usar todavía: faltan las reglas de juego guardadas."}</p>
        <details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><p className="break-all text-sm">Formato: {item.source_format} · revisión de fuente: {item.source_revision} · identificadores del perfil y la fuente: <code>{item.profile_id}@{item.profile_revision}</code> · huella del historial <code>{item.dataset_sha256}</code> · huella de la fuente <code>{item.source_sha256}</code></p></details>
        {item.profile_execution.ready
          ? <Link className="btn btn-tertiary" to={`/simulaciones/nueva/sesion?dataset_sha256=${encodeURIComponent(item.dataset_sha256)}`}>Usar este historial</Link>
          : <p className="field-help">Las reglas de juego usadas ya no están guardadas; registralas de nuevo para continuar.</p>}
      </li>)}</ul>}
      {datasets && !libraryError && datasets.total > DATASET_PAGE_SIZE && <nav aria-label="Páginas de historiales" className="flex items-center gap-3">
        <button type="button" className={button} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - DATASET_PAGE_SIZE))}>Anterior</button>
        <span>{start}–{Math.min(offset + DATASET_PAGE_SIZE, datasets.total)} de {datasets.total}</span>
        <button type="button" className={button} disabled={offset + DATASET_PAGE_SIZE >= datasets.total} onClick={() => setOffset(offset + DATASET_PAGE_SIZE)}>Siguiente</button>
      </nav>}
    </Block>;
  return <>{librarySection}{importSection}</>;
}

export function DataPage() {
  const [mode, setMode] = useState<ImportMode>("history");
  const [historyActivity, setHistoryActivity] = useState<ImportActivity>({ busy: null, uncertain: false });
  const [promotionUncertain, setPromotionUncertain] = useState(false);
  const [profiles, setProfiles] = useState<ProfileListing[]>([]);
  const [templates, setTemplates] = useState<PartialProfileTemplate[]>([]);
  const [registering, setRegistering] = useState(false);
  const [profileOpenRequest, setProfileOpenRequest] = useState(0);
  const [profileTotal, setProfileTotal] = useState(0);
  const [profilesLoading, setProfilesLoading] = useState(true);
  const [profilesError, setProfilesError] = useState("");
  const [profilesRetry, setProfilesRetry] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [draft, setDraft] = useState<Draft>(initial);
  const [preview, setPreview] = useState<{ body: ImportRequest; result: ImportPreview; generation: number } | null>(null);
  const [saved, setSaved] = useState<ImportPromotion | null>(null);
  const [error, setError] = useState("");
  const [errorField, setErrorField] = useState<string | null>(null);
  const [errorToken, setErrorToken] = useState(0);
  const [busy, setBusy] = useState<"preview" | "promote" | null>(null);
  const advanced = useRef<HTMLDetailsElement>(null);
  const generation = useRef(0);
  // Preview requests are replaceable; promotion is a mutation whose outcome cannot be cancelled safely.
  const activePreview = useRef<number | null>(null);
  const promotionInFlight = useRef(false);
  const errorRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    let live = true;
    setProfilesError("");
    setProfilesLoading(true);
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
    return () => { live = false; };
  }, [profilesRetry]);

  // A profiles retry must not invalidate an in-flight preview; only unmount does.
  useEffect(() => () => { generation.current++; }, []);

  useEffect(() => {
    if (!error) return;
    // The error lives inside the advanced disclosure: reveal it first, then land on the field it refers to.
    if (advanced.current && !advanced.current.open) advanced.current.open = true;
    const invalid = errorField ? document.getElementById(errorField) : null;
    (invalid ?? errorRef.current)?.focus();
    // errorToken re-runs this for a repeated identical message; errorField is committed together with it.
  }, [error, errorToken]);
  const bad = (id: string) => errorField === id ? { "aria-invalid": true as const, "aria-describedby": "import-error" } : {};
  /** Records a failure; `field` is the id of the first invalid control, omitted for server failures. */
  function fail(message: string, field: string | null = null) {
    setError(message); setErrorField(field); setErrorToken((value) => value + 1);
  }

  function invalidate() {
    if (promotionInFlight.current || promotionUncertain) return;
    generation.current++;
    setPreview(null);
    setSaved(null);
    setError("");
    setErrorField(null);
    setBusy(null);
  }
  function change(next: Partial<Draft>) {
    if (promotionInFlight.current || promotionUncertain || mode !== "records") return;
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
    if (mode !== "records" || promotionInFlight.current || promotionUncertain || registering || activePreview.current === generation.current) return;
    invalidate();
    if (!file) { fail("Elegí un archivo CSV o JSON.", "import-file"); return; }
    if (!draft.format || !draft.clockMode) { fail("Elegí el formato del archivo y cómo interpretar su hora.", !draft.format ? "import-format" : "clock-mode"); return; }
    if (file.size > MAX_BYTES) { fail("El archivo supera 2 MiB. Elegí uno más pequeño.", "import-file"); return; }
    const selected = profiles.find((item) => `${item.profile.profile_id}@${item.profile.revision}` === draft.profileKey);
    if (!selected) { fail("Elegí un perfil guardado.", "import-profile"); return; }
    const names = [draft.date, draft.time, ...draft.positions];
    const columns: [string, string][] = [["map-date", draft.date], ["map-time", draft.time],
      ...draft.positions.map((value, index): [string, string] => [`map-position-${index}`, value])];
    const seen = new Set<string>();
    const badColumn = columns.find(([, name]) => { const invalid = !name || name.trim() !== name || seen.has(name); seen.add(name); return invalid; });
    if (selected.profile.positions > 30 || names.length !== selected.profile.positions + 2 || badColumn) {
      fail("Indicá un nombre de columna distinto, sin espacios alrededor, para fecha, hora y cada posición.", badColumn?.[0] ?? "import-profile"); return;
    }
    const badSource = ([["sourceId", draft.sourceId], ["revision", draft.revision], ["provenance", draft.provenance]] as const)
      .find(([, value]) => !value || value.trim() !== value || value.length > 256)?.[0]
      ?? (draft.clockMode === "iana" && !draft.zone.trim() ? "clock-zone" : null);
    if (badSource) {
      fail("Completá fuente, revisión, procedencia y, si corresponde, la zona horaria; sin espacios alrededor.", badSource); return;
    }
    setBusy("preview");
    const ticket = generation.current;
    activePreview.current = ticket;
    try {
      const bytes = await readBytes(file);
      if (ticket !== generation.current) return;
      if (bytes.length > MAX_BYTES) { fail("El archivo supera 2 MiB. Elegí uno más pequeño.", "import-file"); return; }
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
      if (ticket === generation.current) fail(failureMessage(cause, "obtener la vista previa"));
    } finally {
      if (activePreview.current === ticket) activePreview.current = null;
      if (ticket === generation.current) setBusy(null);
    }
  }

  async function promote() {
    if (mode !== "records" || promotionInFlight.current || promotionUncertain || registering || !preview || preview.generation !== generation.current ||
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
        fail(failureMessage(cause, "guardar el archivo"));
        // A conflict or uncertain network result must never reuse an old preview.
        if (cause instanceof NetworkError || cause instanceof ApiError && cause.status >= 200 && cause.status < 300) setPromotionUncertain(true);
        setPreview(null);
      }
    } finally {
      promotionInFlight.current = false;
      if (ticket === generation.current) setBusy(null);
    }
  }

  function chooseMode(next: ImportMode) {
    if (promotionInFlight.current || busy !== null || promotionUncertain || registering ||
      historyActivity.busy !== null || historyActivity.uncertain) return;
    setMode(next);
  }

  const profilesSection = <section id="perfiles" aria-labelledby="profiles-title" className="bf-plate bf-section-plate space-y-4">
      <h2 id="profiles-title" className="section-header">Perfiles de juego</h2>
      {profilesLoading && <Loading rows={2} label="Cargando perfiles guardados…" />}
      {profilesError && <div role="alert" className="field-help space-y-2"><p>{profilesError}</p><button type="button" className="btn btn-tertiary" onClick={() => setProfilesRetry((value) => value + 1)}>Reintentar perfiles</button></div>}
      {!profilesLoading && !profilesError && profiles.length === 0 && <p role="status">Todavía no hay perfiles guardados. Creá uno para definir las reglas del sorteo con el botón «Crear perfil de juego».</p>}
      {profiles.length > 0 && <ul className="profile-card-list">{profiles.map(({ profile }) => <li key={`${profile.profile_id}@${profile.revision}`} className="profile-card">
        <div className="data-card-title"><h3>{profile.universe_size} números · {profile.positions} posiciones</h3><span className="neutral-stamp">Perfil guardado</span></div>
        <dl className="data-list"><dt>Repeticiones</dt><dd>{profile.allows_repeats ? "Permite repeticiones" : "Sin repeticiones"}</dd><dt>Moneda</dt><dd>{profile.currency}</dd></dl>
        <details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><p className="text-sm">ID: <code>{profile.profile_id}</code> · revisión: {profile.revision}</p></details>
      </li>)}</ul>}
      {profileTotal > 100 && <p role="status">Solo se pueden elegir los primeros 100 perfiles y los creados ahora.</p>}
      {templates.length > 0 && <p className="field-help">Las plantillas de catálogo son parciales; completá los campos faltantes.</p>}
      <ProfileEditor templates={templates} profiles={profiles} disabled={profilesLoading || !!profilesError || busy === "promote" || historyActivity.busy === "promote" || promotionUncertain || historyActivity.uncertain} openRequest={profileOpenRequest}
        onBusyChange={setRegistering} onRegistered={(item) => {
          const key = `${item.profile.profile_id}@${item.profile.revision}`;
          setProfiles((current) => [item, ...current.filter(({ profile }) => `${profile.profile_id}@${profile.revision}` !== key)]);
          setProfileTotal((total) => total + 1);
          invalidate();
          setDraft((current) => ({ ...current, profileKey: key,
            positions: Array.from({ length: item.profile.positions }, (_, index) => `pos${index + 1}`) }));
        }} />
    </section>;
  const recordsView = <>
      <fieldset disabled={mode !== "records" || busy === "promote" || promotionUncertain || registering} className="min-w-0 space-y-7">
      <legend className="sr-only">Configuración de importación</legend>
      <section aria-labelledby="file-heading" className="border-t border-border pt-5 space-y-4">
        <h3 id="file-heading" className="section-header">Archivo y perfil</h3>
        <div className="field"><label htmlFor="import-file" className="field-label">Archivo de datos (hasta 2 MB)</label>
          <input id="import-file" type="file" accept=".csv,.json,text/csv,application/json" className="control h-auto py-2" {...bad("import-file")} onChange={(event) => { if (mode !== "records" || promotionInFlight.current || promotionUncertain) return; invalidate(); setFile(event.target.files?.[0] ?? null); }} />
          {file && <p className="field-help">Archivo seleccionado: {file.name}</p>}</div>
        <div className="field"><label htmlFor="import-format" className="field-label">Formato del archivo</label>
          <select id="import-format" className="control" {...bad("import-format")} value={draft.format} onChange={(event) => change({ format: event.target.value as Draft["format"] })}><option value="">Elegí un formato</option><option value="csv">CSV</option><option value="json">JSON (lista plana de objetos)</option></select></div>
        <div className="field"><label htmlFor="import-profile" className="field-label">Perfil guardado completo</label>
          <select id="import-profile" className="control" {...bad("import-profile")} value={draft.profileKey} onChange={(event) => chooseProfile(event.target.value)}><option value="">Elegí un perfil</option>{profiles.map(({ profile }) => <option key={`${profile.profile_id}@${profile.revision}`} value={`${profile.profile_id}@${profile.revision}`}>{profile.profile_id} · revisión {profile.revision}</option>)}</select>
          {!profilesLoading && !profilesError && profiles.length === 0 && <div className="field-help space-y-2"><p>Necesitás un perfil para importar estos datos.</p><button type="button" className="btn btn-secondary" onClick={() => setProfileOpenRequest((value) => value + 1)}>Crear perfil</button><a className="link ml-3" href="#perfiles">Ver Perfiles de juego</a></div>}</div>
      </section>
      <section aria-labelledby="source-heading" className="border-t border-border pt-5 space-y-4">
        <h3 id="source-heading" className="section-header">Origen y hora</h3>
        {([ ["sourceId", "Identificador de fuente"], ["revision", "Revisión o corrección"], ["provenance", "Procedencia de los datos"] ] as const).map(([key, label]) => <div className="field" key={key}><label htmlFor={key} className="field-label">{label}</label><input id={key} className="control" {...bad(key)} maxLength={256} value={draft[key]} onChange={(event) => change({ [key]: event.target.value })} /></div>)}
        <div className="field"><label htmlFor="source-kind" className="field-label">Tipo de fuente</label><select id="source-kind" className="control" value={draft.kind} onChange={(event) => change({ kind: event.target.value as Draft["kind"] })}><option value="historical">Histórica</option><option value="artificial">Artificial</option></select></div>
        <div className="field"><label htmlFor="clock-mode" className="field-label">Interpretación de la hora</label><select id="clock-mode" className="control" {...bad("clock-mode")} value={draft.clockMode} onChange={(event) => change({ clockMode: event.target.value as Draft["clockMode"], zone: "" })}><option value="">Elegí una interpretación</option><option value="naive_legacy">Hora local, sin zona</option><option value="iana">Zona horaria concreta</option></select></div>
        {draft.clockMode === "iana" && <div className="field"><label htmlFor="clock-zone" className="field-label">Zona horaria (ej. America/Santo_Domingo)</label><input id="clock-zone" className="control" {...bad("clock-zone")} value={draft.zone} onChange={(event) => change({ zone: event.target.value })} /></div>}
      </section>
      <section aria-labelledby="mapping-heading" className="border-t border-border pt-5 space-y-4">
        <h3 id="mapping-heading" className="section-header">Columnas del archivo</h3>
        <p className="field-help">Escribí el nombre exacto de cada columna. Fecha AAAA-MM-DD, hora HH:MM.</p>
        <div className="grid gap-4 sm:grid-cols-2">{([ ["date", "Columna de fecha"], ["time", "Columna de hora"] ] as const).map(([key, label]) => <div key={key}><label htmlFor={`map-${key}`} className="field-label">{label}</label><input id={`map-${key}`} className="control" {...bad(`map-${key}`)} value={draft[key]} onChange={(event) => change({ [key]: event.target.value })} /></div>)}</div>
        <div className="grid gap-4 sm:grid-cols-2">{draft.positions.map((value, index) => <div key={index}><label htmlFor={`map-position-${index}`} className="field-label">Columna de posición {index + 1}</label><input id={`map-position-${index}`} className="control" {...bad(`map-position-${index}`)} value={value} onChange={(event) => change({ positions: draft.positions.map((item, at) => at === index ? event.target.value : item) })} /></div>)}</div>
      </section>
      <button type="submit" className="btn btn-secondary" aria-busy={busy === "preview"} disabled={busy !== null || promotionUncertain || registering || profilesLoading || !!profilesError}>Generar vista previa</button>
      </fieldset>
    {busy === "preview" && <p role="status">Validando archivo…</p>}
    {error && <p id="import-error" ref={errorRef} tabIndex={-1} role="alert" className="border-y border-border py-3 text-text">{error}</p>}
    {preview && <section aria-labelledby="preview-heading" className="border-t border-border pt-5 space-y-4">
      <h3 id="preview-heading" className="section-header">Vista previa · {preview.result.promotable ? "válida" : "no válida"}</h3>
      <p>Filas leídas: {preview.result.rows_seen} · Sorteos: {preview.result.records_total} · Duplicados: {preview.result.duplicates_merged} · Errores: {preview.result.error_count}{preview.result.errors_truncated ? " (lista parcial)" : ""}</p>
      {preview.result.errors.length > 0 && <ul aria-label="Errores de importación" className="list-disc space-y-1 pl-5">{preview.result.errors.map((issue, index) => <li key={index}> {issue.row === null ? "Archivo" : `Fila ${issue.row}`}: {issue.message}</li>)}</ul>}
      {preview.result.sample.length > 0 && <div><h4 className="field-label">Muestra (hasta 20 registros)</h4><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th scope="col" className="p-2">Fecha</th><th scope="col" className="p-2">Hora</th><th scope="col" className="p-2">Posiciones en orden</th></tr></thead><tbody>{preview.result.sample.map((record, index) => <tr key={index} className="border-t border-border"><td className="p-2">{record.date}</td><td className="p-2">{record.time}</td><td className="p-2">{record.numbers.join(", ")}</td></tr>)}</tbody></table></div></div>}
      <details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><div className="space-y-2 pt-2 text-sm">
        <p>Importar guarda datos, no ejecuta ni calcula pagos.</p>
        {preview.result.dataset_sha256 && <p className="break-all">Identidad canónica (SHA-256): <code>{preview.result.dataset_sha256}</code></p>}
        {preview.result.source_sha256 && <p className="break-all">Archivo de origen (SHA-256): <code>{preview.result.source_sha256}</code></p>}
        {preview.result.errors.length > 0 && <ul aria-label="Códigos técnicos de errores" className="list-disc pl-5">{preview.result.errors.map((issue, index) => <li key={index}>{issue.row === null ? "Archivo" : `Fila ${issue.row}`} · {issue.code}</li>)}</ul>}
      </div></details>
      <button type="button" className={button} disabled={busy !== null || promotionUncertain || registering || !preview.result.promotable || !preview.result.dataset_sha256 || !HASH.test(preview.result.dataset_sha256)} onClick={() => { void promote(); }}>Confirmar y guardar importación</button>
      <button type="button" className="btn btn-tertiary" disabled={busy !== null || promotionUncertain || registering} onClick={invalidate}>Cancelar vista previa</button>
    </section>}
    {promotionUncertain && <p role="status">No se confirmó el guardado. Comprobá el estado desde la cola o la biblioteca antes de reintentar.</p>}
    {busy === "promote" && <p role="status">Guardando; esperá la respuesta antes de volver a enviar.</p>}
    {saved && <section aria-labelledby="saved-heading" role="status" className="border-t border-border pt-5 space-y-2"><h3 id="saved-heading" className="section-header">{saved.created ? "Importación guardada" : "Historial ya guardado"}</h3><p>{saved.duplicate_source_differs ? "Ya existía el mismo historial con otro archivo de origen; se conserva el primero." : saved.created ? "Guardado." : "Ya existía; no se creó una copia."}</p><details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><div className="space-y-2 pt-2 text-sm"><p>Importar guarda datos, no ejecuta ni calcula pagos.</p><p className="break-all">Identidad canónica (SHA-256): <code>{saved.dataset_sha256}</code></p><p className="break-all">Archivo retenido (SHA-256): <code>{saved.retained_source_sha256}</code></p><p className="break-all">Archivo enviado (SHA-256): <code>{saved.submitted_source_sha256}</code></p></div></details></section>}
  </>;
  return <div className="max-w-4xl space-y-8">
    {profilesSection}
    <HistoryImportAndLibrary profiles={profiles} profilesLoading={profilesLoading} profilesError={profilesError}
      onRetryProfiles={() => setProfilesRetry((value) => value + 1)} onCreateProfile={() => setProfileOpenRequest((value) => value + 1)}
      mode={mode} onModeChange={chooseMode} recordsActivity={{ busy, uncertain: promotionUncertain }} registering={registering}
      onHistoryActivity={setHistoryActivity} onRecordsPreview={showPreview} recordsView={recordsView} advanced={advanced} />
  </div>;
}
