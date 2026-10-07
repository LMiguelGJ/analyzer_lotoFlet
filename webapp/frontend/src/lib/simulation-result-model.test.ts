import { describe, expect, it } from "vitest";
import type { BacktestReport } from "../api/types";
import { historicalResultViewModel } from "./simulation-result-model";

const report: BacktestReport = {
  id: "historical-1", name: "Período", created_at: "2025-01-02T03:04:05Z",
  reached_goal: 2, completed: 3, goal_rate: 66.7, quiebres: 1, neto_medio: 12, incomplete: 1,
  window: { bets: 10, wagered: 100, paid: 112, sessions: 4, incomplete: 1 },
  config: {
    name: "Período", strategy: { name: "Transición", selector: "system", system: "transition", coverage: 1, staking: "flat" },
    game: { numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], min_stake: 1 },
    conditions: { capital: 100, goal: 200 }, inputs: { history_sha256: "history", rankings_sha256: "rankings" },
  },
};

describe("historicalResultViewModel", () => {
  it("preserves aggregate provenance, period identity, section semantics, and native denominators", () => {
    const before = structuredClone(report);
    const model = historicalResultViewModel(report);
    expect(model.family).toBe("historical-aggregate");
    expect(model.status).toBe("Histórico");
    expect(model.source).toContain(report.created_at);
    expect(model.sections).toEqual(["Resultados del escenario", "Totales de la ventana histórica", "Configuración usada"]);
    expect(model.payload).toBe(report);
    expect(report).toEqual(before);
    expect(report.completed).toBe(3);
    expect(report.window.sessions).toBe(4);
  });
});
