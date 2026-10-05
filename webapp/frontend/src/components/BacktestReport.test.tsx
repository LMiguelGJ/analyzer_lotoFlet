import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { BacktestReport as BacktestReportData } from "../api/types";
import { BacktestReport } from "./BacktestReport";

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
  });

  it("keeps unavailable report values literal instead of inventing zeroes", () => {
    render(<BacktestReport report={{ ...report, goal_rate: null, neto_medio: null }} />);
    expect(screen.getAllByText("Sin dato")).toHaveLength(4);
  });
});
