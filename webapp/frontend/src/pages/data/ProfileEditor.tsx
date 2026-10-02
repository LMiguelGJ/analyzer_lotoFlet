import { useEffect, useRef, useState } from "react";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { GameProfile, PartialProfileTemplate, ProfileListing } from "../../api/types";
import { exactMultiplier, moneyUnits, wholeNumber } from "../../lib/profile-input";

type Draft = {
  profile_id: string; revision: string; universe_size: string; positions: string;
  allows_repeats: string; multipliers: string[]; currency: string; scale: string;
  stake_increment: string; minimum_stake: string; maximum_stake: string;
  max_coverage: string; max_exposure: string;
};
const empty: Draft = { profile_id: "", revision: "", universe_size: "", positions: "", allows_repeats: "",
  multipliers: [], currency: "", scale: "", stake_increment: "", minimum_stake: "",
  maximum_stake: "", max_coverage: "", max_exposure: "" };
const MAX_MONEY = 1_000_000_000_000n;

function makeProfile(draft: Draft): GameProfile {
  if (!/^[a-z][a-z0-9-]{0,79}$/.test(draft.profile_id) || draft.profile_id === "legacy-quiniela-80") {
    throw new Error("ID: usá 1–80 caracteres (minúsculas, números o guiones), empezando con una letra. La identidad heredada está reservada.");
  }
  const revision = wholeNumber(draft.revision, "Revisión", 1n, 1_000_000n);
  const universe_size = wholeNumber(draft.universe_size, "Universo", 1n, 1_000n);
  const positions = wholeNumber(draft.positions, "Posiciones", 1n, 16n);
  if (!draft.allows_repeats) throw new Error("Repeticiones: elegí sí o no.");
  if (draft.allows_repeats === "no" && positions > universe_size) throw new Error("Las posiciones superan el universo sin repetición.");
  if (draft.multipliers.length !== positions) throw new Error("Indicá un premio por cada posición.");
  const multipliers = draft.multipliers.map((value, index) => exactMultiplier(value, `Premio de posición ${index + 1}`));
  if (!/^[A-Z]{3}$/.test(draft.currency)) throw new Error("Moneda: ingresá exactamente tres letras mayúsculas ISO (por ejemplo, DOP).");
  const scale = wholeNumber(draft.scale, "Escala", 0n, 6n);
  const stake_increment = moneyUnits(draft.stake_increment, scale, "Incremento");
  const minimum_stake = moneyUnits(draft.minimum_stake, scale, "Apuesta mínima");
  const maximum_stake = moneyUnits(draft.maximum_stake, scale, "Apuesta máxima");
  const max_coverage = wholeNumber(draft.max_coverage, "Cobertura", 1n, BigInt(universe_size));
  const max_exposure = moneyUnits(draft.max_exposure, scale, "Exposición máxima");
  if (minimum_stake > maximum_stake || maximum_stake > max_exposure ||
      minimum_stake % stake_increment || maximum_stake % stake_increment ||
      BigInt(max_coverage) * BigInt(minimum_stake) > BigInt(max_exposure)) {
    throw new Error("Apuestas: mínima ≤ máxima ≤ exposición; mínima y máxima deben ser múltiplos del incremento y la cobertura mínima debe caber en la exposición.");
  }
  if (multipliers.some(({ numerator, denominator }) => BigInt(stake_increment) * BigInt(numerator) % BigInt(denominator) !== 0n)) {
    throw new Error("Premios: el incremento debe producir pagos enteros en la escala elegida para cada posición.");
  }
  // Conservative all-settlement ceiling, evaluated without floating point.
  if (multipliers.some(({ numerator, denominator }) => BigInt(max_exposure) * BigInt(numerator) > MAX_MONEY * BigInt(denominator))) {
    throw new Error("Premios: la exposición multiplicada por un premio supera el límite seguro del servidor.");
  }
  let totalNumerator = 0n;
  let totalDenominator = 1n;
  for (const { numerator, denominator } of multipliers) {
    totalNumerator = totalNumerator * BigInt(denominator) + BigInt(numerator) * totalDenominator;
    totalDenominator *= BigInt(denominator);
  }
  if (BigInt(max_exposure) * totalNumerator > MAX_MONEY * totalDenominator) {
    throw new Error("Premios: el pago total máximo de todas las posiciones supera el límite seguro del servidor.");
  }
  return { schema_version: 1, profile_id: draft.profile_id, revision, universe_size, positions,
    allows_repeats: draft.allows_repeats === "yes", multipliers, currency: draft.currency, scale,
    stake_increment, minimum_stake, maximum_stake, max_coverage, max_exposure, best_rule: "maximum-payout/v1" };
}

function fromTemplate(template: PartialProfileTemplate): Draft {
  const known = template.known_fields;
  return { ...empty, universe_size: known.universe_size?.toString() ?? "", positions: known.positions?.toString() ?? "",
    allows_repeats: known.allows_repeats === undefined ? "" : known.allows_repeats ? "yes" : "no",
    multipliers: known.multipliers?.map(({ numerator, denominator }) => `${numerator}/${denominator}`) ?? [],
    currency: known.currency ?? "" };
}

const field = "field";
const input = "control";

export function ProfileEditor({ templates, profiles, onRegistered, onBusyChange, disabled = false }: {
  templates: PartialProfileTemplate[];
  profiles: ProfileListing[];
  onRegistered: (item: ProfileListing) => void;
  onBusyChange: (busy: boolean) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [templateIndex, setTemplateIndex] = useState("");
  const [draft, setDraft] = useState<Draft>(empty);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const inFlight = useRef(false);
  const live = useRef(true);
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  const selectedTemplate = templateIndex === "" ? null : templates[Number(templateIndex)] ?? null;
  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setError(""); setNotice("");
  }
  function changePositions(value: string) {
    setDraft((current) => ({ ...current, positions: value, multipliers: /^(?:[1-9]|1[0-6])$/.test(value)
      ? Array.from({ length: Number(value) }, (_, index) => current.multipliers[index] ?? "") : [] }));
    setError(""); setNotice("");
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || disabled) return;
    setError(""); setNotice("");
    let profile: GameProfile;
    try {
      profile = makeProfile(draft);
      if (profiles.some(({ profile: saved }) => saved.profile_id === profile.profile_id && saved.revision === profile.revision)) {
        throw new Error("Ese ID y revisión ya están guardados. Elegí una revisión nueva; no se modifica una versión existente.");
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Revisá los campos del perfil."); return; }
    inFlight.current = true; setPending(true); onBusyChange(true);
    try {
      const item = await apiClient.registerProfile(profile);
      if (!live.current) return;
      onRegistered(item);
      setNotice("Perfil registrado y seleccionado para importar. La respuesta del servidor confirma su hash y disponibilidad; no se calculan premios en el navegador.");
    } catch (cause) {
      if (!live.current) return;
      if (cause instanceof ApiError && cause.status === 409) {
        setError(/quota/i.test(cause.detail) ? "No hay espacio de cuota para guardar el perfil. Revisá almacenamiento antes de volver a intentarlo." :
          "Ese ID y revisión ya tienen contenido diferente. Elegí una revisión nueva; no se sobrescriben perfiles guardados.");
      } else if (cause instanceof ApiError && cause.status === 422) {
        setError("El servidor rechazó el perfil (422). Revisá todos los campos y sus límites; no se guardó esta versión.");
      } else if (cause instanceof NetworkError) {
        setError("No llegó una respuesta del servidor. La solicitud podría haberse guardado; verificá el catálogo antes de volver a enviarla.");
      } else setError("No se pudo confirmar el registro. Comprobá el catálogo antes de intentar de nuevo.");
    } finally {
      inFlight.current = false;
      if (live.current) { setPending(false); onBusyChange(false); }
    }
  }
  return <section aria-labelledby="profile-editor-heading" className="border-t border-border pt-5 space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 id="profile-editor-heading" className="section-header">Perfiles de juego</h2>
      <p className="field-help max-w-prose">Registrá una versión completa e inmutable antes de importarla. Hasta 16 posiciones y 1.000 números son límites técnicos actuales, no una promesa de capacidad ilimitada.</p></div>
      <button type="button" className="btn btn-secondary" aria-expanded={open} aria-controls="profile-editor-form" disabled={disabled || pending} onClick={() => setOpen(!open)}>{open ? "Cerrar editor" : "Crear perfil"}</button></div>
    {open && <div id="profile-editor-form" className="space-y-5">
      <p className="max-w-prose text-sm text-text-secondary">Las plantillas son referencias incompletas. Solo se precargan campos documentados; declarás vos el resto, incluidos límites financieros. Registrar no ejecuta sesiones ni calcula pagos.</p>
      <div className={field}><label htmlFor="profile-template" className="field-label">Referencia opcional</label><select id="profile-template" className={input} disabled={pending || disabled} value={templateIndex} onChange={(event) => { const value = event.target.value; setTemplateIndex(value); setDraft(value === "" ? empty : fromTemplate(templates[Number(value)])); setError(""); setNotice(""); }}><option value="">Empezar sin plantilla</option>{templates.map((template, index) => <option value={index} key={`${template.name}-${index}`}>{template.name} · parcial</option>)}</select>
        {selectedTemplate && <div className="field-help"><p>Origen: {selectedTemplate.provenance}. Datos conocidos precargados donde corresponden; valores sin escala monetaria se muestran como unidades, no como importes.</p><p>Campos pendientes en la referencia: {selectedTemplate.missing_fields.join(", ")}.</p>{selectedTemplate.known_fields.minimum_stake !== undefined && <p>Apuesta mínima conocida: {selectedTemplate.known_fields.minimum_stake} unidad(es) sin escala declarada; ingresá su importe luego de elegir la escala.</p>}</div>}</div>
      <form onSubmit={(event) => { void submit(event); }} noValidate>
        <fieldset disabled={pending || disabled} className="min-w-0 space-y-6"><legend className="sr-only">Perfil de juego completo</legend>
          <section aria-labelledby="profile-identity" className="border-t border-border pt-4"><h3 id="profile-identity" className="section-header">Identidad y sorteo</h3><div className="grid gap-x-5 sm:grid-cols-2">
            <div className={field}><label htmlFor="profile-id" className="field-label">ID nuevo del perfil</label><input id="profile-id" className={input} required pattern="[a-z][a-z0-9-]*" maxLength={80} value={draft.profile_id} onChange={(event) => update("profile_id", event.target.value)} /><p className="field-help">Una revisión guardada no se sobrescribe.</p></div>
            <div className={field}><label htmlFor="profile-revision" className="field-label">Revisión (1–1.000.000)</label><input id="profile-revision" className={input} inputMode="numeric" required value={draft.revision} onChange={(event) => update("revision", event.target.value)} /></div>
            <div className={field}><label htmlFor="profile-universe" className="field-label">Tamaño del universo (1–1.000)</label><input id="profile-universe" className={input} inputMode="numeric" required value={draft.universe_size} onChange={(event) => update("universe_size", event.target.value)} /></div>
            <div className={field}><label htmlFor="profile-positions" className="field-label">Posiciones por sorteo (1–16)</label><input id="profile-positions" className={input} inputMode="numeric" required value={draft.positions} onChange={(event) => changePositions(event.target.value)} /></div>
            <div className={field}><label htmlFor="profile-repeats" className="field-label">¿Se repiten números en un sorteo?</label><select id="profile-repeats" className={input} required value={draft.allows_repeats} onChange={(event) => update("allows_repeats", event.target.value)}><option value="">Elegí sí o no</option><option value="yes">Sí</option><option value="no">No</option></select></div>
          </div></section>
          <section aria-labelledby="profile-prizes" className="border-t border-border pt-4"><h3 id="profile-prizes" className="section-header">Premios por posición</h3><p className="field-help mb-4">Multiplicador de pago total por unidad apostada, en orden. Entero, decimal exacto (ej. 1.25) o fracción (ej. 5/4). No incluye devolución adicional.</p>
            <div className="grid gap-x-5 sm:grid-cols-3">{draft.multipliers.map((value, index) => <div key={index} className={field}><label htmlFor={`profile-multiplier-${index}`} className="field-label">Posición {index + 1} · multiplicador</label><input id={`profile-multiplier-${index}`} className={input} inputMode="decimal" required value={value} onChange={(event) => update("multipliers", draft.multipliers.map((item, at) => at === index ? event.target.value : item))} /></div>)}</div></section>
          <section aria-labelledby="profile-money" className="border-t border-border pt-4"><h3 id="profile-money" className="section-header">Moneda y límites de apuesta</h3><p className="field-help mb-4">Importes humanos en la moneda elegida. La escala (0–6 decimales) convierte cada importe a unidades enteras exactas. Definí explícitamente cada límite; no hay política financiera predeterminada.</p><div className="grid gap-x-5 sm:grid-cols-2">
            <div className={field}><label htmlFor="profile-currency" className="field-label">Moneda (código ISO de 3 letras)</label><input id="profile-currency" className={input} maxLength={3} required value={draft.currency} onChange={(event) => update("currency", event.target.value)} /></div>
            <div className={field}><label htmlFor="profile-scale" className="field-label">Escala decimal (0–6)</label><input id="profile-scale" className={input} inputMode="numeric" required value={draft.scale} onChange={(event) => update("scale", event.target.value)} /></div>
            {([ ["stake_increment", "Incremento de apuesta"], ["minimum_stake", "Apuesta mínima"], ["maximum_stake", "Apuesta máxima"], ["max_exposure", "Exposición máxima por sorteo"] ] as const).map(([key, label]) => <div key={key} className={field}><label htmlFor={`profile-${key}`} className="field-label">{label} (importe)</label><input id={`profile-${key}`} className={input} inputMode="decimal" required value={draft[key]} onChange={(event) => update(key, event.target.value)} /></div>)}
            <div className={field}><label htmlFor="profile-coverage" className="field-label">Cobertura máxima (números por sorteo)</label><input id="profile-coverage" className={input} inputMode="numeric" required value={draft.max_coverage} onChange={(event) => update("max_coverage", event.target.value)} /></div>
          </div><p className="field-help">Regla de mejor premio para perfiles nuevos: máximo pago (maximum-payout/v1). Esquema: versión 1. Ambos son requeridos por el contrato actual.</p></section>
          <button type="submit" className="btn btn-primary disabled:opacity-50">Registrar perfil inmutable</button>
        </fieldset>
      </form>
      {pending && <p role="status">Registro enviado; respuesta pendiente. No lo reenvíes hasta confirmar el resultado.</p>}
      {error && <p ref={errorRef} tabIndex={-1} role="alert" className="border-y border-border py-3">{error}</p>}
      {notice && <p role="status" className="border-y border-border py-3">{notice}</p>}
    </div>}
  </section>;
}
