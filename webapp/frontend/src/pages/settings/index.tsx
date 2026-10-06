import { useEffect, useRef, useState } from "react";
import { Link, useBlocker, useSearchParams } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { GameSettings, GameSettingsSource, SettingsView } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorBanner, Loading } from "../../components/ui";
import { formatDOP } from "../../lib/format";

const MAX_QUOTA = 9223372036854775807n;
const GIB = 1073741824n;
const action = "btn btn-secondary disabled:cursor-not-allowed";
const metric = "metric-item";

function grouped(value: bigint): string {
  try { return new Intl.NumberFormat("es-DO", { useGrouping: true }).format(value); }
  catch { return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
}
function bytes(value: string): string {
  // Exact string/BigInt path: do not round an int64 quota through Number.
  return `${grouped(BigInt(value))} bytes`;
}
function readableCapacity(value: string): string {
  const exact = BigInt(value);
  const units = [[1099511627776n, "TiB"], [GIB, "GiB"], [1048576n, "MiB"], [1024n, "KiB"]] as const;
  const [divisor, label] = units.find(([size]) => exact >= size) ?? [1n, "bytes"];
  if (divisor === 1n) return `${grouped(exact)} ${label}`;
  const tenths = (exact * 10n + divisor / 2n) / divisor;
  return `${grouped(tenths / 10n)}${tenths % 10n ? `.${tenths % 10n}` : ""} ${label}`;
}
function measured(value: number): string {
  // Physical and free-disk fields are legacy JSON numbers; unlike quota they
  // have no exact string representation from this API.
  try { return `${new Intl.NumberFormat("es-DO").format(value)} bytes`; }
  catch { return `${String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",")} bytes`; }
}
function validate(value: string): string | null {
  if (!/^[1-9][0-9]*$/.test(value) || value.length > 19 || BigInt(value) > MAX_QUOTA) {
    return "Ingresá un entero en bytes, entre 1 y 9,223,372,036,854,775,807, sin separadores, espacios ni ceros iniciales.";
  }
  return null;
}

const MAX_POSITIONS = 50;
const WHOLE = /^[0-9]+$/;
const GAME_WARNING = "Cambiar las reglas del juego afecta las simulaciones futuras; las guardadas conservan las suyas.";

interface GameDraft { name: string; numbers: string; positions: string; prizes: string[]; repeats: boolean; stake: string }
interface GameErrors { name?: string; numbers?: string; positions?: string; prizes: (string | undefined)[]; stake?: string }

function toDraft(game: GameSettings): GameDraft {
  return {
    name: game.name, numbers: String(game.numbers), positions: String(game.positions),
    prizes: game.prizes.map(String), repeats: game.allows_repeats, stake: String(game.minimum_stake),
  };
}
// Mirrors the backend make_game() rules so the form never sends what the server would reject.
function validateGame(draft: GameDraft): GameErrors {
  const errors: GameErrors = { prizes: [] };
  const numbers = WHOLE.test(draft.numbers) ? Number(draft.numbers) : NaN;
  const positions = WHOLE.test(draft.positions) ? Number(draft.positions) : NaN;
  if (draft.name.trim().length === 0 || draft.name.trim().length > 80) errors.name = "Escribí un nombre de hasta 80 caracteres.";
  if (!(numbers >= 2)) errors.numbers = "Tiene que haber al menos 2 números posibles.";
  if (!(positions >= 1)) errors.positions = "Tiene que haber al menos 1 posición.";
  else if (positions > MAX_POSITIONS) errors.positions = `Se pueden editar hasta ${MAX_POSITIONS} posiciones.`;
  else if (!draft.repeats && numbers >= 2 && positions > numbers) {
    errors.positions = "Sin repeticiones, las posiciones no pueden superar a los números posibles.";
  }
  draft.prizes.forEach((prize, index) => {
    errors.prizes[index] = WHOLE.test(prize) && Number(prize) >= 1 ? undefined : "Mínimo 1.";
  });
  if (!WHOLE.test(draft.stake) || Number(draft.stake) < 1) errors.stake = "La apuesta mínima es de al menos RD$1.";
  return errors;
}
const hasGameErrors = (errors: GameErrors) =>
  !!(errors.name || errors.numbers || errors.positions || errors.stake || errors.prizes.some(Boolean));

function GameRulesSection({ onSource, onSummary, onValidity, onLoadState, onRetry, onOutcome, retry }: { onSource: (source: GameSettingsSource) => void; onSummary: (draft: GameDraft) => void; onValidity: (valid: boolean) => void; onLoadState: (state: "loading" | "ready" | "error") => void; onRetry: () => void; onOutcome: (message: string) => void; retry: number }) {
  const [draft, setDraft] = useState<GameDraft | null>(null);
  const [loadError, setLoadError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const busyRef = useRef(false);

  useEffect(() => {
    let live = true;
    onLoadState("loading");
    setLoadError("");
    apiClient.getGameSettings().then((value) => {
      if (!live) return;
      const next = toDraft(value);
      setDraft(next); onSummary(next); onValidity(!hasGameErrors(validateGame(next))); onSource(value.source); onLoadState("ready");
    }).catch(() => { if (live) { setLoadError("No se pudieron cargar las reglas del juego."); onLoadState("error"); } });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onLoadState, retry]);

  function edit(change: Partial<GameDraft>) {
    setDraft((current) => {
      if (!current) return current;
      const next = { ...current, ...change };
      onSummary(next); onValidity(!hasGameErrors(validateGame(next)));
      return next;
    });
    setSaved(false); setSaveError(""); onOutcome("");
  }
  function changePositions(value: string) {
    const count = WHOLE.test(value) ? Number(value) : NaN;
    const next: Partial<GameDraft> = { positions: value };
    if (count >= 1 && count <= MAX_POSITIONS && draft) {
      next.prizes = Array.from({ length: count }, (_, index) => draft.prizes[index] ?? "1");
    }
    edit(next);
  }
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft || busyRef.current || hasGameErrors(validateGame(draft))) return;
    busyRef.current = true; setSaving(true); setSaveError(""); setSaved(false);
    try {
      const value = await apiClient.saveGameSettings({
        name: draft.name.trim(), numbers: Number(draft.numbers), positions: Number(draft.positions),
        prizes: draft.prizes.map(Number), allows_repeats: draft.repeats, minimum_stake: Number(draft.stake),
      });
      setDraft(toDraft(value)); onSource(value.source); setSaved(true); onOutcome("Reglas guardadas. Se usarán en las próximas simulaciones.");
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 422) { setSaveError(failure.detail); onOutcome("No se guardaron las reglas. Revisá los datos y reintentá."); }
      else if (failure instanceof NetworkError) { setSaveError("Sin respuesta del servidor. Revisá la conexión y reintentá."); onOutcome("No se guardaron las reglas. Revisá la conexión y reintentá."); }
      else { setSaveError("No se pudieron guardar las reglas. Tus cambios siguen en el formulario; reintentá."); onOutcome("No se guardaron las reglas. Tus cambios siguen disponibles para reintentar."); }
    } finally { busyRef.current = false; setSaving(false); }
  }

  const errors = draft ? validateGame(draft) : null;
  return <section aria-labelledby="game-rules-heading" className="mt-4">
    <h2 id="game-rules-heading" className="section-header">Reglas del sorteo</h2>
    <p className="field-help mb-4">Elegí cómo funciona el sorteo. Estos cambios se aplican a las simulaciones nuevas.</p>
    {loadError && <div role="alert" className="mb-4 text-sm text-red-300"><p>{loadError} La cuota y los detalles avanzados siguen disponibles; las reglas no se modificarán.</p><button type="button" className="btn btn-tertiary mt-2" onClick={onRetry}>Reintentar reglas</button></div>}
    {draft && errors && <form id="game-rules-form" onSubmit={(event) => { void save(event); }} noValidate className="max-w-xl space-y-4">
      <div>
        <label htmlFor="game-name" className="field-label">Nombre</label>
        <input id="game-name" type="text" autoComplete="off" className="control" value={draft.name} disabled={saving} aria-invalid={!!errors.name} aria-describedby={errors.name ? "game-name-error" : "game-name-help"} onChange={(event) => edit({ name: event.target.value })} />
        <p id="game-name-help" className="field-help">Este nombre identifica las reglas en las simulaciones nuevas.</p>
        {errors.name && <p id="game-name-error" className="mt-2 text-sm text-red-300">{errors.name}</p>}
      </div>
      <div>
        <label htmlFor="game-numbers" className="field-label">Números posibles</label>
        <input id="game-numbers" type="text" inputMode="numeric" autoComplete="off" className="control tabular-nums" value={draft.numbers} disabled={saving} aria-invalid={!!errors.numbers} aria-describedby={errors.numbers ? "game-numbers-error" : "game-numbers-help"} onChange={(event) => edit({ numbers: event.target.value })} />
        <p id="game-numbers-help" className="field-help">Cuántos números distintos puede elegir el sorteo; se necesitan al menos 2.</p>
        {errors.numbers && <p id="game-numbers-error" className="mt-2 text-sm text-red-300">{errors.numbers}</p>}
      </div>
      <div>
        <label htmlFor="game-positions" className="field-label">Posiciones por sorteo</label>
        <input id="game-positions" type="text" inputMode="numeric" autoComplete="off" className="control tabular-nums" value={draft.positions} disabled={saving} aria-invalid={!!errors.positions} aria-describedby={errors.positions ? "game-positions-error" : "game-positions-help"} onChange={(event) => changePositions(event.target.value)} />
        <p id="game-positions-help" className="field-help">Cuántos resultados se ordenan en cada sorteo; se pueden editar hasta {MAX_POSITIONS}.</p>
        {errors.positions && <p id="game-positions-error" className="mt-2 text-sm text-red-300">{errors.positions}</p>}
      </div>
      <fieldset>
        <legend className="field-label">Premios por posición</legend>
        <p className="field-help">Cuánto paga cada RD$1 apostado a esa posición.</p>
        <div className="mt-2 space-y-2">
          {draft.prizes.map((prize, index) => {
            const error = errors.prizes[index];
            return <div key={index}>
              <label htmlFor={`game-prize-${index}`} className="text-sm text-text-secondary">Posición {index + 1}</label>
              <input id={`game-prize-${index}`} type="text" inputMode="numeric" autoComplete="off" className="control tabular-nums" value={prize} disabled={saving} aria-invalid={!!error} aria-describedby={error ? `game-prize-${index}-error` : `game-prize-${index}-help`} onChange={(event) => edit({ prizes: draft.prizes.map((current, at) => (at === index ? event.target.value : current)) })} />
              {error ? <p id={`game-prize-${index}-error`} className="mt-1 text-sm text-red-300">{error}</p>
                : <p className="mt-1 text-sm text-text-secondary">Paga {formatDOP(Number(prize))} por cada RD$1.</p>}
            </div>;
          })}
        </div>
      </fieldset>
      <div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.repeats} disabled={saving} onChange={(event) => edit({ repeats: event.target.checked })} />Repeticiones permitidas</label>
        <p className="field-help">Si se permiten, el mismo número puede salir en varias posiciones.</p>
      </div>
      <div>
        <label htmlFor="game-stake" className="field-label">Apuesta mínima por número</label>
        <input id="game-stake" type="text" inputMode="numeric" autoComplete="off" className="control tabular-nums" value={draft.stake} disabled={saving} aria-invalid={!!errors.stake} aria-describedby={errors.stake ? "game-stake-error" : "game-stake-help"} onChange={(event) => edit({ stake: event.target.value })} />
        {errors.stake ? <p id="game-stake-error" className="mt-2 text-sm text-red-300">{errors.stake}</p>
          : <p id="game-stake-help" className="field-help">Mínimo actual: {formatDOP(Number(draft.stake))}.</p>}
      </div>
      <p className="border border-border-control bg-field p-3 text-sm">{GAME_WARNING}</p>
      {saveError && <p role="alert" className="text-sm text-red-300">{saveError}</p>}
      {saved && <p role="status" className="text-sm text-accent">Reglas guardadas. Se usarán en las próximas simulaciones.</p>}
      <button type="submit" className="btn btn-secondary" disabled={saving || hasGameErrors(errors)}>{saving ? "Guardando reglas…" : "Guardar reglas"}</button>
    </form>}
  </section>;
}

export function SettingsPage() {
  const [view, setView] = useState<SettingsView | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saved, setSaved] = useState(false);
  const [wizardOutcome, setWizardOutcome] = useState("");
  const [saving, setSaving] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [gameSource, setGameSource] = useState<GameSettingsSource | null>(null);
  const [searchParams] = useSearchParams();
  const [step, setStep] = useState(() => {
    switch (searchParams.get("paso")) {
      case "reglas": return 0;
      case "cuota": return 1;
      case "detalles": return 2;
      case "revisar": return 3;
      default: return 0;
    }
  });
  const [gameSummary, setGameSummary] = useState<GameDraft | null>(null);
  const [gameValid, setGameValid] = useState(false);
  const [gameRulesState, setGameRulesState] = useState<"loading" | "ready" | "error">("loading");
  const [gameRulesRetry, setGameRulesRetry] = useState(0);
  const [agentCredential, setAgentCredential] = useState<string | null>(null);
  const [agentCredentialVisible, setAgentCredentialVisible] = useState(false);
  const [agentCredentialLoading, setAgentCredentialLoading] = useState(false);
  const [agentCredentialCopying, setAgentCredentialCopying] = useState(false);
  const [agentCredentialError, setAgentCredentialError] = useState("");
  const [agentCredentialCopied, setAgentCredentialCopied] = useState(false);
  const [manualCopyFallback, setManualCopyFallback] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const agentCredentialInputRef = useRef<HTMLInputElement>(null);
  const agentCredentialTriggerRef = useRef<HTMLButtonElement>(null);
  const restoreAgentCredentialFocusRef = useRef(false);
  const dirtyRef = useRef(false);
  const saveRef = useRef(false);
  const requestRef = useRef(0);
  const agentCredentialSequenceRef = useRef(0);
  const agentCredentialBusyRef = useRef(false);
  const agentCredentialCopyBusyRef = useRef(false);
  const dirty = !!view && draft !== null && draft !== view.quota.effective_bytes;
  // Current servers report the aggregate. Older captured responses may only
  // report historical experiment bytes; make that incomplete fallback visible.
  const hasAdmission = typeof view?.storage.admission_logical_bytes_exact === "string";
  const used = view ? BigInt(hasAdmission ? view.storage.admission_logical_bytes_exact : view.storage.logical_used_bytes_exact) : 0n;
  const limit = view ? BigInt(view.quota.effective_bytes) : 0n;
  const remaining = limit > used ? limit - used : 0n;
  const quotaValid = !!view && (!view.quota.writable || (draft !== null && !validate(draft) && BigInt(draft) >= used));
  // The conversion is of a bounded 0..100 integer, never of byte counts.
  const progress = limit > 0n ? Number((used < limit ? used : limit) * 100n / limit) : 0;
  dirtyRef.current = dirty;
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    dirty && currentLocation.pathname !== nextLocation.pathname);

  useEffect(() => { if (fieldError && !saving) inputRef.current?.focus(); }, [fieldError, saving]);

  useEffect(() => {
    if (!dirty) return;
    function warnBeforeUnload(event: BeforeUnloadEvent) { event.preventDefault(); event.returnValue = ""; }
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [dirty]);

  useEffect(() => {
    let live = true;
    const sequence = ++requestRef.current;
    if (!view) setLoading(true);
    setLoadError("");
    apiClient.getSettings().then((value) => {
      if (!live || sequence !== requestRef.current) return;
      setView(value);
      if (!dirtyRef.current) setDraft(value.quota.effective_bytes);
      setLoadError(""); setLoading(false);
    }).catch((error: unknown) => {
      if (!live || sequence !== requestRef.current) return;
      setLoadError(error instanceof NetworkError
        ? "No se pudo contactar al servidor."
        : "No se pudieron cargar los ajustes.");
      setLoading(false);
    });
    return () => { live = false; };
    // Refresh is explicit; a draft never triggers a new GET.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh]);

  useEffect(() => () => {
    agentCredentialSequenceRef.current += 1;
    agentCredentialBusyRef.current = false;
    agentCredentialCopyBusyRef.current = false;
  }, []);

  useEffect(() => {
    if (!manualCopyFallback || !agentCredential || !agentCredentialVisible) return;
    agentCredentialInputRef.current?.focus();
    agentCredentialInputRef.current?.select();
  }, [agentCredential, agentCredentialVisible, manualCopyFallback]);

  useEffect(() => {
    if (!restoreAgentCredentialFocusRef.current || agentCredential || agentCredentialLoading) return;
    const trigger = agentCredentialTriggerRef.current;
    if (!trigger) return;
    restoreAgentCredentialFocusRef.current = false;
    trigger.focus();
  }, [agentCredential, agentCredentialLoading]);

  async function retrieveAgentCredential() {
    if (agentCredentialBusyRef.current) return;
    const sequence = ++agentCredentialSequenceRef.current;
    agentCredentialBusyRef.current = true;
    setAgentCredentialLoading(true);
    setAgentCredentialError("");
    setAgentCredentialCopied(false);
    setManualCopyFallback(false);
    try {
      const response = await apiClient.getAgentCredential();
      if (sequence !== agentCredentialSequenceRef.current) return;
      if (typeof response?.token !== "string" || response.token.length === 0) {
        throw new Error("invalid credential response");
      }
      setAgentCredential(response.token);
      setAgentCredentialVisible(false);
    } catch (failure) {
      if (sequence !== agentCredentialSequenceRef.current) return;
      if (failure instanceof NetworkError) {
        setAgentCredentialError("No se pudo contactar al servidor. Reintentá.");
      } else if (failure instanceof ApiError && failure.status === 403) {
        setAgentCredentialError("El servidor rechazó el origen. Abrí la aplicación desde la dirección local del servidor.");
      } else if (failure instanceof ApiError && failure.status === 401) {
        setAgentCredentialError("El servidor rechazó la solicitud. Reintentá.");
      } else {
        setAgentCredentialError("No se pudo consultar la credencial. Reintentá.");
      }
    } finally {
      if (sequence === agentCredentialSequenceRef.current) {
        agentCredentialBusyRef.current = false;
        setAgentCredentialLoading(false);
      }
    }
  }

  function hideAgentCredential() {
    restoreAgentCredentialFocusRef.current = true;
    agentCredentialSequenceRef.current += 1;
    agentCredentialBusyRef.current = false;
    agentCredentialCopyBusyRef.current = false;
    setAgentCredential(null);
    setAgentCredentialVisible(false);
    setAgentCredentialLoading(false);
    setAgentCredentialCopying(false);
    setAgentCredentialError("");
    setAgentCredentialCopied(false);
    setManualCopyFallback(false);
  }

  async function copyAgentCredential() {
    if (!agentCredential || agentCredentialCopyBusyRef.current) return;
    const sequence = agentCredentialSequenceRef.current;
    agentCredentialCopyBusyRef.current = true;
    setAgentCredentialCopying(true);
    setAgentCredentialCopied(false);
    setAgentCredentialError("");
    setManualCopyFallback(false);
    try {
      const clipboard = navigator.clipboard;
      if (typeof clipboard?.writeText !== "function") throw new Error("clipboard unavailable");
      await clipboard.writeText(agentCredential);
      if (sequence !== agentCredentialSequenceRef.current) return;
      setAgentCredentialCopied(true);
    } catch {
      if (sequence !== agentCredentialSequenceRef.current) return;
      setAgentCredentialVisible(true);
      setManualCopyFallback(true);
      setAgentCredentialError("No se pudo copiar. Seleccioná y copiá el texto mostrado manualmente.");
    } finally {
      if (sequence === agentCredentialSequenceRef.current) {
        agentCredentialCopyBusyRef.current = false;
        setAgentCredentialCopying(false);
      }
    }
  }

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!view?.quota.writable || draft === null || saveRef.current) return;
    const error = validate(draft) ?? (BigInt(draft) < used
      ? `El límite no puede ser menor que el uso actual (${bytes(used.toString())}).`
      : null);
    setFieldError(error ?? ""); setSaveError(""); setSaved(false);
    if (error) { inputRef.current?.focus(); return; }
    saveRef.current = true; setSaving(true);
    const sequence = ++requestRef.current;
    let refreshAfterFailure = false;
    try {
      const value = await apiClient.updateSettings(draft);
      // A reload may have started while the PUT was pending. Its snapshot can be
      // older than the successful write, so invalidate it and trust the PUT view.
      if (sequence !== requestRef.current) requestRef.current += 1;
      setLoadError("");
      setView(value);
      setDraft(value.quota.effective_bytes); // PUT returns the full authoritative view.
      dirtyRef.current = false;
      setSaved(true); setWizardOutcome("Ajustes guardados. Se aplicarán a las simulaciones nuevas.");
    } catch (failure) {
      if (sequence !== requestRef.current) {
        requestRef.current += 1;
        refreshAfterFailure = true;
      }
      if (failure instanceof ApiError && failure.status === 422 && failure.fieldErrors?.some((entry) =>
        entry.loc.map(String).join(".") === "body.quota_bytes")) {
        setFieldError("El servidor rechazó el límite. Revisá el valor.");
      } else if (failure instanceof ApiError && failure.status === 409) {
        setSaveError(failure.detail === "environment quota is read-only"
          ? "El entorno fija el límite y no se puede cambiar desde la web. Actualizá el estado."
          : "El límite no puede ser menor que el uso actual. Actualizá el estado e ingresá un valor mayor.");
      } else if (failure instanceof NetworkError) {
        setSaveError("Sin respuesta del servidor. Puede que se haya guardado; actualizá el estado antes de reintentar.");
      } else if (failure instanceof ApiError && failure.status === 403) {
        setSaveError("El servidor rechazó el origen. Abrí la aplicación desde la dirección local del servidor.");
      } else {
        setSaveError("No se pudo guardar el límite. Tus cambios siguen en el campo; reintentá.");
      }
      setWizardOutcome("No se guardó el límite. Tus cambios siguen disponibles para reintentar.");
    } finally {
      saveRef.current = false;
      setSaving(false);
      if (refreshAfterFailure) setRefresh((previous) => previous + 1);
    }
  }

  const gameSourceName = gameSource === "stored" ? "Guardadas desde la web" : gameSource === "environment" ? "Variables de entorno LABORATORIO_GAME_*" : gameSource === "default" ? "Predeterminadas (Quiniela 80)" : "Sin leer";
  const sourceName = view?.quota.source === "environment" ? "Variable de entorno" : view?.quota.source === "persisted" ? "Preferencia guardada" : "Por defecto";
  const reviewQuota = draft && !validate(draft) ? draft : view?.quota.effective_bytes ?? "0";
  const stepTitles = ["1 · ¿Qué reglas tendrá el sorteo?", "2 · ¿Cuánto espacio puede usar?", "3 · ¿Necesitás revisar detalles técnicos?", "4 · Revisá y guardá"];
  return <div className="max-w-5xl space-y-8">
    {loading && <Loading rows={3} label="Cargando ajustes…" className="border-y border-border py-5" />}
    {loadError && <ErrorBanner cause={loadError} recovery={view ? "Se muestra la última lectura; reintentá para actualizarla." : "Comprobá que el laboratorio siga abierto y reintentá."} preserved={!!view} actionLabel="Reintentar" onAction={() => setRefresh((previous) => previous + 1)} />}
    {wizardOutcome && step === 3 && <div role={wizardOutcome.startsWith("No se") ? "alert" : "status"} className="m3-review mb-4"><p className="font-medium">{wizardOutcome}</p>{!wizardOutcome.startsWith("No se") && <Link className="btn btn-tertiary mt-3" to="/simulaciones/nueva">Crear una simulación</Link>}</div>}
    {view && <>
      <section className="m3-wizard" aria-label="Asistente de ajustes">
        <div className="m3-wizard-progress" data-step={step + 1} role="progressbar" aria-label={`Paso ${step + 1} de 4`} aria-valuenow={step + 1} aria-valuemin={1} aria-valuemax={4}>
          <span />
        </div>
        <p className="m3-wizard-step">Paso {step + 1} de 4</p>
        <h2 className="m3-wizard-title">{stepTitles[step]}</h2>
        <p className="field-help">Guardar ajustes aplica las reglas del sorteo y el límite de almacenamiento a las simulaciones nuevas.</p>
        <div className="m3-wizard-actions">
          <button type="button" className="btn btn-outlined" disabled={step === 0} onClick={() => setStep((current) => Math.max(0, current - 1))}>Atrás</button>
          {step < 3 ? <button type="button" className="btn btn-primary" disabled={(step === 0 && gameRulesState === "ready" && !gameValid) || (step === 1 && !quotaValid)} onClick={() => setStep((current) => Math.min(3, current + 1))}>Siguiente</button>
            : <button type="button" className="btn btn-primary" disabled={(gameRulesState === "ready" && !gameValid) || !quotaValid || saving} onClick={() => {
              (document.getElementById("game-rules-form") as HTMLFormElement | null)?.requestSubmit();
              (document.getElementById("quota-form") as HTMLFormElement | null)?.requestSubmit();
            }}>{saving ? "Guardando…" : "Guardar ajustes"}</button>}
        </div>
      </section>
      <div hidden={step !== 0}>
        <GameRulesSection onSource={setGameSource} onSummary={(summary) => { setGameSummary(summary); setWizardOutcome(""); }} onValidity={setGameValid} onLoadState={setGameRulesState} onRetry={() => setGameRulesRetry((value) => value + 1)} onOutcome={setWizardOutcome} retry={gameRulesRetry} />
      </div>
      <div hidden={step !== 1}>
      <div className="flex justify-end">
        <button type="button" className="btn btn-secondary disabled:cursor-not-allowed" onClick={() => setRefresh((previous) => previous + 1)}>Actualizar estado</button>
      </div>
      <section aria-labelledby="storage-heading" className="border-t border-border pt-5">
        <h2 id="storage-heading" className="section-header">Presupuesto y cuota</h2>
        <p className="field-help mb-4">El límite de almacenamiento controla cuánto historial y resultados puede conservar el laboratorio; no es dinero para apostar.</p>
        <p className="field-help">{view.quota.writable ? `Límite actual: ${sourceName}.` : "El límite lo fija el servidor y no se puede cambiar aquí."}</p>
        <div className="metric-grid">
          <div className={metric}><h3 className="field-label">Límite de almacenamiento</h3><p className="metric-value">{readableCapacity(view.quota.effective_bytes)}</p></div>
          <div className={metric}><h3 className="field-label">Usado</h3><p className="metric-value">{readableCapacity(used.toString())}</p></div>
          {hasAdmission && <div className={metric}><h3 className="field-label">Disponible</h3><p className="metric-value"><span className="tabular-nums">{readableCapacity(remaining.toString())}</span></p></div>}
        </div>
        {hasAdmission
          ? <progress className="mt-4 w-full accent-accent" aria-label="Cuota lógica utilizada" value={progress} max={100} />
          : <p className="mt-4 text-sm text-text-secondary">Uso incompleto: este servidor no informa el total.</p>}
        {hasAdmission && used > limit && <p className="mt-2 text-sm text-text-secondary">Uso superior al límite por {bytes((used - limit).toString())}.</p>}
        <p className="mt-3 text-sm text-text-secondary">El límite de almacenamiento no es el espacio libre en disco.</p>
        {view.storage.warning && <p role="alert" className="mt-4 border border-border-control bg-field p-3 text-sm">El servidor avisa: cerca del límite o falta de disco.</p>}
      </section>
      <section aria-labelledby="quota-form-heading" className="border-t border-border pt-5">
        <h2 id="quota-form-heading" className="section-header">Cambiar límite</h2>
        {view.quota.writable ? <form id="quota-form" onSubmit={(event) => { void save(event); }} noValidate className="max-w-xl">
          <label htmlFor="quota-bytes" className="field-label">Nuevo límite de almacenamiento (en bytes)</label>
          <input ref={inputRef} id="quota-bytes" type="text" inputMode="numeric" autoComplete="off" spellCheck={false} value={draft ?? ""} disabled={saving} aria-invalid={!!fieldError} aria-describedby={fieldError ? "quota-help quota-error" : "quota-help"} onChange={(event) => { setDraft(event.target.value); setFieldError(""); setSaveError(""); setSaved(false); setWizardOutcome(""); }} className="control font-mono tabular-nums" />
          <p id="quota-help" className="field-help">Ingresá un entero positivo con cuántos bytes puede ocupar el almacenamiento; no es dinero. Escribí solo números, sin separadores. Por ejemplo, 5 GiB son 5,368,709,120 bytes. Mínimo actual: {readableCapacity(used.toString())} ({bytes(used.toString())}).</p>
          {fieldError && <p id="quota-error" className="mt-2 text-sm text-red-300">{fieldError}</p>}
          {saveError && <p role="alert" className="mt-2 text-sm text-red-300">{saveError}</p>}
          {saved && <p role="status" className="mt-2 text-sm text-accent">Guardado.</p>}
          <button type="submit" className="sr-only" disabled={saving}>{saving ? "Guardando…" : "Guardar límite"}</button>
        </form> : <div className="max-w-prose text-text-secondary"><p>El entorno del servidor fija el límite; aquí es de solo lectura.</p>{dirty && <p className="mt-2 break-words">Borrador no guardado: <span className="font-mono">{draft}</span> bytes. No se envió.</p>}</div>}
      </section>
      </div>
      <div hidden={step !== 2}>
      <h2 className="section-header">Detalles avanzados</h2>
      <details className="border-y border-border py-3"><summary className="disclosure-summary">Detalles técnicos</summary>
        <div className="mt-4 space-y-6 text-sm">
          <dl className="metric-grid">
            <div className={metric}><dt>Origen del límite</dt><dd>{sourceName}</dd></div>
            <div className={metric}><dt>Límite efectivo en bytes</dt><dd className="break-words font-mono tabular-nums">{bytes(view.quota.effective_bytes)}</dd></div>
            <div className={metric}><dt>Preferencia persistida</dt><dd className="break-words font-mono tabular-nums">{view.quota.persisted_bytes === null ? "ninguna" : bytes(view.quota.persisted_bytes)}</dd></div>
            {hasAdmission && <>
              <div className={metric}><dt>Disponible en bytes</dt><dd className="break-words font-mono tabular-nums">{bytes(remaining.toString())}</dd></div>
              <div className={metric}><dt>Uso agregado en bytes</dt><dd className="break-words font-mono tabular-nums">{bytes(view.storage.admission_logical_bytes_exact!)}</dd></div>
              <div className={metric}><dt>Experimentos y ejecuciones históricos</dt><dd className="break-words font-mono tabular-nums">{bytes(view.storage.logical_used_bytes_exact)}</dd></div>
              <div className={metric}><dt>Artefactos de perfiles (copias JSON)</dt><dd className="break-words font-mono tabular-nums">{bytes(view.storage.profile_artifact_bytes_exact)}</dd></div>
              <div className={metric}><dt>Artefactos de datasets</dt><dd className="break-words font-mono tabular-nums">{bytes(view.storage.dataset_artifact_bytes_exact)}</dd></div>
            </>}
          </dl>
          <section aria-labelledby="physical-heading">
            <h3 id="physical-heading" className="field-label">Archivos físicos y disco</h3>
            <dl className="metric-grid">
              <div className={metric}><dt>SQLite y archivos locales (total informado)</dt><dd className="break-words font-mono">{measured(view.storage.sqlite_bytes)}</dd></div>
              <div className={metric}><dt>Espacio en disco libre</dt><dd className="break-words font-mono">{measured(view.storage.free_disk_bytes)}</dd></div>
              <div className={metric}><dt>Base SQLite</dt><dd className="break-words font-mono">{measured(view.storage.database_bytes)}</dd></div>
              <div className={metric}><dt>WAL</dt><dd className="break-words font-mono">{measured(view.storage.wal_bytes)}</dd></div>
              <div className={metric}><dt>SHM</dt><dd className="break-words font-mono">{measured(view.storage.shm_bytes)}</dd></div>
              <div className={metric}><dt>Temporales locales</dt><dd className="break-words font-mono">{measured(view.storage.temp_bytes)}</dd></div>
            </dl>
          </section>
          <section aria-labelledby="game-source-heading">
            <h3 id="game-source-heading" className="field-label">Origen de las reglas del juego</h3>
            <p>{gameSourceName}</p>
          </section>
          <section aria-labelledby="sources-heading">
            <h3 id="sources-heading" className="field-label">Datos de origen</h3>
            <dl className="space-y-3">
              <div><dt className="text-text-secondary">Historial · identificador</dt><dd className="break-all font-mono">{view.sources.history_id}</dd></div>
              <div><dt className="text-text-secondary">Historial · SHA-256</dt><dd className="break-all font-mono">{view.sources.history_sha256}</dd></div>
              <div><dt className="text-text-secondary">Rankings · identificador</dt><dd className="break-all font-mono">{view.sources.rankings_id}</dd></div>
              <div><dt className="text-text-secondary">Rankings · SHA-256</dt><dd className="break-all font-mono">{view.sources.rankings_sha256}</dd></div>
              <div><dt className="text-text-secondary">Versión de código</dt><dd className="break-all font-mono">{view.sources.code_version}</dd></div>
            </dl>
          </section>
          <section aria-labelledby="connection-heading">
            <h3 id="connection-heading" className="field-label">Conexión local</h3>
            <dl className="metric-grid">
              <div className={metric}><dt>Servidor</dt><dd className="font-mono">{view.connection.host}:{view.connection.port}</dd></div>
              <div className={metric}><dt>Versión</dt><dd className="font-mono">{view.connection.version}</dd></div>
            </dl>
            <p className="mt-3 text-text-secondary">Iniciar: <code>iniciar-laboratorio.bat</code>. Detener: Ctrl+C en su consola.</p>
          </section>
        </div>
      </details>
      <details className="border-y border-border py-3">
        <summary id="agent-access-heading" className="disclosure-summary">Acceso para agentes</summary>
        <p className="mt-3 max-w-prose text-sm text-text-secondary">No compartas esta credencial de acceso a la API.</p>
        {!agentCredential && !agentCredentialLoading && <button ref={agentCredentialTriggerRef} type="button" className={`${action} mt-4`} onClick={() => { void retrieveAgentCredential(); }}>
          {agentCredentialError ? "Reintentar consulta" : "Consultar credencial de agente"}
        </button>}
        {agentCredentialLoading && <div className="mt-4 flex flex-wrap items-center gap-3">
          <button type="button" className={action} disabled>Consultando credencial…</button>
          <button type="button" className={action} onClick={hideAgentCredential}>Cancelar</button>
        </div>}
        {agentCredentialError && <p role="alert" className="mt-3 max-w-prose text-sm text-red-300">{agentCredentialError}</p>}
        {agentCredential && <div className="mt-4 max-w-2xl">
          <label htmlFor="agent-credential" className="field-label">Credencial de agente</label>
          <input
            ref={agentCredentialInputRef}
            id="agent-credential"
            type={agentCredentialVisible ? "text" : "password"}
            className="control mt-2 w-full font-mono"
            value={agentCredential}
            readOnly
            autoComplete="off"
            spellCheck={false}
            aria-describedby="agent-credential-help"
          />
          <p id="agent-credential-help" className="field-help mt-2">Ocultarla la borra de la pantalla.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className={action} onClick={() => { setAgentCredentialVisible((value) => !value); setManualCopyFallback(false); }}>
              {agentCredentialVisible ? "Ocultar credencial" : "Mostrar credencial"}
            </button>
            <button type="button" className={action} disabled={agentCredentialCopying} onClick={() => { void copyAgentCredential(); }}>
              {agentCredentialCopying ? "Copiando…" : "Copiar credencial"}
            </button>
            <button type="button" className={action} onClick={hideAgentCredential}>Ocultar y borrar credencial</button>
          </div>
          {agentCredentialCopied && <p role="status" className="mt-3 text-sm text-accent">Credencial copiada al portapapeles.</p>}
        </div>}
      </details>
      </div>
      <section hidden={step !== 3} aria-labelledby="review-heading" className="m3-review">
        <h2 id="review-heading">Revisá tus ajustes</h2>
        <p>Antes de guardar, confirmá estos valores. Se usarán en simulaciones nuevas.</p>
        {gameSummary && <dl className="m3-review-list">
          <div><dt>Sorteo</dt><dd>{gameSummary.name}</dd></div>
          <div><dt>Números posibles</dt><dd>{gameSummary.numbers}</dd></div>
          <div><dt>Posiciones y premios</dt><dd>{gameSummary.positions}: {gameSummary.prizes.map((prize, index) => `posición ${index + 1}, ${formatDOP(Number(prize))}`).join("; ")}</dd></div>
          <div><dt>Repeticiones</dt><dd>{gameSummary.repeats ? "Permitidas" : "No permitidas"}</dd></div>
          <div><dt>Apuesta mínima por número</dt><dd>{formatDOP(Number(gameSummary.stake))}</dd></div>
        </dl>}
        <dl className="m3-review-list"><div><dt>Límite de almacenamiento</dt><dd>{readableCapacity(reviewQuota)} ({bytes(reviewQuota)})</dd></div><div><dt>Uso actual</dt><dd>{readableCapacity(used.toString())} ({bytes(used.toString())})</dd></div></dl>
        <button type="button" className="btn btn-outlined mt-3" onClick={() => setStep(1)}>Editar cuota</button>
        {gameRulesState === "error" && <p role="status" className="mt-3 text-sm text-text-secondary">Las reglas no pudieron verificarse. Podés guardar la cuota y volver a intentar cargarlas después.</p>}
        <p className="field-help">Cambiar las reglas afecta simulaciones futuras; las ya guardadas conservan sus reglas. Esto simula resultados históricos: no predice sorteos ni garantiza ganancias.</p>
      </section>
    </>}
    <ConfirmDialog open={blocker.state === "blocked"} title="¿Salir sin guardar?" description="Perderás el límite sin guardar." confirmLabel="Salir sin guardar" cancelLabel="Seguir editando" onCancel={() => blocker.reset?.()} onConfirm={() => blocker.proceed?.()} />
  </div>;
}
