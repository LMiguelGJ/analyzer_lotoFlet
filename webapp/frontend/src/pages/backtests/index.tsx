import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { BacktestReport as BacktestReportData, Catalog, GameSettings } from "../../api/types";
import { BacktestReport } from "../../components/BacktestReport";
import { ErrorBanner, Loading } from "../../components/ui";
import { backtestScenarioName, buildBacktestBody, stakingDescriptions, validateBacktestDraft, type BacktestDraft } from "./backtest-model";

const PAGE_SIZE = 20;
const SYSTEMS = [
  ["transition", "Transición", "Ordena números según cambios observados entre sorteos anteriores."],
  ["cold", "Fríos", "Da prioridad a números que llevan más tiempo sin aparecer."],
  ["select_interpretable", "Selector automático", "Elige un método de ranking interpretable con datos anteriores."],
  ["mix", "Mezclas", "Combina señales de varios métodos de ranking."],
  ["ensemble", "Ensemble", "Reúne varios métodos de ranking en una selección."],
] as const;
const INITIAL_DRAFT: BacktestDraft = {
  name: "", system: "transition", parity: false, coverage: "1", staking: "flat",
  numbers: "", positions: "", prizes: [], minStake: "", capital: "2000", goal: "2800",
};
const CAVEAT = "Simula con datos históricos: no predice resultados futuros ni garantiza rentabilidad.";

export function ExperimentTabs({ active }: { active: "simulations" | "backtests" }) {
  return <nav className="experiment-view-tabs" aria-label="Simulaciones">
    <Link className={active === "simulations" ? "is-active" : ""} aria-current={active === "simulations" ? "page" : undefined} to="/simulaciones">Simulaciones</Link>
    <Link className={active === "backtests" ? "is-active" : ""} aria-current={active === "backtests" ? "page" : undefined} to="/simulaciones/historicas">Corridas históricas</Link>
  </nav>;
}

function errorMessage(error: unknown, action: string) {
  if (error instanceof NetworkError) return `No se pudo contactar al servidor para ${action}. Iniciá el laboratorio y reintentá.`;
  if (error instanceof ApiError && error.status === 409) return "Cambió el historial o los rankings disponibles. Actualizá la página antes de crear otra corrida.";
  if (error instanceof ApiError && error.status === 422) return `El servidor no aceptó la configuración: ${error.detail}`;
  return `No se pudo ${action}. Tus campos siguen disponibles; reintentá.`;
}

function sourceInputs(catalog: Catalog | null) {
  const sources = catalog?.sources;
  return sources?.history_sha256 && sources.rankings_sha256
    ? { history_sha256: sources.history_sha256, rankings_sha256: sources.rankings_sha256 }
    : null;
}

export function BacktestsPage() {
  const [items, setItems] = useState<BacktestReportData[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const sequence = useRef(0);
  useEffect(() => {
    let live = true;
    const ticket = ++sequence.current;
    setState("loading"); setError("");
    apiClient.listBacktests(offset, PAGE_SIZE).then((page) => {
      if (!live || ticket !== sequence.current) return;
      setItems(page.items); setTotal(page.total); setState("ready");
    }).catch((cause: unknown) => {
      if (!live || ticket !== sequence.current) return;
      setError(errorMessage(cause, "cargar las corridas históricas")); setState("error");
    });
    return () => { live = false; sequence.current++; };
  }, [offset, retry]);
  const retryLoad = () => setRetry((value) => value + 1);
  return <div className="backtests-page max-w-6xl space-y-5">
    <ExperimentTabs active="backtests" />
    <header className="space-y-2"><h2>Corridas históricas</h2><p className="max-w-prose">Reproduce una estrategia en el historial disponible, reiniciando el capital al cerrar cada sesión. No son apuestas realizadas.</p></header>
    <p className="backtest-caveat">{CAVEAT}</p>
    {state === "loading" && <Loading rows={4} label="Cargando corridas históricas…" />}
    {state === "error" && <ErrorBanner cause={error} recovery="La configuración no se modificó. Podés volver a intentar." preserved actionLabel="Reintentar" onAction={retryLoad} />}
    {state === "ready" && total === 0 && <section className="backtest-empty" role="status"><h3>Todavía no hay corridas históricas</h3><p>Elegí un método, una cobertura y una forma de apostar para explorar qué pasó en el historial.</p><Link className="btn btn-primary" to="/simulaciones/nueva-historica">Nueva corrida histórica</Link></section>}
    {state === "ready" && total > 0 && <>
      <p className="field-help">{total.toLocaleString("es-DO")} corridas guardadas</p>
      <ul className="backtest-run-list" aria-label="Corridas históricas guardadas">{items.map((item) => <li key={item.id}>
        <div><h3>{item.name || backtestScenarioName(item)}</h3><p>{backtestScenarioName(item)} · {item.config?.strategy?.coverage ?? "Sin dato"} números · {item.config?.strategy?.staking ?? "Sin dato"}</p>
          <p className="field-help">Meta {item.goal_rate == null ? "Sin dato" : `${new Intl.NumberFormat("es-DO", { maximumFractionDigits: 1 }).format(item.goal_rate)}%`} · Llegaron {item.reached_goal ?? "Sin dato"} / {item.completed ?? "Sin dato"}</p></div>
        <Link className="btn btn-secondary" aria-label={`Abrir corrida histórica de ${item.name}`} to={`/simulaciones/historicas/${encodeURIComponent(item.id)}`}>Ver resultados</Link>
      </li>)}</ul>
      <div className="flex flex-wrap items-center justify-between gap-3"><p>Mostrando {offset + 1}–{Math.min(offset + items.length, total)} de {total}</p><div className="flex gap-2"><button className="btn btn-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</button><button className="btn btn-secondary" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</button></div></div>
    </>}
  </div>;
}

export function BacktestCreatePage() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [gameSettings, setGameSettings] = useState<GameSettings | null>(null);
  const [draft, setDraft] = useState<BacktestDraft>(INITIAL_DRAFT);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const mounted = useRef(true);
  const inFlight = useRef(false);
  const errors = useMemo(() => validateBacktestDraft(draft), [draft]);
  const inputs = sourceInputs(catalog);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const loadSettings = async () => {
    setLoading(true); setLoadError("");
    try {
      const [catalogResult, gameResult] = await Promise.all([apiClient.getCatalog(), apiClient.getGameSettings()]);
      if (!mounted.current) return;
      setCatalog(catalogResult); setGameSettings(gameResult);
      setDraft((current) => ({ ...current, numbers: String(gameResult.numbers), positions: String(gameResult.positions), prizes: gameResult.prizes.map(String), minStake: String(gameResult.minimum_stake) }));
    } catch (cause) {
      if (mounted.current) setLoadError(errorMessage(cause, "cargar las reglas y los datos históricos"));
    } finally { if (mounted.current) setLoading(false); }
  };
  useEffect(() => { void loadSettings(); }, []);
  function changeRules(key: "numbers" | "positions" | "minStake", value: string) {
    setDraft((current) => {
      if (key === "positions") {
        const count = Number(value);
        const prizes = Number.isSafeInteger(count) && count >= 0 && count <= 16
          ? Array.from({ length: count }, (_, index) => current.prizes[index] ?? "1") : current.prizes;
        return { ...current, positions: value, prizes };
      }
      return { ...current, [key]: value };
    });
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || loading || !gameSettings || !inputs || errors.length) return;
    inFlight.current = true; setSubmitting(true); setError("");
    try {
      const body = buildBacktestBody(draft, gameSettings, inputs);
      const result = await apiClient.createBacktest(body);
      if (mounted.current) navigate(`/simulaciones/historicas/${encodeURIComponent(result.id)}`);
    } catch (cause) {
      if (mounted.current) setError(errorMessage(cause, "crear la corrida histórica"));
    } finally { inFlight.current = false; if (mounted.current) setSubmitting(false); }
  }
  const sections = ["Método", "Cobertura y apuesta", "Reglas del juego", "Capital y resumen"];
  return <div className="backtests-page max-w-3xl space-y-5">
    <ExperimentTabs active="backtests" />
    <header><h2>Nueva corrida histórica</h2><p>Configurá una decisión por paso. Podés cambiar las reglas antes de iniciar.</p></header>
    <p className="backtest-caveat">{CAVEAT}</p>
    <dl className="backtest-financial-summary" aria-label="Condiciones financieras de esta corrida">
      <div><dt>Capital inicial</dt><dd>RD${draft.capital || "Sin dato"}</dd></div>
      <div><dt>Meta de saldo</dt><dd>RD${draft.goal || "Sin dato"}</dd></div>
      <div><dt>Duración</dt><dd>Hasta meta o quiebre; sin límite temporal</dd></div>
    </dl>
    {loadError && <div role="alert" className="space-y-2"><p>{loadError}</p><button className="btn btn-secondary" type="button" onClick={() => void loadSettings()}>Reintentar carga</button></div>}
    {loading && <Loading rows={3} label="Cargando reglas guardadas y datos históricos…" />}
    {!loading && <form onSubmit={(event) => void submit(event)} noValidate className="backtest-form">
      <nav className="backtest-stepper" aria-label="Pasos de la corrida histórica">{sections.map((name, index) => <span key={name} aria-current={index === step ? "step" : undefined}>{index + 1}. {name}</span>)}</nav>
      {step === 0 && <section aria-labelledby="backtest-strategy-heading" className="backtest-step">
        <h3 id="backtest-strategy-heading">¿Cómo se eligen los números?</h3>
        <label className="field"><span className="field-label">Nombre de la corrida</span><input className="control" type="text" maxLength={80} value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></label>
        <label className="field"><span className="field-label">Método de selección</span><select className="control" value={draft.parity ? "parity" : "system"} onChange={(event) => setDraft((current) => ({ ...current, parity: event.target.value === "parity" }))}><option value="system">Sistema de ranking</option><option value="parity">Tu par/impar</option></select></label>
        {draft.parity ? <p className="field-help">Paridad combina 27 votos par/impar calculados antes de cada sorteo; no usa un sistema de ranking.</p> : <>
          <label className="field"><span className="field-label">Sistema</span><select className="control" value={draft.system} onChange={(event) => setDraft((current) => ({ ...current, system: event.target.value as BacktestDraft["system"] }))}>{SYSTEMS.map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
          <ul className="backtest-method-help">{SYSTEMS.map(([key, name, description]) => <li key={key}><strong>{name}:</strong> {description}</li>)}</ul>
        </>}
      </section>}
      {step === 1 && <section aria-labelledby="backtest-staking-heading" className="backtest-step">
        <h3 id="backtest-staking-heading">¿Cuántos números y cómo apostar?</h3>
        <label className="field"><span className="field-label">Números cubiertos</span><input aria-label="Números cubiertos" className="control" type="number" min="1" max={draft.numbers || undefined} step="1" value={draft.coverage} onChange={(event) => setDraft((current) => ({ ...current, coverage: event.target.value }))} /><span className="field-help">Cantidad de números distintos que se cubren por sorteo.</span></label>
        <label className="field"><span className="field-label">Forma de apostar</span><select className="control" value={draft.staking} onChange={(event) => setDraft((current) => ({ ...current, staking: event.target.value as BacktestDraft["staking"] }))}><option value="flat">Plana</option><option value="ladder">Escalera</option><option value="bold">Audaz</option></select></label>
        <ul className="backtest-method-help">{Object.values(stakingDescriptions).map((description) => <li key={description}>{description}</li>)}</ul>
      </section>}
      {step === 2 && <section aria-labelledby="backtest-game-heading" className="backtest-step">
        <h3 id="backtest-game-heading">Reglas del juego</h3>
        <p className="field-help">Se precargaron desde los ajustes del sorteo. Cambiar aquí solo afecta esta corrida.</p>
        <label className="field"><span className="field-label">Números posibles</span><input aria-label="Números posibles" className="control" type="number" min="2" max="1000" step="1" value={draft.numbers} onChange={(event) => changeRules("numbers", event.target.value)} /></label>
        <label className="field"><span className="field-label">Posiciones</span><input aria-label="Posiciones" className="control" type="number" min="1" max="16" step="1" value={draft.positions} onChange={(event) => changeRules("positions", event.target.value)} /></label>
        <fieldset className="backtest-prizes"><legend className="field-label">Premios por posición (RD$ por peso apostado)</legend>{draft.prizes.map((prize, index) => <label className="field" key={index}><span className="field-label">Posición {index + 1}</span><input aria-label={`Premio de la posición ${index + 1}`} className="control" type="number" min="1" step="1" value={prize} onChange={(event) => setDraft((current) => ({ ...current, prizes: current.prizes.map((item, at) => at === index ? event.target.value : item) }))} /></label>)}</fieldset>
        <label className="field"><span className="field-label">Apuesta mínima (RD$)</span><input aria-label="Apuesta mínima (RD$)" className="control" type="number" min="1" step="1" value={draft.minStake} onChange={(event) => changeRules("minStake", event.target.value)} /></label>
        <Link to="/ajustes?paso=reglas" className="btn btn-tertiary">Editar reglas del sorteo</Link>
        {gameSettings && <p className="field-help">Origen de estas reglas: {gameSettings.source === "stored" ? "ajustes guardados" : gameSettings.source === "environment" ? "configuración del sistema" : "valor inicial de la plataforma"} · {gameSettings.name}.</p>}
      </section>}
      {step === 3 && <section aria-labelledby="backtest-conditions-heading" className="backtest-step">
        <h3 id="backtest-conditions-heading">Capital y meta</h3>
        <label className="field"><span className="field-label">Capital inicial (RD$)</span><input aria-label="Capital inicial (RD$)" className="control" type="number" min="1" step="1" value={draft.capital} onChange={(event) => setDraft((current) => ({ ...current, capital: event.target.value }))} /></label>
        <label className="field"><span className="field-label">Meta de saldo (RD$)</span><input aria-label="Meta de saldo (RD$)" className="control" type="number" min="2" step="1" value={draft.goal} onChange={(event) => setDraft((current) => ({ ...current, goal: event.target.value }))} /></label>
        <p className="field-help">Cada sesión empieza con este capital y termina al llegar a la meta o al no poder financiar la siguiente apuesta.</p>
        <div className="backtest-review"><h4>Configuración que se enviará</h4><p>{draft.parity ? "Tu par/impar" : SYSTEMS.find(([key]) => key === draft.system)?.[1]} · {draft.coverage} números · {draft.staking} · capital RD${draft.capital} · meta RD${draft.goal}</p><p>{draft.numbers} números posibles · {draft.positions} posiciones · apuesta mínima RD${draft.minStake}</p></div>
      </section>}
      {errors.length > 0 && <ul className="backtest-validation" aria-label="Qué revisar antes de crear" role="alert">{errors.map((message) => <li key={message}>{message}</li>)}</ul>}
      {!inputs && <p role="alert">El servidor no informó las huellas del historial y sus rankings; no se puede fijar esta corrida con seguridad.</p>}
      {error && <p role="alert" className="backtest-submit-error">{error}</p>}
      <div className="backtest-step-actions"><button type="button" className="btn btn-secondary" disabled={step === 0 || submitting} onClick={() => setStep((value) => Math.max(0, value - 1))}>Anterior</button>{step < 3 ? <button type="button" className="btn btn-primary" onClick={() => setStep((value) => Math.min(3, value + 1))}>Siguiente</button> : <button className="btn btn-primary" type="submit" disabled={submitting || loading || errors.length > 0 || !inputs}>{submitting ? "Creando…" : "Crear corrida histórica"}</button>}</div>
    </form>}
  </div>;
}

export function BacktestDetailPage() {
  const { id = "" } = useParams();
  const [report, setReport] = useState<BacktestReportData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let live = true;
    setLoading(true); setError("");
    apiClient.getBacktest(id).then((value) => { if (live) setReport(value); }).catch((cause: unknown) => { if (live) setError(errorMessage(cause, "cargar el informe histórico")); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [id, retry]);
  return <div className="backtests-page max-w-6xl space-y-5">
    <ExperimentTabs active="backtests" />
    <p><Link className="link" to="/simulaciones/historicas">Volver a corridas históricas</Link></p>
    {loading && <Loading rows={4} label="Cargando informe histórico…" />}
    {error && <ErrorBanner cause={error} recovery="La corrida guardada no se modificó. Podés volver a intentar." preserved actionLabel="Reintentar" onAction={() => setRetry((value) => value + 1)} />}
    {!loading && report && <><header><h2>{report.name || backtestScenarioName(report)}</h2></header><BacktestReport report={report} /></>}
  </div>;
}
