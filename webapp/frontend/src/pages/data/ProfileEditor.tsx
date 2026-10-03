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
const quiniela80: Draft = { profile_id: "quiniela-80", revision: "1", universe_size: "100", positions: "3",
  allows_repeats: "yes", multipliers: ["60", "10", "5"], currency: "DOP", scale: "0",
  stake_increment: "1", minimum_stake: "1", maximum_stake: "100", max_coverage: "10", max_exposure: "1000" };
const MAX_MONEY = 1_000_000_000_000n;

/** A validation failure tied to the control that should receive focus (element id). */
class FieldError extends Error {
  constructor(readonly field: string, message: string) { super(message); }
}
function at<T>(field: string, read: () => T): T {
  try { return read(); } catch (cause) { throw new FieldError(field, cause instanceof Error ? cause.message : "Revisá este campo."); }
}
function fail(field: string, message: string): never { throw new FieldError(field, message); }

function makeProfile(draft: Draft): GameProfile {
  if (!/^[a-z][a-z0-9-]{0,79}$/.test(draft.profile_id) || draft.profile_id === "legacy-quiniela-80") {
    fail("profile-id", "ID: usá minúsculas, números o guiones (hasta 80), empezando con una letra. Ese ID está reservado.");
  }
  const revision = at("profile-revision", () => wholeNumber(draft.revision, "Revisión", 1n, 1_000_000n));
  const universe_size = at("profile-universe", () => wholeNumber(draft.universe_size, "Universo", 1n, 1_000n));
  const positions = at("profile-positions", () => wholeNumber(draft.positions, "Posiciones", 1n, 16n));
  if (!draft.allows_repeats) fail("profile-repeats", "Repeticiones: elegí sí o no.");
  if (draft.allows_repeats === "no" && positions > universe_size) fail("profile-positions", "Las posiciones superan el universo sin repetición.");
  if (draft.multipliers.length !== positions) fail("profile-positions", "Indicá un premio por cada posición.");
  const multipliers = draft.multipliers.map((value, index) => at(`profile-multiplier-${index}`, () => exactMultiplier(value, `Premio de posición ${index + 1}`)));
  if (!/^[A-Z]{3}$/.test(draft.currency)) fail("profile-currency", "Moneda: ingresá exactamente tres letras mayúsculas ISO (por ejemplo, DOP).");
  const scale = at("profile-scale", () => wholeNumber(draft.scale, "Escala", 0n, 6n));
  const stake_increment = at("profile-stake_increment", () => moneyUnits(draft.stake_increment, scale, "Incremento"));
  const minimum_stake = at("profile-minimum_stake", () => moneyUnits(draft.minimum_stake, scale, "Apuesta mínima"));
  const maximum_stake = at("profile-maximum_stake", () => moneyUnits(draft.maximum_stake, scale, "Apuesta máxima"));
  const max_coverage = at("profile-coverage", () => wholeNumber(draft.max_coverage, "Cobertura", 1n, BigInt(universe_size)));
  const max_exposure = at("profile-max_exposure", () => moneyUnits(draft.max_exposure, scale, "Exposición máxima"));
  if (minimum_stake > maximum_stake || maximum_stake > max_exposure ||
      minimum_stake % stake_increment || maximum_stake % stake_increment ||
      BigInt(max_coverage) * BigInt(minimum_stake) > BigInt(max_exposure)) {
    fail("profile-minimum_stake", "Apuestas: mínima ≤ máxima ≤ exposición; mínima y máxima deben ser múltiplos del incremento y la cobertura mínima debe caber en la exposición.");
  }
  if (multipliers.some(({ numerator, denominator }) => BigInt(stake_increment) * BigInt(numerator) % BigInt(denominator) !== 0n)) {
    fail("profile-stake_increment", "Premios: el incremento debe producir pagos enteros en la escala elegida para cada posición.");
  }
  // Conservative all-settlement ceiling, evaluated without floating point.
  if (multipliers.some(({ numerator, denominator }) => BigInt(max_exposure) * BigInt(numerator) > MAX_MONEY * BigInt(denominator))) {
    fail("profile-max_exposure", "Premios: la exposición multiplicada por un premio supera el límite seguro del servidor.");
  }
  let totalNumerator = 0n;
  let totalDenominator = 1n;
  for (const { numerator, denominator } of multipliers) {
    totalNumerator = totalNumerator * BigInt(denominator) + BigInt(numerator) * totalDenominator;
    totalDenominator *= BigInt(denominator);
  }
  if (BigInt(max_exposure) * totalNumerator > MAX_MONEY * totalDenominator) {
    fail("profile-max_exposure", "Premios: el pago total máximo de todas las posiciones supera el límite seguro del servidor.");
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

export function ProfileEditor({ templates, profiles, onRegistered, onBusyChange, disabled = false, openRequest = 0 }: {
  templates: PartialProfileTemplate[];
  profiles: ProfileListing[];
  onRegistered: (item: ProfileListing) => void;
  onBusyChange: (busy: boolean) => void;
  disabled?: boolean;
  openRequest?: number;
}) {
  const [open, setOpen] = useState(false);
  const [templateIndex, setTemplateIndex] = useState("");
  const [draft, setDraft] = useState<Draft>(quiniela80);

  const [error, setError] = useState("");
  const [errorCode, setErrorCode] = useState<number | null>(null);
  const [errorField, setErrorField] = useState<string | null>(null);
  const [errorToken, setErrorToken] = useState(0);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const inFlight = useRef(false);
  const live = useRef(true);
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => { if (openRequest) setOpen(true); }, [openRequest]);
  useEffect(() => {
    if (!error) return;
    // Validation inside a collapsed host disclosure must be visible before focus moves.
    const invalid = errorField ? document.getElementById(errorField) : null;
    let host = invalid?.closest("details") as HTMLDetailsElement | null;
    while (host) { host.open = true; host = host.parentElement?.closest("details") as HTMLDetailsElement | null; }
    (invalid ?? errorRef.current)?.focus();
    // errorToken re-runs this for a repeated identical message; errorField is committed together with it.
  }, [error, errorToken]);
  const bad = (id: string) => errorField === id ? { "aria-invalid": true as const, "aria-describedby": "profile-error" } : {};
  const selectedTemplate = templateIndex === "" ? null : templates[Number(templateIndex)] ?? null;
  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setError(""); setErrorCode(null); setErrorField(null); setNotice("");
  }
  function changePositions(value: string) {
    setDraft((current) => ({ ...current, positions: value, multipliers: /^(?:[1-9]|1[0-6])$/.test(value)
      ? Array.from({ length: Number(value) }, (_, index) => current.multipliers[index] ?? "") : [] }));
    setError(""); setErrorCode(null); setErrorField(null); setNotice("");
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || disabled) return;
    setError(""); setErrorCode(null); setErrorField(null); setNotice("");
    let profile: GameProfile;
    try {
      profile = makeProfile(draft);
      if (profiles.some(({ profile: saved }) => saved.profile_id === profile.profile_id && saved.revision === profile.revision)) {
        fail("profile-revision", "Ese ID y revisión ya existen. Elegí una revisión nueva.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Revisá los campos del perfil.");
      setErrorField(cause instanceof FieldError ? cause.field : null); setErrorToken((value) => value + 1);
      return;
    }
    inFlight.current = true; setPending(true); onBusyChange(true);
    try {
      const item = await apiClient.registerProfile(profile);
      if (!live.current) return;
      onRegistered(item);
      setNotice("Perfil guardado y seleccionado.");
    } catch (cause) {
      if (!live.current) return;
      setErrorCode(cause instanceof ApiError ? cause.status : null);
      if (cause instanceof ApiError && cause.status === 409) {
        setError(/quota/i.test(cause.detail) ? "No hay espacio para guardar el perfil. Liberá almacenamiento y reintentá." :
          "Ese ID y revisión ya existen con otro contenido. Elegí una revisión nueva.");
      } else if (cause instanceof ApiError && cause.status === 422) {
        setError("El servidor rechazó el perfil. Revisá los campos; no se guardó.");
      } else if (cause instanceof NetworkError) {
        setError("Sin respuesta del servidor. Puede que se haya guardado; revisá la lista antes de reenviar.");
      } else setError("No se pudo confirmar el guardado. Revisá la lista antes de reintentar.");
    } finally {
      inFlight.current = false;
      if (live.current) { setPending(false); onBusyChange(false); }
    }
  }
  return <section aria-labelledby="profile-editor-heading" className="border-t border-border pt-5 space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 id="profile-editor-heading" className="section-header">Crear perfil de juego</h3></div>
      <button type="button" className="btn btn-primary" aria-expanded={open} aria-controls="profile-editor-form" disabled={disabled || pending} onClick={() => setOpen(!open)}>{open ? "Cerrar editor" : "Crear perfil de juego"}</button></div>
    {open && <div id="profile-editor-form" className="space-y-5">
            <div className={field}><label htmlFor="profile-template" className="field-label">Referencia opcional</label><select id="profile-template" className={input} disabled={pending || disabled} value={templateIndex} onChange={(event) => { const value = event.target.value; setTemplateIndex(value); setDraft(value === "" ? empty : fromTemplate(templates[Number(value)])); setError(""); setErrorCode(null); setNotice(""); }}><option value="">Empezar sin plantilla</option>{templates.map((template, index) => <option value={index} key={`${template.name}-${index}`}>{template.name} · parcial</option>)}</select>
        {templates.length > 0 && <p className="field-help">Las plantillas de catálogo son parciales; completá los campos que faltan.</p>}
        {selectedTemplate && <div className="field-help"><p>Origen: {selectedTemplate.provenance}.</p><p>Falta completar: {selectedTemplate.missing_fields.join(", ")}.</p>{selectedTemplate.known_fields.minimum_stake !== undefined && <p>Apuesta mínima conocida: {selectedTemplate.known_fields.minimum_stake} unidad(es) sin escala; ingresá el importe tras elegirla.</p>}</div>}</div>
      <form onSubmit={(event) => { void submit(event); }} noValidate>
        <fieldset disabled={pending || disabled} className="min-w-0 space-y-6"><legend className="sr-only">Perfil de juego completo</legend>
          <section aria-labelledby="profile-identity" className="border-t border-border pt-4"><h4 id="profile-identity" className="section-header">Reglas del sorteo</h4><div className="grid gap-x-5 sm:grid-cols-2">
            <div className={field}><label htmlFor="profile-universe" className="field-label">Tamaño del universo (1–1.000)</label><input id="profile-universe" className={input} {...bad("profile-universe")} inputMode="numeric" required value={draft.universe_size} onChange={(event) => update("universe_size", event.target.value)} /></div>
            <div className={field}><label htmlFor="profile-positions" className="field-label">Posiciones por sorteo (1–16)</label><input id="profile-positions" className={input} {...bad("profile-positions")} inputMode="numeric" required value={draft.positions} onChange={(event) => changePositions(event.target.value)} /></div>
            <div className={field}><label htmlFor="profile-repeats" className="field-label">¿Se repiten números en un sorteo?</label><select id="profile-repeats" className={input} {...bad("profile-repeats")} required value={draft.allows_repeats} onChange={(event) => update("allows_repeats", event.target.value)}><option value="">Elegí sí o no</option><option value="yes">Sí</option><option value="no">No</option></select></div>
          </div></section>
          <section aria-labelledby="profile-prizes" className="border-t border-border pt-4"><h4 id="profile-prizes" className="section-header">Premios por posición</h4><p className="field-help mb-4">Premio total por unidad apostada, sin devolución adicional de la apuesta: entero, decimal (1.25) o fracción (5/4).</p>
            <div className="grid gap-x-5 sm:grid-cols-3">{draft.multipliers.map((value, index) => <div key={index} className={field}><label htmlFor={`profile-multiplier-${index}`} className="field-label">Posición {index + 1} · multiplicador</label><input id={`profile-multiplier-${index}`} className={input} {...bad(`profile-multiplier-${index}`)} inputMode="decimal" required value={value} onChange={(event) => update("multipliers", draft.multipliers.map((item, at) => at === index ? event.target.value : item))} /></div>)}</div></section>
          <section aria-labelledby="profile-money" className="border-t border-border pt-4"><h4 id="profile-money" className="section-header">Moneda y límites de apuesta</h4><p className="field-help mb-4">Importes en la moneda elegida; la escala son sus decimales.</p><div className="grid gap-x-5 sm:grid-cols-2">
            <div className={field}><label htmlFor="profile-currency" className="field-label">Moneda (código ISO de 3 letras)</label><input id="profile-currency" className={input} {...bad("profile-currency")} maxLength={3} required value={draft.currency} onChange={(event) => update("currency", event.target.value)} /></div>
            <div className={field}><label htmlFor="profile-scale" className="field-label">Escala decimal (0–6)</label><input id="profile-scale" className={input} {...bad("profile-scale")} inputMode="numeric" required value={draft.scale} onChange={(event) => update("scale", event.target.value)} /><p className="field-help">0 = sin escala.</p></div>
            {([ ["stake_increment", "Incremento de apuesta"], ["minimum_stake", "Apuesta mínima"], ["maximum_stake", "Apuesta máxima"], ["max_exposure", "Exposición máxima por sorteo"] ] as const).map(([key, label]) => <div key={key} className={field}><label htmlFor={`profile-${key}`} className="field-label">{label} (importe)</label><input id={`profile-${key}`} className={input} {...bad(`profile-${key}`)} inputMode="decimal" required value={draft[key]} onChange={(event) => update(key, event.target.value)} /></div>)}
            <div className={field}><label htmlFor="profile-coverage" className="field-label">Cobertura máxima (números por sorteo)</label><input id="profile-coverage" className={input} {...bad("profile-coverage")} inputMode="numeric" required value={draft.max_coverage} onChange={(event) => update("max_coverage", event.target.value)} /></div>
          </div></section>
          <details><summary className="disclosure-summary">Detalles técnicos</summary><section aria-label="Identificadores del perfil" className="grid gap-x-5 pt-4 sm:grid-cols-2">
            <div className={field}><label htmlFor="profile-id" className="field-label">ID nuevo del perfil</label><input id="profile-id" className={input} {...bad("profile-id")} required pattern="[a-z][a-z0-9-]*" maxLength={80} value={draft.profile_id} onChange={(event) => update("profile_id", event.target.value)} /></div>
            <div className={field}><label htmlFor="profile-revision" className="field-label">Revisión (1–1.000.000)</label><input id="profile-revision" className={input} {...bad("profile-revision")} inputMode="numeric" required value={draft.revision} onChange={(event) => update("revision", event.target.value)} /></div>
          </section></details>
          <button type="submit" className="btn btn-secondary">Guardar perfil</button>
        </fieldset>
      </form>
      {pending && <p role="status">Guardando perfil; esperá la respuesta.</p>}
      {error && <p id="profile-error" ref={errorRef} tabIndex={-1} role="alert" className="border-y border-border py-3">{error}</p>}
      {errorCode !== null && <details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><p className="text-sm">Código HTTP: <code>{errorCode}</code></p></details>}
      {notice && <p role="status" className="border-y border-border py-3">{notice}</p>}
    </div>}
  </section>;
}
