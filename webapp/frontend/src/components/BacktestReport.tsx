import type { BacktestReport as BacktestReportData, StakingStyle } from "../api/types";
import { SimulationResultFrame } from "./SimulationResultFrame";
import { BacktestSessions } from "./BacktestSessions";
import { historicalResultViewModel } from "../lib/simulation-result-model";

const methods: Record<string, string> = {
  transition: "Transición", cold: "Fríos", select_interpretable: "Selector automático", mix: "Mezclas", ensemble: "Ensemble",
};
const stakingNames: Record<StakingStyle, string> = { flat: "Plana", ladder: "Escalera", bold: "Audaz" };
const stakingHelp: Record<StakingStyle, string> = {
  flat: "RD$1 a cada número.",
  ladder: "Recupera lo apostado + RD$10 al acertar el primero.",
  bold: "Apuesta para que un primer premio alcance la meta.",
};
const group = (value: string) => value.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
const integer = (value: number | null | undefined) => value == null ? "Sin dato" : group(String(value));
const fixedDecimal = (value: number) => {
  const [whole, fraction] = Math.abs(value).toFixed(1).split(".");
  return `${group(whole)},${fraction}`;
};
const decimal = (value: number | null | undefined, suffix = "") => value == null ? "Sin dato" : `${fixedDecimal(value)}${suffix}`;
const money = (value: number | string | null | undefined, signed = false) => {
  if (value == null) return "Sin dato";
  // Trace projections use exact decimal strings only for unsafe JS integers.
  if (typeof value === "string") return `RD$${group(value)},0`;
  return `${signed && value > 0 ? "+" : signed && value < 0 ? "−" : ""}RD$${fixedDecimal(value)}`;
};

function methodName(report: BacktestReportData) {
  const strategy = report.config.strategy;
  return strategy.selector === "parity" ? "Tu par/impar" : methods[strategy.system ?? ""] ?? "Sin dato";
}

export function BacktestReport({ report }: { report: BacktestReportData }) {
  const strategy = report.config.strategy;
  const staking = stakingNames[strategy.staking] ?? "Sin dato";
  const row = <tr>
    <th scope="row">{methodName(report)}</th>
    <td>{integer(strategy.coverage)}</td>
    <td>{staking}</td>
    <td>{integer(report.reached_goal)} / {integer(report.completed)}</td>
    <td>{decimal(report.goal_rate, "%")}</td>
    <td>{integer(report.quiebres)}</td>
    <td>{money(report.neto_medio, true)}</td>
  </tr>;
  return <SimulationResultFrame model={historicalResultViewModel(report)}>
    <article className="backtest-report space-y-5" aria-label={`Informe: ${report.name}`}>
    <p className="backtest-caveat">Simula, no predice ni garantiza rentabilidad</p>
    <p className="backtest-caveat backtest-context">Simula con datos históricos: no predice resultados futuros ni garantiza rentabilidad.</p>
    <section aria-label="Resultados del escenario">
      <div className="backtest-report-table overflow-x-auto">
        <table>
          <caption>Resultados del escenario · {report.name}</caption>
          <thead><tr><th scope="col">Método</th><th scope="col">Números</th><th scope="col">Apuesta</th><th scope="col">Llegaron/Completas</th><th scope="col">Meta</th><th scope="col">Quiebres</th><th scope="col">Neto medio</th></tr></thead>
          <tbody>{row}</tbody>
        </table>
      </div>
      <dl className="backtest-mobile-result" aria-label="Resultados del escenario">
        <div><dt>Método</dt><dd>{methodName(report)}</dd></div>
        <div><dt>Números</dt><dd>{integer(strategy.coverage)}</dd></div>
        <div><dt>Apuesta</dt><dd>{staking}</dd></div>
        <div><dt>Llegaron/Completas</dt><dd>{integer(report.reached_goal)} / {integer(report.completed)}</dd></div>
        <div><dt>Meta</dt><dd>{decimal(report.goal_rate, "%")}</dd></div>
        <div><dt>Quiebres</dt><dd>{integer(report.quiebres)}</dd></div>
        <div><dt>Neto medio</dt><dd>{money(report.neto_medio, true)}</dd></div>
      </dl>
      <details className="mt-3"><summary className="disclosure-summary">Qué significan estas cifras</summary>
        <dl className="backtest-definitions">
          <dt>Método</dt><dd>Regla que elige los números antes del siguiente resultado.</dd>
          <dt>Números</dt><dd>Cantidad de números distintos cubiertos en cada sorteo.</dd>
          <dt>Apuesta</dt><dd>{stakingHelp[strategy.staking] ?? "Sin dato"}</dd>
          <dt>Llegaron/Completas</dt><dd>Sesiones que alcanzaron la meta, divididas por sesiones terminadas en meta o quiebre.</dd>
          <dt>Meta</dt><dd>Porcentaje de sesiones completas que alcanzaron la meta; no es una probabilidad futura.</dd>
          <dt>Quiebres</dt><dd>Sesiones que no pudieron financiar la siguiente apuesta prescrita; puede quedar saldo.</dd>
          <dt>Neto medio</dt><dd>Saldo final menos capital inicial, promediado en sesiones completas.</dd>
        </dl>
      </details>
    </section>
    <section aria-labelledby="backtest-window-title" className="backtest-window">
      <h3 id="backtest-window-title">Totales de la ventana histórica</h3>
      <dl><div><dt>Sorteos apostados</dt><dd>{integer(report.window.bets)}</dd></div><div><dt>Apostado</dt><dd>{report.window.wagered == null ? "Sin dato" : `RD$${integer(report.window.wagered)}`}</dd></div><div><dt>Pagado</dt><dd>{report.window.paid == null ? "Sin dato" : `RD$${integer(report.window.paid)}`}</dd></div><div><dt>Sesiones iniciadas</dt><dd>{integer(report.window.sessions)}</dd></div></dl>
      <p>{integer(report.incomplete)} sesión histórica inconclusa al final de los datos; no se cuenta en tasas ni promedios de sesiones completas.</p>
    </section>
    <BacktestSessions report={report} formatMoney={money} />
    <section aria-labelledby="backtest-config-title" className="backtest-config">
      <h3 id="backtest-config-title">Configuración usada</h3>
      <p>{methodName(report)} · {integer(strategy.coverage)} números · {staking} · capital RD${integer(report.config.conditions.capital)} · meta RD${integer(report.config.conditions.goal)}</p>
      <p>Reglas del juego: {integer(report.config.game.numbers)} números posibles · {integer(report.config.game.positions)} posiciones · premios {report.config.game.prizes?.join(" / ") || "Sin dato"} · apuesta mínima RD${integer(report.config.game.min_stake)}.</p>
      <details><summary className="disclosure-summary">Detalles técnicos</summary><div className="space-y-2 break-all"><p>ID: <code>{report.id || "Sin dato"}</code></p><p>Historial SHA-256: <code>{report.config.inputs?.history_sha256 || "Sin dato"}</code></p><p>Rankings SHA-256: <code>{report.config.inputs?.rankings_sha256 || "Sin dato"}</code></p></div></details>
    </section>
    </article>
  </SimulationResultFrame>;
}
