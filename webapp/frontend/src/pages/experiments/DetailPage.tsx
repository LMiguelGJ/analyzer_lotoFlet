import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import { isProfileBatchExperiment, isProfileBatchRun, isProfileExperiment, isProfileReplay, isProfileRun } from "../../api/types";
import type { AnyRunSummary, Bet, ExperimentSummary, LegacyExperimentSummary, ProfileBatchExperimentSummary, ProfileBet, ProfileExperimentSummary, ProfileRunResult, ReplayPage, RunSummary } from "../../api/types";
import { RunTrajectory } from "../../components/RunTrajectory";
import { FinancialMetrics } from "../../components/FinancialMetrics";
import { DataTable } from "../../components/DataTable";
import type { DataTableColumn } from "../../components/DataTable";
import { StatusLabel } from "../../components/StatusLabel";
import { Disclosure, Figure, Loading, SectionHeader, Stat } from "../../components/ui";
import type { FigureVariant } from "../../components/ui";
import { formatDOP, formatTwoDigit } from "../../lib/format";
import { PROFILE_COLLISION_LABELS, PROFILE_OUTCOME_LABELS, profileMoney } from "../../lib/profile-display";
import { FIELD_HELP_DELTA, FIELD_LABEL_DELTA, SELECTOR_LABELS, SETTLEMENT_LABELS, STAKING_LABELS } from "../../lib/ui-labels";
import { PAGE_SIZE, pageOffset, replayIndex } from "./replay";

const button = "btn btn-secondary";
const tabs = ["Resultado", "Apuestas", "Parámetros y datos"] as const;
type Tab = typeof tabs[number];
const numberList = (values: number[]) => values.map(formatTwoDigit).join(", ");
function storedDate(label: string) {
  // Display the stored draw label verbatim, merely separating an ISO date/time.
  return label.replace("T", " ");
}
function stopCategoryLabel(category: string) {
  return ({ financial_goal: "Meta financiera alcanzada", financial_ruin: "Quiebre financiero", recovery_end: "Fin de escalera de recuperación", interrupted: "Interrumpida", configured_limit: "Límite configurado", operational_budget: "Límite operativo; fuente incompleta", operational_window: "Ventana operativa; fuente incompleta", source_end: "Fin de la fuente guardada", unknown: "Cierre no disponible" } as Record<string, string>)[category] ?? "Cierre no reconocido";
}
function detailError(error: unknown) {
  if (error instanceof NetworkError) return "No se pudo contactar al servidor. El cálculo puede continuar en el servidor; comprobá el estado desde la cola antes de reintentar.";
  if (error instanceof ApiError && error.status === 404) return "Este experimento no existe o fue eliminado.";
  return "No se pudo consultar el experimento. Reintentá.";
}
export function verdictPhrase(outcome: string | undefined, status: string): string {
  if (outcome === "goal") return "Meta alcanzada";
  if (outcome === "ruin") return "Se agotó el capital";
  if (outcome === "limit") return "Límite de sesión";
  if (outcome === "history_exhausted") return "Historial agotado";
  if (outcome === "cancelled" || status === "cancelled") return "Simulación cancelada";
  if (status === "pending" || status === "running" || status === "held") return "En curso";
  return "Simulación cerrada";
}

function financialConclusion(run: AnyRunSummary): string | null {
  if (!run.result) return null;
  if (run.result.outcome === "goal") return "Llegó a la meta.";
  if (run.result.outcome === "ruin") return "Perdió: se quedó sin plata.";
  if (run.result.outcome === "limit") return "Se detuvo al alcanzar el límite de duración.";
  if (run.result.outcome === "history_exhausted") return "Se detuvo: terminó el historial disponible.";
  return "La simulación terminó sin alcanzar la meta.";
}

function profileCloseReason(result: ProfileRunResult): string {
  const reasons = result.collisions.map((reason) => PROFILE_COLLISION_LABELS[reason]).filter((reason): reason is string => Boolean(reason));
  return `${PROFILE_OUTCOME_LABELS[result.outcome]}${reasons.length ? ` (${reasons.join(", ")})` : ""}`;
}

function replayError(error: unknown) {
  if (error instanceof NetworkError) return "No se pudo contactar al servidor. Lo guardado no cambió.";
  if (error instanceof ApiError && error.status === 409) return "La reproducción todavía no está disponible para esta ejecución.";
  if (error instanceof ApiError && error.status === 404) return "La ejecución o el experimento ya no existe.";
  return "No se pudo cargar esta página de apuestas. Reintentá.";
}

function BetDetails({ bet }: { bet: Bet }) {
  const [open, setOpen] = useState(false);
  return <div>
    <button type="button" className="btn btn-tertiary" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Ocultar detalle" : "Detalle"}</button>
    {open && <dl className="data-list mt-2 min-w-[220px]">
      <dt>Fecha y hora</dt><dd>{storedDate(bet.label)}</dd>
      <dt>Números elegidos</dt><dd>{numberList(bet.numbers)}</dd>
      <dt>Apuesta por número</dt><dd className="data-list-numeric">{formatDOP(bet.per_number)}</dd>
      <dt>Resultados (posiciones 1 a 5)</dt><dd>{numberList(bet.results)}</dd>
      <dt>Cobro</dt><dd className="data-list-numeric">{formatDOP(bet.paid)}</dd>
      <dt>Saldo resultante</dt><dd className="data-list-numeric">{formatDOP(bet.balance)}</dd>
    </dl>}
  </div>;
}

function ProfileBetDetails({ bet, data }: { bet: ProfileBet; data: ProfileExperimentSummary }) {
  const [open, setOpen] = useState(false);
  return <div><button type="button" className="btn btn-tertiary" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Ocultar detalle" : "Detalle"}</button>
    {open && <dl className="data-list mt-2 min-w-[220px]">
      <dt>Fecha y hora</dt><dd>{storedDate(bet.label)}</dd>
      <dt>Apuestas por número</dt><dd>{bet.stakes.map(([number, stake]) => `${number}: ${profileMoney(data, stake)}`).join(", ")}</dd>
      <dt>Resultados ({bet.results.length} posiciones)</dt><dd>{bet.results.join(", ")}</dd>
      <dt>Cobro</dt><dd className="data-list-numeric">{profileMoney(data, bet.paid)}</dd>
      <dt>Saldo resultante</dt><dd className="data-list-numeric">{profileMoney(data, bet.balance)}</dd>
    </dl>}
  </div>;
}

function profileColumns(data: ProfileExperimentSummary, canonical = false): DataTableColumn<ProfileBet>[] {
  return [
    ...(canonical ? [
      { key: "source-index", header: "Sorteo n.º", render: (bet: ProfileBet) => bet.source_index == null ? "—" : bet.source_index },
      { key: "bet-index", header: "Apuesta n.º", render: (bet: ProfileBet) => bet.bet_index == null ? "—" : bet.bet_index + 1 },
    ] : []),
    { key: "date", header: "Fecha y hora", render: (bet) => storedDate(bet.label) },
    { key: "stakes", header: "Apuestas por número", render: (bet) => bet.stakes.map(([number, stake]) => `${number}: ${profileMoney(data, stake)}`).join(", ") },
    { key: "wagered", header: "Gasto total", headerClassName: "text-right", cellClassName: "text-right font-mono tabular-nums", render: (bet) => profileMoney(data, bet.wagered) },
    ...Array.from({ length: data.profile.positions }, (_, position): DataTableColumn<ProfileBet> => ({ key: `result-${position}`, header: `Resultado ${position + 1}`, render: (bet) => bet.results[position] ?? "—" })),
    { key: "paid", header: "Cobro", headerClassName: "text-right", cellClassName: "text-right font-mono tabular-nums", render: (bet) => profileMoney(data, bet.paid) },
    { key: "balance", header: "Saldo", headerClassName: "text-right", cellClassName: "text-right font-mono tabular-nums", render: (bet) => profileMoney(data, bet.balance) },
    { key: "detail", header: "Detalle", render: (bet) => <ProfileBetDetails bet={bet} data={data} /> },
  ];
}

const columns: DataTableColumn<Bet>[] = [
  { key: "date", header: "Fecha y hora", render: (bet) => storedDate(bet.label) },
  { key: "numbers", header: "Números elegidos", render: (bet) => numberList(bet.numbers) },
  { key: "per", header: "Por número", headerClassName: "text-right", cellClassName: "text-right font-mono tabular-nums", render: (bet) => formatDOP(bet.per_number) },
  { key: "wagered", header: "Gasto total", headerClassName: "text-right", cellClassName: "text-right font-mono tabular-nums", render: (bet) => formatDOP(bet.wagered) },
  ...[0, 1, 2, 3, 4].map((position): DataTableColumn<Bet> => ({ key: `result-${position}`, header: `Resultado ${position + 1}`, render: (bet) => formatTwoDigit(bet.results[position]) })),
  { key: "paid", header: "Cobro", headerClassName: "text-right", cellClassName: "text-right font-mono tabular-nums", render: (bet) => formatDOP(bet.paid) },
  { key: "balance", header: "Saldo", headerClassName: "text-right", cellClassName: "text-right font-mono tabular-nums", render: (bet) => formatDOP(bet.balance) },
  { key: "detail", header: "Detalle", render: (bet) => <BetDetails bet={bet} /> },
];

const ledgerMoneyCell = "text-right font-mono tabular-nums";
function profileLedgerColumns(data: ProfileExperimentSummary): DataTableColumn<ProfileBet>[] {
  return [
    { key: "date", header: "Sorteo", render: (bet) => storedDate(bet.label) },
    { key: "wagered", header: "Gasto", headerClassName: "text-right", cellClassName: ledgerMoneyCell, render: (bet) => profileMoney(data, bet.wagered) },
    { key: "paid", header: "Cobro", headerClassName: "text-right", cellClassName: ledgerMoneyCell, render: (bet) => profileMoney(data, bet.paid) },
    { key: "balance", header: "Saldo", headerClassName: "text-right", cellClassName: ledgerMoneyCell, render: (bet) => profileMoney(data, bet.balance) },
  ];
}
const ledgerColumns: DataTableColumn<Bet>[] = [
  { key: "date", header: "Sorteo", render: (bet) => storedDate(bet.label) },
  { key: "wagered", header: "Gasto", headerClassName: "text-right", cellClassName: ledgerMoneyCell, render: (bet) => formatDOP(bet.wagered) },
  { key: "paid", header: "Cobro", headerClassName: "text-right", cellClassName: ledgerMoneyCell, render: (bet) => formatDOP(bet.paid) },
  { key: "balance", header: "Saldo", headerClassName: "text-right", cellClassName: ledgerMoneyCell, render: (bet) => formatDOP(bet.balance) },
];

function Parameters({ data, run }: { data: LegacyExperimentSummary; run: RunSummary }) {
  const conditions = data.request.conditions;
  const strategy = data.request.strategies[run.ordinal];
  return <div className="space-y-6 text-sm">
    <dl className="data-list">
      <dt>Sorteo inicial</dt><dd>{storedDate(conditions.start_draw)}</dd>
      <dt>Límite de apuestas</dt><dd>{conditions.max_bets ?? "Sin límite"}</dd>
      <dt>Límite de minutos históricos</dt><dd>{conditions.max_minutes ?? "Sin límite"}</dd>
      <dt>Liquidación</dt><dd>{SETTLEMENT_LABELS[conditions.settlement]}</dd>
      <dt>Semilla guardada</dt><dd>{conditions.seed}</dd>
            <dt>Estrategia</dt><dd>{strategy?.name ?? "No registrada"}</dd>
      {strategy && <><dt>Selector</dt><dd>{SELECTOR_LABELS[strategy.selector]}</dd><dt>Sistema</dt><dd>{strategy.system ?? "—"}</dd><dt>Cobertura</dt><dd>{strategy.coverage}</dd><dt>Apuesta</dt><dd>{STAKING_LABELS[strategy.staking]}</dd>
        {strategy.components && <><dt>Componentes guardados</dt><dd>{strategy.components.map((component) => `${component.system}: ${component.weight}`).join(", ")}</dd></>}</>}
    </dl>
    <div>
      <dl className="data-list break-all pt-2">
        <dt>Configuración asociada</dt><dd className={run.configuration_id ? "font-mono" : undefined}>{run.configuration_id ?? "Sin configuración asociada"}</dd>
        <dt>Historial</dt><dd className="font-mono">{data.sources.history_id}</dd><dt>SHA-256 historial</dt><dd className="font-mono">{data.sources.history_sha256}</dd>
        <dt>Rankings</dt><dd className="font-mono">{data.sources.rankings_id}</dd><dt>SHA-256 rankings</dt><dd className="font-mono">{data.sources.rankings_sha256}</dd>
        <dt>Versión de código</dt><dd className="font-mono">{data.sources.code_version}</dd>
      </dl>
    </div>
  </div>;
}

function ProfileParameters({ data, run }: { data: Exclude<ProfileExperimentSummary, ProfileBatchExperimentSummary>; run: AnyRunSummary }) {
  const { conditions, selector } = data.request;
  return <div className="space-y-6 text-sm"><dl className="data-list">
    <dt>Sorteo inicial</dt><dd>{storedDate(conditions.start_draw)}</dd>
    <dt>Perfil</dt><dd>{data.profile.profile_id} · revisión {data.profile.revision} · {data.profile.positions} posiciones · {data.display.currency}</dd>
    <dt>Límite de sorteos transcurridos</dt><dd>{conditions.max_elapsed_draws ?? "Sin límite"}</dd>
    <dt>Límite de sorteos apostados</dt><dd>{conditions.max_bet_draws ?? "Sin límite"}</dd>
    <dt>Hora límite</dt><dd>{conditions.end_minute ?? "Sin límite"}</dd>
    <dt>Duración límite (minutos)</dt><dd>{conditions.duration_minutes ?? "Sin límite"}</dd>
    <dt>Liquidación</dt><dd>{SETTLEMENT_LABELS[conditions.settlement]}</dd>
    <dt>Selector</dt><dd>{data.display.selector_label} · cobertura {selector.coverage}{selector.numbers ? ` · números ${selector.numbers.join(", ")}` : ""}</dd>
    <dt>Apuesta</dt><dd>{data.request.schema_version === 1
      ? `${data.display.staking_label} · ${profileMoney(data, data.request.staking.per_number_stake)} por número`
      : data.display.staking_label}</dd>
    {data.request.schema_version === 4 && <><dt>Margen objetivo</dt><dd>{profileMoney(data, data.request.staking.target_margin)}</dd><dt>Rondas de recuperación</dt><dd>{data.request.staking.rounds}</dd><dt>Al agotar la escalera</dt><dd>{data.request.staking.end_mode === "cycle" ? "Reiniciar la escalera" : "Detener la sesión"}</dd></>}
      </dl><dl className="data-list pt-2"><dt>Versión de solicitud</dt><dd>Perfil v{data.request.schema_version}</dd><dt>Versión del resultado</dt><dd>{isProfileRun(run) && run.result ? `Perfil v${run.result.schema_version}` : "No disponible"}</dd><dt>Conjunto de datos SHA-256</dt><dd className="font-mono break-all">{data.request.dataset_sha256}</dd>
    <dt>Perfil SHA-256</dt><dd className="font-mono break-all">{data.request.profile_sha256}</dd>
    <dt>Versión de código</dt><dd>{data.sources.code_version}</dd></dl></div>;
}

function ProfileBatchParameters({ data, run }: { data: ProfileBatchExperimentSummary; run: AnyRunSummary }) {
  const { conditions } = data.request;
  const admission = data.batch_admission;
  const identity = admission.source_identity;
  const strategyRef = isProfileBatchRun(run) ? run.strategy : admission.strategy_refs[run.ordinal];
  const strategyName = isProfileBatchRun(run) ? run.strategy.name : null;
  const definition = data.request.strategies[run.ordinal];
  return <div className="space-y-6 text-sm"><dl className="data-list break-all">
    <dt>Sorteo inicial</dt><dd>{storedDate(conditions.start_draw)}</dd>
    <dt>Perfil</dt><dd>{data.request.profile_id} · revisión {data.request.profile_revision}</dd>
    <dt>Liquidación</dt><dd>{SETTLEMENT_LABELS[conditions.settlement]}</dd>
    <dt>Estrategia</dt><dd>{strategyName ?? definition?.name ?? "No disponible"} · revisión {strategyRef?.revision ?? "—"}{definition ? ` · cobertura ${definition.coverage}` : ""}</dd>
    <dt>Ventana</dt><dd>{String(admission.effective_constraints.max_draws ?? data.request.max_draws)} sorteos máximos · {String(admission.effective_constraints.max_elapsed_draws ?? "sin límite")} transcurridos</dd>
    <dt>Filas de la fuente</dt><dd>{identity.row_count}</dd>
  </dl><dl className="data-list break-all pt-2">
    <dt>Versión de solicitud</dt><dd>Perfil v{data.request.schema_version}</dd>
    <dt>Versión del resultado</dt><dd>{isProfileBatchRun(run) && run.result ? `Perfil v${run.result.schema_version}` : "No disponible"}</dd>
    <dt>Sorteo de inicio (índice fuente)</dt><dd>{definition ? data.runs[run.ordinal]?.result?.start_draw_index ?? "(no iniciado)" : "—"}</dd>
    <dt>SHA-256 del perfil</dt><dd className="font-mono">{data.request.profile_sha256}</dd>
    <dt>ID de estrategia</dt><dd>{strategyRef?.id ?? "—"}</dd>
    <dt>SHA-256 de definición</dt><dd className="font-mono">{strategyRef?.definition_sha256 ?? "—"}</dd>
    <dt>Selector y apuesta</dt><dd>{definition ? `${definition.selector} · ${definition.staking}` : "No disponible"}</dd>
    {definition && <><dt>Definición guardada</dt><dd><pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all">{JSON.stringify(definition, null, 2)}</pre></dd></>}
    <dt>Dataset SHA-256</dt><dd className="font-mono">{identity.dataset_sha256}</dd>
    <dt>Fuente SHA-256</dt><dd className="font-mono">{identity.source_sha256}</dd>
    <dt>Fuente canónica SHA-256</dt><dd className="font-mono">{identity.canonical_sha256}</dd>
    <dt>Archivo autenticado</dt><dd>{identity.archive_bound ? `Verificado · historial ${identity.archive_history_sha256}` : "No aplica a esta estrategia"}</dd>
    <dt>Restricciones solicitadas</dt><dd><code>{JSON.stringify(admission.requested_constraints)}</code></dd>
    <dt>Restricciones efectivas</dt><dd><code>{JSON.stringify(admission.effective_constraints)}</code></dd>
    <dt>Política de ejecución</dt><dd>Revisión {admission.policy_revision} · <code>{JSON.stringify(admission.policy)}</code></dd>
    <dt>Versión de código</dt><dd className="font-mono">{data.sources.code_version}</dd>
  </dl></div>;
}

function RunView({ data, run }: { data: ExperimentSummary; run: AnyRunSummary }) {
  const { search } = useLocation();
  const betQuery = new URLSearchParams(search).get("bet");
  const requestedBet = betQuery && /^(0|[1-9]\d*)$/.test(betQuery) ? Number(betQuery) : 0;
  const betTotal = run.result ? isProfileRun(run) ? run.result.bet_draws : run.result.bets_count : 0;
  const initialBet = Number.isSafeInteger(requestedBet) && requestedBet < betTotal ? requestedBet : 0;
  const [tab, setTab] = useState<Tab>(betQuery != null ? "Apuestas" : "Resultado");
  const [cursor, setCursor] = useState(initialBet);
  const [offset, setOffset] = useState(pageOffset(initialBet));
  const [page, setPage] = useState<ReplayPage | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const cache = useRef(new Map<number, ReplayPage>());
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const money = isProfileExperiment(data) ? (amount: number) => profileMoney(data, amount) : formatDOP;
  const total = run.result ? isProfileRun(run) ? run.result.bet_draws : run.result.bets_count : 0;
  const runName = isProfileBatchRun(run) ? run.strategy.name ?? `Estrategia ${run.ordinal + 1}` : isProfileExperiment(data) ? data.display.name : data.request.strategies[run.ordinal]?.name ?? `Ejecución ${run.ordinal + 1}`;
  const [trajectoryMaximum, setTrajectoryMaximum] = useState<number | null>(null);
  const capital = isProfileExperiment(data) ? data.display.capital : data.request.conditions.capital;
  const goal = isProfileExperiment(data) ? data.display.goal : data.request.conditions.goal;
  const drawCount = run.result ? isProfileRun(run) ? run.result.bet_draws : run.result.bets_count : null;
  const outcome = run.result?.outcome;
  const delta = run.result?.delta;
  const deltaVariant: FigureVariant = delta == null || delta === 0 ? "neutral" : delta > 0 ? "positive" : "negative";
  const closeReason = run.result ? isProfileBatchRun(run) ? stopCategoryLabel(run.result.stop_category) : isProfileRun(run) ? profileCloseReason(run.result) : <StatusLabel kind="outcome" value={run.result.outcome} /> : "Todavía no hay un resultado guardado.";

  useEffect(() => {
    if (!run.result) { setPage(null); setError(""); setLoading(false); return; }
    const cached = cache.current.get(offset);
    if (cached && retry === 0) { setPage(cached); setError(""); setLoading(false); return; }
    let live = true;
    setLoading(true); setError("");
    void apiClient.getReplay(data.id, run.ordinal, offset, PAGE_SIZE).then((result) => {
      if (!live) return;
      // Keep at most three bounded pages per mounted run; never eagerly download history.
      cache.current.delete(offset);
      cache.current.set(offset, result);
      if (cache.current.size > 3) cache.current.delete(cache.current.keys().next().value!);
      setPage(result); setLoading(false);
    }).catch((cause: unknown) => { if (live) { setError(replayError(cause)); setLoading(false); setPlaying(false); } });
    return () => { live = false; };
  }, [data.id, run.ordinal, !!run.result, offset, retry]);

  useEffect(() => {
    if (!playing || !run.result || !page || loading || error || cursor >= total - 1) {
      if (playing && cursor >= total - 1) setPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      setCursor((current) => {
        const next = replayIndex(current, 1, total);
        setOffset(pageOffset(next));
        return next;
      });
    }, 1000 / speed);
    return () => clearTimeout(timer);
  }, [playing, !!run.result, page, loading, error, cursor, total, speed]);

  function move(step: number) {
    const next = replayIndex(cursor, step, total);
    setCursor(next); setOffset(pageOffset(next));
  }
  function selectTab(next: Tab) { setTab(next); setPlaying(false); }
  function onTabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault(); selectTab(tabs[next]); tabRefs.current[next]?.focus();
  }
  const visiblePage = page?.offset === offset ? page : null;
  const current = visiblePage?.items[cursor - offset];
  return <section className="mt-6" aria-label={`Ejecución ${run.ordinal + 1}`}>
    {run.result && <>
      <section aria-label="Veredicto" className="ledger-block">
        <h2 className="ledger-verdict-title">{verdictPhrase(outcome, run.status)}</h2>
        <p className="mt-3 text-lg font-medium">{financialConclusion(run)}</p>
        <div className="ledger-verdict-figures">
          <Stat label="Saldo final" value={money(run.result.final_balance)} variant={run.result.final_balance > capital ? "positive" : run.result.final_balance < capital ? "negative" : "neutral"} />
          <Stat label="Mejor saldo" value={trajectoryMaximum == null ? "—" : money(trajectoryMaximum)} variant="neutral" />
          <Stat label="Sorteos jugados" value={<Figure value={drawCount ?? "—"} />} />
        </div>
        <p>Motivo de cierre: {closeReason}</p>
        <p className="ledger-caveat">Esto simula con datos históricos: no predice resultados futuros ni garantiza rentabilidad.</p>
        <p className="text-sm">Tu ganancia o pérdida está en «Cambio respecto del inicio», más abajo.</p>
      </section>
      <dl className="data-list border-b border-border py-3">
        <dt>Capital inicial</dt><dd className="data-list-numeric">{money(capital)}</dd>
        <dt>Meta de saldo</dt><dd className="data-list-numeric">{money(goal)}</dd>
        <dt>Duración</dt><dd className="data-list-numeric">{isProfileRun(run) ? `${run.result.elapsed_draws} sorteos transcurridos` : `${run.result.bets_count} sorteos jugados`}</dd>
        <dt>{FIELD_LABEL_DELTA}</dt><dd className="data-list-numeric" aria-describedby="detail-delta-help"><Figure value={money(delta!)} variant={deltaVariant} align="right" /><span id="detail-delta-help" className="field-help block text-right">{FIELD_HELP_DELTA}</span></dd>
      </dl>
    </>}
    {!run.result && <>
      <section aria-label="Veredicto" className="ledger-block">
        <h2 className="ledger-verdict-title">Todavía no hay un resultado guardado</h2>
        <p className="mt-3">El resultado aún no está disponible; el estado de la ejecución aparece junto al nombre.</p>
        <p className="ledger-caveat">Esto simula con datos históricos: no predice resultados futuros ni garantiza rentabilidad.</p>
      </section>
      <dl className="data-list border-b border-border py-3">
        <dt>Capital inicial</dt><dd className="data-list-numeric">{money(capital)}</dd>
        <dt>Meta de saldo</dt><dd className="data-list-numeric">{money(goal)}</dd>
        <dt>Duración</dt><dd className="data-list-numeric">Sin resultado guardado</dd>
      </dl>
    </>}
    <div className="flex flex-wrap items-center gap-4">{data.runs.length === 1 && <StatusLabel kind="execution" value={run.status} />}</div>
    <div role="tablist" aria-label="Secciones del detalle" className="mt-6 flex flex-wrap gap-2 border-b border-border">
      {tabs.map((name, index) => <button key={name} ref={(node) => { tabRefs.current[index] = node; }} type="button" role="tab" id={`detail-tab-${index}`} aria-controls={`detail-panel-${index}`} aria-selected={tab === name} tabIndex={tab === name ? 0 : -1} onClick={() => selectTab(name)} onKeyDown={(event) => onTabKey(event, index)} className={`min-h-control px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${tab === name ? "border-b-2 border-accent text-text" : "text-text-secondary hover:text-text"}`}>{name}</button>)}
    </div>
    <div role="tabpanel" id={`detail-panel-${tabs.indexOf(tab)}`} aria-labelledby={`detail-tab-${tabs.indexOf(tab)}`} tabIndex={0} className="pt-5">
      {tab === "Parámetros y datos" ? (
        <Disclosure summary="Cómo se hizo"><dl className="data-list mb-4"><dt>Nombre de ejecución</dt><dd>{runName}</dd></dl>{isProfileBatchExperiment(data) ? <ProfileBatchParameters data={data} run={run} /> : isProfileExperiment(data) ? <ProfileParameters data={data} run={run} /> : !isProfileRun(run) ? <Parameters data={data} run={run} /> : null}</Disclosure>
      ) : !run.result ? (
        <div><p role="status">Esta ejecución todavía no tiene un resultado guardado. Volvé a la pestaña Resultado más tarde; el estado se actualiza automáticamente.</p>{isProfileBatchRun(run) && <><p className="mt-2 text-sm">{stopCategoryLabel(run.stop_category)}</p><Disclosure summary="Detalles técnicos"><dl className="data-list pt-2"><dt>Categoría de parada (código)</dt><dd>{run.stop_category}</dd><dt>Motivo informado</dt><dd>{run.stop_reason}</dd><dt>Código de parada</dt><dd>{run.stop_code}</dd>{run.error && <><dt>Error</dt><dd>{run.error}</dd></>}</dl></Disclosure></>}</div>
      ) : tab === "Resultado" ? (
        <div>
          {isProfileBatchRun(run) && !run.result.complete && <p role="status" className="mb-4 text-sm">Resultado incompleto · {stopCategoryLabel(run.result.stop_category)}. Revisá el motivo antes de comparar esta simulación.</p>}
          <SectionHeader title="Evolución del saldo" />
          <RunTrajectory id={data.id} ordinal={run.ordinal} name={runName} goal={goal} money={money} onLoad={(_ordinal, trajectory) => setTrajectoryMaximum(trajectory.maximum.balance)} onSelect={(index) => { setPlaying(false); setCursor(index); setOffset(pageOffset(index)); setTab("Apuestas"); }} />
          <div className="border-t border-border pt-5" role="region" aria-label="Reproducción visual">
            <h3 className="section-header">Reproducción visual</h3>
            <p aria-live="polite" className="mb-3 text-sm">Sorteo mostrado: {total ? `${cursor + 1} de ${total}` : "sin apuestas"}{current ? ` · ${storedDate(current.label)} · saldo en ese sorteo ${money(current.balance)}` : ""}</p>
            <div className="flex flex-wrap items-center gap-2">
              <button className={button} type="button" disabled={!total || cursor === 0} onClick={() => move(-1)}>Sorteo anterior</button>
              <button className={button} type="button" disabled={!total || cursor >= total - 1 || (typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches)} onClick={() => setPlaying(!playing)}>{playing ? "Pausar" : "Reproducir"}</button>
              <button className={button} type="button" disabled={!total || cursor >= total - 1} onClick={() => move(1)}>Siguiente sorteo</button>
              <label htmlFor="replay-speed" className="text-sm">Velocidad</label><select id="replay-speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))} className="min-h-control border border-border-control bg-field px-2 text-sm"><option value={0.5}>0,5×</option><option value={1}>1×</option><option value={2}>2×</option></select>
            </div>
            {typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches && <p className="mt-2 text-sm">Movimiento reducido: usá anterior y siguiente.</p>}
          </div>
          {visiblePage && visiblePage.items.length > 0 && (isProfileReplay(visiblePage) && isProfileExperiment(data) ? <DataTable caption="Libro de sorteos" columns={profileLedgerColumns(data)} rows={visiblePage.items} getRowKey={(bet) => bet.label} /> : !isProfileReplay(visiblePage) && <DataTable caption="Libro de sorteos" columns={ledgerColumns} rows={visiblePage.items} getRowKey={(bet) => bet.label} />)}
          {visiblePage && visiblePage.items.length === 0 && <p role="status">Todavía no hay sorteos registrados. La simulación puede seguir en curso.</p>}
          <FinancialMetrics result={run.result} money={money} />
          {isProfileBatchRun(run) && <Disclosure summary="Detalles técnicos"><dl className="data-list break-all pt-2"><dt>Versión de solicitud</dt><dd>{isProfileBatchExperiment(data) ? `Perfil v${data.request.schema_version}` : "No disponible"}</dd><dt>Versión del resultado</dt><dd>{run.result.schema_version}</dd><dt>Categoría de parada (código)</dt><dd>{run.result.stop_category}</dd><dt>Motivo informado</dt><dd>{run.result.stop_reason}</dd><dt>Código de parada</dt><dd>{run.stop_code}</dd><dt>Índice de inicio en la fuente</dt><dd>{run.result.start_draw_index}</dd></dl></Disclosure>}
        </div>
      ) : (
        <div>
          {current && <p role="status">Sorteo seleccionado {cursor + 1}: {storedDate(current.label)} · {money(current.balance)}</p>}
          {visiblePage && visiblePage.items.length > 0 && (isProfileReplay(visiblePage) && isProfileExperiment(data) ? <DataTable caption="Apuestas del experimento" columns={profileColumns(data, isProfileBatchRun(run))} rows={visiblePage.items} getRowKey={(bet) => bet.label} /> : !isProfileReplay(visiblePage) && <DataTable caption="Apuestas del experimento" columns={columns} rows={visiblePage.items} getRowKey={(bet) => bet.label} />)}
          {visiblePage && visiblePage.items.length === 0 && <p role="status">No hay sorteos registrados en esta página.</p>}
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm"><span>Mostrando {total ? offset + 1 : 0}–{Math.min(offset + (visiblePage?.items.length ?? 0), total)} de {total}</span><button type="button" className={button} disabled={offset === 0} onClick={() => { const previous = Math.max(0, offset - PAGE_SIZE); setPlaying(false); setOffset(previous); setCursor(previous); }}>Página anterior</button><button type="button" className={button} disabled={offset + PAGE_SIZE >= total} onClick={() => { const next = offset + PAGE_SIZE; setPlaying(false); setOffset(next); setCursor(next); }}>Página siguiente</button></div>
        </div>
      )}
      {loading && <Loading rows={3} label="Cargando sorteos…" className="mt-3" />}
      {error && <p role="alert" className="mt-3">{error} Los datos guardados no se modificaron. Podés volver a cargar esta página de sorteos. <button type="button" className="btn btn-tertiary" onClick={() => setRetry((value) => value + 1)}>Reintentar página</button></p>}
    </div>
    {tabs.map((name, index) => name !== tab && <div key={name} role="tabpanel" id={`detail-panel-${index}`} aria-labelledby={`detail-tab-${index}`} hidden />)}
  </section>;
}

export function DetailPage() {
  const { id = "" } = useParams();
  const { search } = useLocation();
  const query = new URLSearchParams(search);
  const requestedRun = query.get("run");
  const fromComparison = query.get("from") === "comparison";
  const [snapshot, setSnapshot] = useState<ExperimentSummary | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [ordinal, setOrdinal] = useState<number | null>(null);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    setError(""); setOrdinal(null);
    async function load() {
      try {
        const next = await apiClient.getExperiment(id);
        if (!live) return;
        setSnapshot(next); setError("");
        if (["pending", "held", "running"].includes(next.status)) timer = setTimeout(load, 5000);
      } catch (cause) {
        if (!live) return;
        setError(detailError(cause));
        // A temporary network failure says nothing about the server's execution state.
        if (!(cause instanceof ApiError && cause.status === 404)) timer = setTimeout(load, 5000);
      }
    }
    void load();
    return () => { live = false; clearTimeout(timer); };
  }, [id, retry]);
  const data = snapshot?.id === id ? snapshot : null;
  const target = requestedRun !== null && /^(0|[1-9]\d*)$/.test(requestedRun) ? Number(requestedRun) : null;
  const requested = data?.runs.find((run) => run.ordinal === target);
  const selected = data?.runs.find((run) => run.ordinal === ordinal) ?? requested ?? data?.runs[0];
  return <div>
    {!data && !error && <Loading rows={4} label="Cargando el estado de la simulación…" className="my-4" />}
    {error && <div role="alert" className="mb-4 border-y border-border py-4"><p>{error}</p><p>Tu información guardada se conserva. Podés consultar la cola y volver a intentar la carga.</p><button type="button" className="btn btn-secondary" onClick={() => setRetry((value) => value + 1)}>Volver a cargar</button></div>}
    {data && <>
      {selected && <RunView key={`${id}:${selected.ordinal}`} data={data} run={selected} />}
      {requestedRun !== null && !requested && <p role="status" className="mb-4">Esa ejecución no existe; se muestra la primera.</p>}
      <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-border pt-4"><h2 className="font-heading text-2xl">{isProfileBatchExperiment(data) ? data.display.name : data.request.name}</h2><StatusLabel kind="execution" value={data.status} /></div>
      {(data.status === "running" || data.status === "pending" || data.status === "held") && <p className="mt-3 text-sm text-text-secondary">El cálculo puede continuar en el servidor; comprobá el estado desde la cola antes de reintentar.</p>}
      {data.runs.length > 1 && <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Elegir ejecución">
        {data.runs.map((run) => <button key={run.ordinal} type="button" aria-pressed={selected?.ordinal === run.ordinal} className={`${button} ${selected?.ordinal === run.ordinal ? "border-accent text-accent" : ""}`} onClick={() => setOrdinal(run.ordinal)}>{run.ordinal + 1}. {isProfileBatchRun(run) ? run.strategy.name ?? `Estrategia ${run.ordinal + 1}` : isProfileExperiment(data) ? data.display.name : data.request.strategies[run.ordinal]?.name ?? "Estrategia"} <StatusLabel kind="execution" value={run.status} className="ledger-chip-compact ml-2" /></button>)}
      </div>}
      <nav aria-label="Navegación del experimento" className="mt-6 flex flex-wrap gap-2 text-sm">
        <Link className="btn btn-tertiary" to="/experimentos">Volver a simulaciones</Link>
        <Link className="btn btn-primary" to={`/experimentos/${encodeURIComponent(id)}/comparacion`}>{fromComparison ? "Volver a comparación" : "Comparar simulaciones"}</Link>
      </nav>
    </>}
  </div>;
}
