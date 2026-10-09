import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { apiClient } from "../api/client";
import type { BacktestReport as BacktestReportData } from "../api/types";
import { BacktestReport } from "./BacktestReport";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient,
    getBacktestSessions: vi.fn(), getBacktestSessionBets: vi.fn() } };
});

const styles = readFileSync(resolve(import.meta.dirname, "../styles/index.css"), "utf8");

const report: BacktestReportData = {
  id: "run-1", name: "Prueba histórica", created_at: "2026-10-01T00:00:00Z",
  reached_goal: 681, completed: 963, goal_rate: 70.7, quiebres: 282, neto_medio: 10.3, incomplete: 1,
  window: { bets: 1234, wagered: 12345, paid: 13000, sessions: 964, incomplete: 1 },
  config: {
    name: "Prueba histórica",
    strategy: { name: "Transición", selector: "system", system: "transition", coverage: 1, staking: "bold" },
    game: { numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], min_stake: 1 },
    conditions: { capital: 2000, goal: 2800 },
    inputs: { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) },
  },
};

describe("BacktestReport", () => {
  it("shows the four acceptance metrics, totals, censored tail, config and caveat", () => {
    render(<BacktestReport report={report} />);
    const frame = screen.getByRole("region", { name: "Informe histórico" });
    expect(frame).toHaveAttribute("data-result-family", "historical-aggregate");
    expect(within(frame).getByText("Histórico")).toBeInTheDocument();
    expect(within(frame).getByText(`Informe guardado · ${report.created_at}`)).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Llegaron/Completas" })).toBeInTheDocument();
    const table = within(screen.getByRole("table"));
    expect(table.getByText("681 / 963")).toBeInTheDocument();
    expect(table.getByText("70,7%")).toBeInTheDocument();
    expect(table.getByText("282")).toBeInTheDocument();
    expect(table.getByText("+RD$10,3")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Totales de la ventana histórica" })).toBeInTheDocument();
    expect(screen.getByText(/1 sesión histórica inconclusa/)).toBeInTheDocument();
    expect(screen.getByText(/Simula con datos históricos: no predice resultados futuros ni garantiza rentabilidad\./)).toBeInTheDocument();
    expect(table.getByText("Transición")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sesiones y apuestas" })).toBeInTheDocument();
    expect(screen.getByText("Detalle no almacenado")).toBeInTheDocument();
  });

  it("keeps historical caveat ink dim despite report paragraph styling", () => {
    render(<BacktestReport report={report} />);
    expect(screen.getByText("Simula, no predice ni garantiza rentabilidad")).toHaveClass("backtest-caveat");
    expect(styles).toContain(".backtest-report p.backtest-caveat { color: var(--bf-legend-dim); }");
  });

  it("uses the incumbent money format for native saved sessions and bets", async () => {
    const user = userEvent.setup();
    const trace = { version: 1 as const, status: "complete" as const, reason: null,
      unit: "native-RD$-integer" as const, total_sessions: 1, stored_sessions: 1,
      total_bets: 1, stored_bets: 1, source_window: null,
      limits: { bytes: 2097152, bets: 10000, sessions: 1000 } };
    const session = { ordinal: 0, outcome: "reached_goal" as const, final_balance: 3407,
      bets_count: 1, first_bet: { label: "2025-01-01 05:10", source_index: null, minute: null },
      last_bet: { label: "2025-01-01 05:10", source_index: null, minute: null } };
    vi.mocked(apiClient.getBacktestSessions).mockResolvedValue({ id: report.id, trace,
      total: 1, offset: 0, limit: 20, items: [session] });
    vi.mocked(apiClient.getBacktestSessionBets).mockResolvedValue({ id: report.id, ordinal: 0,
      trace, session, total: 1, offset: 0, limit: 20,
      items: [{ label: "2025-01-01 05:10", bet_index: 0, source_index: null, minute: null,
        numbers: [17], per_number: 7, wagered: 7, results: [17, 0, 0, 0, 0],
        paid: 1407, balance: 3407 }] });
    const { rerender } = render(<BacktestReport report={{ ...report, trace }} />);
    await user.click(await screen.findByRole("button", { name: "Ver apuestas de la sesión 1" }));
    const ledger = within(await screen.findByRole("table", { name: "Apuestas registradas de la sesión 1" }));
    expect(ledger.getAllByText("RD$7,0")).toHaveLength(2);
    expect(ledger.getByText("RD$1.407,0")).toBeInTheDocument();
    expect(ledger.getByText("RD$3.407,0")).toBeInTheDocument();
    expect(ledger.queryByText("RD$34,1")).not.toBeInTheDocument();
    expect(screen.getByText(/saldo final RD\$3.407,0/)).toBeInTheDocument();
    const exact = "9007199254740993";
    vi.mocked(apiClient.getBacktestSessions).mockResolvedValue({ id: report.id, trace,
      total: 1, offset: 0, limit: 20, items: [{ ...session, final_balance: exact }] });
    rerender(<BacktestReport report={{ ...report, name: "Nuevo informe exacto", trace }} />);
    expect(await screen.findByText(/saldo final RD\$9.007.199.254.740.993,0/)).toBeInTheDocument();
  });

  it("keeps unavailable report values literal instead of inventing zeroes", () => {
    render(<BacktestReport report={{ ...report, goal_rate: null, neto_medio: null }} />);
    expect(screen.getAllByText("Sin dato")).toHaveLength(4);
  });
});
