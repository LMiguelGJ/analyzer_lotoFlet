import { describe, expect, it } from "vitest";
import { runFixture, optionsFixture } from "./test-fixtures";
import { formatResultStrategy, resultSummaryRows, detailStatusCopy } from "./result-model";

describe("result model", () => {
  it("uses localized catalog labels and a safe fallback for unknown IDs", () => {
    expect(formatResultStrategy(runFixture.config.strategy, optionsFixture.systems)).toBe("Mezcla · Transición 60 % + Fríos 40 % · cobertura 10");
    expect(formatResultStrategy({ ...runFixture.config.strategy, components: [{ system: "internal-secret", percent: 100 }] }, [])).toContain("Sistema no disponible 100 %");
    expect(formatResultStrategy({ ...runFixture.config.strategy, kind: "parity", components: [] }, [])).toBe("Paridad · cobertura 10");
  });

  it("builds a signed ledger, preserves null means, and calls out incomplete sessions", () => {
    const report = { ...runFixture, summary: { ...runFixture.summary, totals: { ...runFixture.summary.totals, net: 25, paid: 35, wagered: 10, return_pct: 250, mean_net_closed: null, incomplete: 1 }, detail: { ...runFixture.summary.detail, total_sessions: 2, stored_sessions: 2 }, window: { ...runFixture.summary.window, draws: 10, ranked_draws: 6 } } };
    const rows: [string, string][] = resultSummaryRows(report);
    expect(rows.find(([label]) => label === "Neto")?.[1]).toBe("+RD$25");
    expect(rows.find(([label]) => label === "Retorno sobre lo apostado")?.[1]).toBe("+250,0 %");
    expect(rows.find(([label]) => label === "Neto medio por sesión cerrada")?.[1]).toBe("—");
    expect(rows.find(([label]) => label === "Incompletas")?.[1]).toBe("1 · incluidas en el neto total");
  });

  it("formats positive and negative outcomes, all closure counts, and decimal means", () => {
    const report = { ...runFixture, summary: { ...runFixture.summary, totals: { ...runFixture.summary.totals, sessions: 4, goal: 1, ruin: 1, limit: 1, incomplete: 1, net: 35, wagered: 100, paid: 135, return_pct: 35, mean_net_closed: 11.5 } } };
    const rows = resultSummaryRows(report);
    expect(rows.find(([label]) => label === "Neto")?.[1]).toBe("+RD$35");
    expect(rows.find(([label]) => label === "Retorno sobre lo apostado")?.[1]).toBe("+35,0 %");
    expect(rows.find(([label]) => label === "Neto medio por sesión cerrada")?.[1]).toBe("+RD$11,5");
    expect(rows.find(([label]) => label === "Metas")?.[1]).toBe("1");
    expect(rows.find(([label]) => label === "Quiebras")?.[1]).toBe("1");
    expect(rows.find(([label]) => label === "Límites")?.[1]).toBe("1");
    expect(rows.find(([label]) => label === "Incompletas")?.[1]).toBe("1 · incluidas en el neto total");
  });

  it("explains persisted detail caps and truncation without claiming missing tails", () => {
    expect(detailStatusCopy({ status: "partial", total_sessions: 14, stored_sessions: 14, total_bets: 80, stored_bets: 50, limits: { sessions: 50, bets: 50, bytes: 1000 } })).toMatch(/50 de 80 apuestas/);
    expect(detailStatusCopy({ status: "sessions_truncated", total_sessions: 14, stored_sessions: 10, total_bets: 80, stored_bets: 30, limits: { sessions: 10, bets: 50, bytes: 1000 } })).toMatch(/4 sesiones.*no se guardaron/);
  });
});
