import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { BacktestReport as BacktestReportData, Catalog, ConfigurationSummary, GameSettings } from "../../api/types";
import { StrategyEditor } from "../../components/StrategyEditor";
import { FiveStepWizard, useFiveStepWizard } from "../../components/FiveStepWizard";
import { WizardScopeSelector } from "../../components/WizardScopeSelector";
import { GameRulesSummary } from "../../components/GameRulesSummary";
import { classicRulesView } from "../../lib/game-rules";
import type { StrategyDraft } from "../new-experiment/model";
import { applyHistoricalStrategyDraft, historicalStrategyToDraft, strategyDraftFromBacktest } from "./historical-strategy-compatibility";
import { BacktestReport } from "../../components/BacktestReport";
import { ErrorBanner, Loading } from "../../components/ui";
import { backtestScenarioName, buildBacktestBody, hydrateBacktestDraft, stakingDescriptions, validateBacktestDraft, type BacktestDraft } from "./backtest-model";

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
  if (error instanceof ApiError && error.status === 409) return "Cambió el historial o los rankings disponibles. Revisá las fuentes en Datos antes de crear otra corrida.";
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
        <div className="flex flex-wrap gap-2"><Link className="btn btn-secondary" aria-label={`Abrir corrida histórica de ${item.name}`} to={`/simulaciones/historicas/${encodeURIComponent(item.id)}`}>Ver resultados</Link><Link className="btn btn-secondary" aria-label={`Repetir con cambios: ${item.name}`} to={`/simulaciones/nueva-historica?base=${encodeURIComponent(item.id)}`}>Repetir con cambios</Link></div>
      </li>)}</ul>
      <div className="flex flex-wrap items-center justify-between gap-3"><p>Mostrando {offset + 1}–{Math.min(offset + items.length, total)} de {total}</p><div className="flex gap-2"><button className="btn btn-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</button><button className="btn btn-secondary" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</button></div></div>
    </>}
  </div>;
}

export function BacktestCreatePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const baseId = searchParams.get("base");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [gameSettings, setGameSettings] = useState<GameSettings | null>(null);
  const [savedConfigurations, setSavedConfigurations] = useState<ConfigurationSummary[]>([]);
  const [libraryError, setLibraryError] = useState("");
  const [selectedConfiguration, setSelectedConfiguration] = useState("");
  const [configurationError, setConfigurationError] = useState("");
  const [configurationPending, setConfigurationPending] = useState(false);
  const configurationRequest = useRef(0);
  const [draft, setDraft] = useState<BacktestDraft>(INITIAL_DRAFT);
  const wizard = useFiveStepWizard(5, validateWizardStep);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const mounted = useRef(true);
  const loadSequence = useRef(0);
  const inFlight = useRef(false);
  const errors = useMemo(() => validateBacktestDraft(draft), [draft]);
  const inputs = draft.inputs ?? sourceInputs(catalog);
  const editorCatalog = useMemo(() => catalog && ({
    ...catalog, selectors: ["system", "parity"] as Catalog["selectors"],
    coverages: Array.from(new Set([...catalog.coverages, Number(draft.coverage)])).filter((coverage) => Number.isSafeInteger(coverage) && coverage > 0),
    systems: Object.fromEntries(SYSTEMS.map(([key, label]) => [key, catalog.systems[key] ?? label])),
  }), [catalog, draft.coverage]);
  const strategyDraft = strategyDraftFromBacktest(draft);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const loadSettings = async (ticket: number) => {
    setLoading(true); setLoadError("");
    try {
      const [catalogResult, gameResult, baseReport] = await Promise.all([
        apiClient.getCatalog(), apiClient.getGameSettings(), baseId ? apiClient.getBacktest(baseId) : Promise.resolve(null),
      ]);
      if (!mounted.current || ticket !== loadSequence.current) return;
      const repeatedDraft = baseReport && hydrateBacktestDraft(baseReport.config);
      if (baseId && !repeatedDraft) throw new Error("La corrida guardada no contiene una configuración completa y válida.");
      setCatalog(catalogResult); setGameSettings(gameResult);
      setDraft(repeatedDraft ?? { ...INITIAL_DRAFT, numbers: String(gameResult.numbers), positions: String(gameResult.positions), prizes: gameResult.prizes.map(String), minStake: String(gameResult.minimum_stake) });
    } catch (cause) {
      if (mounted.current && ticket === loadSequence.current) setLoadError(baseId ? `No se pudo cargar la configuración guardada para repetir. ${errorMessage(cause, "cargar la corrida histórica")}` : errorMessage(cause, "cargar las reglas y los datos históricos"));
    } finally { if (mounted.current && ticket === loadSequence.current) setLoading(false); }
  };
  useEffect(() => {
    const ticket = ++loadSequence.current;
    void loadSettings(ticket);
    return () => { loadSequence.current++; };
  }, [baseId, retry]);
  useEffect(() => {
    let live = true;
    apiClient.listConfigurations(0, 100).then((page) => { if (live) { setSavedConfigurations(page.items); setLibraryError(""); } })
      .catch(() => { if (live) setLibraryError("No se pudieron cargar las estrategias guardadas. Podés continuar con una configuración manual."); });
    return () => { live = false; };
  }, [retry]);
  async function selectConfiguration(id: string) {
    const ticket = ++configurationRequest.current;
    setSelectedConfiguration(id); setConfigurationError("");
    if (!id) { setConfigurationPending(false); return; }
    setConfigurationPending(true);
    try {
      const saved = await apiClient.getConfiguration(id);
      if (ticket !== configurationRequest.current) return;
      const adapted = historicalStrategyToDraft(saved.strategy, Number(draft.numbers));
      if (!adapted) { setConfigurationError("Esta estrategia guardada usa una selección no disponible en corridas históricas. No se convierte a otro método; elegí otra o continuá con una configuración manual."); return; }
      setDraft((current) => applyHistoricalStrategyDraft(current, adapted) ?? current);
    } catch (cause) {
      if (ticket === configurationRequest.current) setConfigurationError(cause instanceof ApiError && cause.status === 404
        ? "La estrategia guardada ya no existe. Actualizá la página de Estrategias y elegí otra."
        : "No se pudo cargar la estrategia guardada; no se aplicaron cambios. Reintentá o elegí otra.");
    } finally { if (ticket === configurationRequest.current) setConfigurationPending(false); }
  }
  function changeStrategy(value: StrategyDraft) {
    configurationRequest.current++;
    setConfigurationPending(false);
    // The shared classic editor resets coverage on selector changes; historical
    // replay keeps the user's native subset instead, in both directions.
    const changedSelector = value.selector !== strategyDraft.selector;
    const adapted = applyHistoricalStrategyDraft(draft, changedSelector ? {
      ...value, coverage: draft.coverage, system: value.selector === "parity" ? "" : draft.system,
    } : value);
    if (adapted) { setDraft(adapted); setSelectedConfiguration(""); setConfigurationError(""); }
  }
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
  function validateWizardStep(currentStep: number): boolean {
    if (currentStep === 2) {
      setError(inputs ? "" : "No se pudieron verificar las huellas del historial y sus rankings.");
      return Boolean(inputs);
    }
    // Exact model messages, including parity, belong to the editable native step.
    const strategyErrors = new Set([
      "Ingresá un nombre para la estrategia.",
      "La cobertura debe ser un número entero desde 1.",
      `La cobertura supera los ${Number(draft.numbers)} números posibles; la estrategia no puede elegirlos.`,
      "Paridad puede cubrir hasta 50 números; con más no hay números para seleccionar.",
    ]);
    const ruleErrors = new Set([
      "Ingresá entre 2 y 1.000 números posibles; la regla debe coincidir con el sorteo.",
      "Ingresá entre 1 y 16 posiciones de premio.",
      "Ingresá un premio entero de al menos RD$1 por cada posición.",
      "La apuesta mínima debe ser un entero de al menos RD$1.",
    ]);
    const capitalErrors = new Set([
      "Escribí un nombre de hasta 80 caracteres para reconocer la corrida.",
      "El capital debe ser un entero de al menos RD$1.",
      "La meta debe ser mayor que el capital; sin esa diferencia la sesión no puede terminar al alcanzarla.",
    ]);
    const owners = [strategyErrors, ruleErrors, new Set<string>(), capitalErrors];
    const applicable = errors.filter((message) => owners[currentStep]?.has(message));
    if (currentStep === 0 && (configurationError || configurationPending)) {
      setError(configurationError || "Esperá a que termine la carga de la estrategia guardada."); return false;
    }
    setError(applicable.join(" "));
    return applicable.length === 0;
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (wizard.step !== 4 || inFlight.current || loading || !gameSettings || !inputs || errors.length || configurationError || configurationPending) return;
    inFlight.current = true; setSubmitting(true); setError("");
    try {
      const body = buildBacktestBody(draft, gameSettings, inputs);
      const result = await apiClient.createBacktest(body);
      if (mounted.current) navigate(`/simulaciones/historicas/${encodeURIComponent(result.id)}`);
    } catch (cause) {
      if (mounted.current) setError(baseId && cause instanceof ApiError && cause.status === 409
        ? "Las huellas guardadas del historial o los rankings ya no están disponibles. Revisá las fuentes en Datos; no se cambian automáticamente en esta repetición."
        : errorMessage(cause, "crear la corrida histórica"));
    } finally { inFlight.current = false; if (mounted.current) setSubmitting(false); }
  }
  const sections = [
    { title: "1 · Estrategia", description: "Elegí un método compatible, cobertura y forma de apostar." },
    { title: "2 · Reglas", description: "Revisá las reglas del juego para esta corrida." },
    { title: "3 · Alcance", description: "Confirmá el historial completo y las huellas de origen." },
    { title: "4 · Capital y meta", description: "Identificá la corrida y definí sus límites financieros." },
    { title: "5 · Revisá y creá", description: "Confirmá la configuración antes de crearla." },
  ];
  return <div className="backtests-page max-w-3xl space-y-5">
    <ExperimentTabs active="backtests" />
    <header><h2>Nueva corrida histórica</h2><p>{baseId ? "Se crea una corrida nueva a partir de esta configuración; la original no se modifica." : "Configurá una decisión por paso. Podés cambiar las reglas antes de iniciar."}</p></header>
    <p className="backtest-caveat">{CAVEAT}</p>
    <dl className="backtest-financial-summary" aria-label="Condiciones financieras de esta corrida">
      <div><dt>Capital inicial</dt><dd>RD${draft.capital || "Sin dato"}</dd></div>
      <div><dt>Meta de saldo</dt><dd>RD${draft.goal || "Sin dato"}</dd></div>
      <div><dt>Duración</dt><dd>Hasta meta o quiebre; sin límite temporal</dd></div>
    </dl>
    {loadError && <div role="alert" className="space-y-2"><p>{loadError}</p><button className="btn btn-secondary" type="button" onClick={() => setRetry((value) => value + 1)}>Reintentar carga</button>{baseId && <Link className="btn btn-tertiary" to="/simulaciones/historicas">Volver a corridas históricas</Link>}</div>}
    {loading && <Loading rows={3} label={baseId ? "Cargando la configuración guardada…" : "Cargando reglas guardadas y datos históricos…"} />}
    {!loading && !loadError && <form onSubmit={(event) => void submit(event)} noValidate className="backtest-form">
      <FiveStepWizard steps={sections} activeStep={wizard.step} maxReachableStep={wizard.maxReachableStep} onSelectStep={wizard.goTo} onNext={wizard.next} onBack={wizard.back} busy={loading || submitting || configurationPending}>
      {error && <p role="alert" className="backtest-submit-error">{error}</p>}
      {wizard.step === 0 && <section aria-labelledby="backtest-strategy-heading" className="backtest-step">
        <h3 id="backtest-strategy-heading">¿Cómo se eligen los números?</h3>
        {editorCatalog && <>
          <label className="field"><span className="field-label">Estrategia guardada (opcional)</span><select className="control" aria-label="Estrategia guardada (opcional)" value={selectedConfiguration} onChange={(event) => void selectConfiguration(event.target.value)}><option value="">Configurar manualmente</option>{savedConfigurations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          {libraryError && <p className="field-help" role="status">{libraryError}</p>}
          {configurationError && <p className="backtest-submit-error" role="alert">{configurationError}</p>}
          {configurationPending && <p role="status">Cargando la estrategia guardada…</p>}
          {/* Classic parity has fixed coverage; compose historical controls with
              the ranking editor without changing that shared contract. */}
          {draft.parity ? <div className="space-y-4">
            <label className="field"><span className="field-label">Nombre de la estrategia 1</span><input className="control" maxLength={81} value={strategyDraft.name} onChange={(event) => changeStrategy({ ...strategyDraft, name: event.target.value })} /></label>
            <label className="field"><span className="field-label">Método de la estrategia 1</span><select className="control" value="parity" onChange={(event) => changeStrategy({ ...strategyDraft, selector: event.target.value as StrategyDraft["selector"] })}><option value="system">Sistema de ranking</option><option value="parity">Tu par/impar</option></select></label>
            <p className="field-help">Paridad histórica permite cubrir de 1 a 50 números, sin superar los números posibles del juego.</p>
          </div> : <StrategyEditor value={strategyDraft} index={0} catalog={editorCatalog} errors={{}} onChange={changeStrategy} />}
          <fieldset disabled className="backtest-method-help" aria-label="Métodos no disponibles en corridas históricas">
            <legend className="field-label">No disponibles en corridas históricas</legend>
            {[...Object.entries(catalog?.systems ?? {}).filter(([key]) => !SYSTEMS.some(([supported]) => supported === key)).map(([, label]) => label), "Combinación de estrategias (blend)", "Aleatorio (random)"].map((label) => <label key={label} className="mr-4 inline-flex items-center gap-2 opacity-60"><input type="checkbox" disabled />{label}</label>)}
          </fieldset>
          <p className="field-help">Estas opciones quedan deshabilitadas; las estrategias guardadas incompatibles se rechazan y no se convierten a otro método.</p>
        </>}
      </section>}
      {wizard.step === 0 && <section aria-labelledby="backtest-staking-heading" className="backtest-step">
        <h3 id="backtest-staking-heading">¿Cuántos números y cómo apostar?</h3>
        <label className="field"><span className="field-label">Números cubiertos</span><input aria-label="Números cubiertos" className="control" type="number" min="1" max={draft.parity ? Math.min(50, Number(draft.numbers)) : draft.numbers || undefined} step="1" value={draft.coverage} onChange={(event) => setDraft((current) => ({ ...current, coverage: event.target.value }))} /><span className="field-help">Cantidad de números distintos que se cubren por sorteo.</span></label>
        <label className="field"><span className="field-label">Forma de apostar</span><select className="control" value={draft.staking} onChange={(event) => setDraft((current) => ({ ...current, staking: event.target.value as BacktestDraft["staking"] }))}><option value="flat">Plana</option><option value="ladder">Escalera</option><option value="bold">Audaz</option></select></label>
        <ul className="backtest-method-help">{Object.values(stakingDescriptions).map((description) => <li key={description}>{description}</li>)}</ul>
      </section>}
      {wizard.step === 1 && <section aria-labelledby="backtest-game-heading" className="backtest-step">
        <h3 id="backtest-game-heading">Reglas del juego</h3>
        <p className="field-help">{baseId ? "Reglas guardadas de la corrida original. Cambiar aquí solo afecta la nueva corrida." : "Se precargaron desde los ajustes del sorteo. Cambiar aquí solo afecta esta corrida."}</p>
        <GameRulesSummary view={classicRulesView({ numbers: draft.numbers, positions: draft.positions, prizes: draft.prizes, minimum_stake: draft.minStake }, baseId ? `Configuración histórica guardada /backtests/${baseId} · borrador de la corrida nueva` : "Ajustes clásicos /settings/game · borrador local de esta corrida", { draft: true, source: baseId ? undefined : gameSettings?.source, settlementContract: "historical-unreported" })} />
        <label className="field"><span className="field-label">Números posibles</span><input aria-label="Números posibles" className="control" type="number" min="2" max="1000" step="1" value={draft.numbers} onChange={(event) => changeRules("numbers", event.target.value)} /></label>
        <label className="field"><span className="field-label">Posiciones</span><input aria-label="Posiciones" className="control" type="number" min="1" max="16" step="1" value={draft.positions} onChange={(event) => changeRules("positions", event.target.value)} /></label>
        <fieldset className="backtest-prizes"><legend className="field-label">Premios por posición (RD$ por peso apostado)</legend>{draft.prizes.map((prize, index) => <label className="field" key={index}><span className="field-label">Posición {index + 1}</span><input aria-label={`Premio de la posición ${index + 1}`} className="control" type="number" min="1" step="1" value={prize} onChange={(event) => setDraft((current) => ({ ...current, prizes: current.prizes.map((item, at) => at === index ? event.target.value : item) }))} /></label>)}</fieldset>
        <label className="field"><span className="field-label">Apuesta mínima (RD$)</span><input aria-label="Apuesta mínima (RD$)" className="control" type="number" min="1" step="1" value={draft.minStake} onChange={(event) => changeRules("minStake", event.target.value)} /></label>
        <Link to="/ajustes?paso=reglas" className="btn btn-tertiary">Editar reglas del sorteo</Link>
        {!baseId && gameSettings && <p className="field-help">Origen de estas reglas: {gameSettings.source === "stored" ? "ajustes guardados" : gameSettings.source === "environment" ? "configuración del sistema" : "valor inicial de la plataforma"} · {gameSettings.name}.</p>}
      </section>}
      {wizard.step === 2 && <section aria-labelledby="backtest-scope-heading" className="backtest-step">
        <h3 id="backtest-scope-heading">Historial completo y fuentes</h3><p>La corrida recorre todo el historial disponible. No se eligió un sorteo inicial parcial.</p>
        {inputs ? <dl className="data-list"><dt>Huella del historial</dt><dd className="break-all">{inputs.history_sha256}</dd><dt>Huella de rankings</dt><dd className="break-all">{inputs.rankings_sha256}</dd></dl> : <p role="alert">No se pudieron verificar las huellas del origen.</p>}
        <WizardScopeSelector currentMode="history" busy={loading || submitting || configurationPending || inFlight.current} />
      </section>}
      {wizard.step === 3 && <section aria-labelledby="backtest-conditions-heading" className="backtest-step">
        <h3 id="backtest-conditions-heading">Capital y meta</h3>
        <label className="field"><span className="field-label">Nombre de la corrida</span><input className="control" type="text" maxLength={80} value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></label>
        <label className="field"><span className="field-label">Capital inicial (RD$)</span><input aria-label="Capital inicial (RD$)" className="control" type="number" min="1" step="1" value={draft.capital} onChange={(event) => setDraft((current) => ({ ...current, capital: event.target.value }))} /></label>
        <label className="field"><span className="field-label">Meta de saldo (RD$)</span><input aria-label="Meta de saldo (RD$)" className="control" type="number" min="2" step="1" value={draft.goal} onChange={(event) => setDraft((current) => ({ ...current, goal: event.target.value }))} /></label>
        <p className="field-help">Cada sesión empieza con este capital y termina al llegar a la meta o al no poder financiar la siguiente apuesta.</p>
        <div className="backtest-review"><h4>Configuración que se enviará</h4><p>{draft.parity ? "Tu par/impar" : SYSTEMS.find(([key]) => key === draft.system)?.[1]} · {draft.coverage} números · {draft.staking} · capital RD${draft.capital} · meta RD${draft.goal}</p><p>{draft.numbers} números posibles · {draft.positions} posiciones · apuesta mínima RD${draft.minStake}</p></div>
      </section>}
      {wizard.step === 4 && <section aria-labelledby="backtest-review-heading" className="backtest-step">
        <h3 id="backtest-review-heading">Revisá la corrida histórica</h3>
        <dl className="data-list"><dt>Nombre</dt><dd>{draft.name || "Sin nombre"}</dd><dt>Estrategia</dt><dd>{draft.parity ? "Tu par/impar" : draft.strategyName ?? SYSTEMS.find(([key]) => key === draft.system)?.[1]} · {draft.coverage} números · {draft.staking}</dd><dt>Reglas</dt><dd>{draft.numbers} números · {draft.positions} posiciones · apuesta mínima RD${draft.minStake}</dd><dt>Capital y meta</dt><dd>RD${draft.capital} · RD${draft.goal}</dd><dt>Capital</dt><dd>RD${draft.capital}</dd><dt>Meta</dt><dd>RD${draft.goal}</dd><dt>Duración</dt><dd>Hasta meta o quiebre; sin límite temporal</dd><dt>Advertencia</dt><dd>{CAVEAT}</dd><dt>Alcance</dt><dd>Todo el historial · huellas de origen fijadas</dd></dl>
        <button className="btn btn-primary" type="submit" disabled={submitting || loading || errors.length > 0 || !inputs || !!configurationError || configurationPending}>{submitting ? "Creando…" : "Crear corrida histórica"}</button>
      </section>}
      </FiveStepWizard>
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
    {!loading && report && <><header><h2>{report.name || backtestScenarioName(report)}</h2></header><BacktestReport report={report} />{hydrateBacktestDraft(report.config) && <Link className="btn btn-primary" to={`/simulaciones/nueva-historica?base=${encodeURIComponent(report.id)}`}>Repetir con cambios</Link>}</>}
  </div>;
}
