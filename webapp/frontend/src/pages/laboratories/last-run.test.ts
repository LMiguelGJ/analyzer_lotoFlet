import { describe, expect, it } from "vitest";
import { lastRunPresentation } from "./last-run";

const run = (total_net: number) => ({ id: "r", created_at: "2026-10-01T10:00:00.000Z", total_net, total_wagered: 1000, total_paid: 1000 + total_net });

describe("lastRunPresentation", () => {
  it("marks a positive net as a gain with arrow, sign and spoken label", () => {
    expect(lastRunPresentation(run(1234))).toEqual({ state: "gain", text: "▲ +RD$1.234", label: "Último resultado: ganancia de RD$1.234" });
  });
  it("marks a negative net as a loss", () => {
    expect(lastRunPresentation(run(-500))).toEqual({ state: "loss", text: "▼ −RD$500", label: "Último resultado: pérdida de RD$500" });
  });
  it("shows zero as neutral", () => {
    expect(lastRunPresentation(run(0))).toEqual({ state: "even", text: "= RD$0", label: "Último resultado: sin ganancia ni pérdida (RD$0)" });
  });
  it("says there are no runs for null, undefined or an unusable net", () => {
    for (const value of [null, undefined, run(Number.NaN)]) {
      expect(lastRunPresentation(value)).toEqual({ state: "none", text: "Sin corridas", label: "Último resultado: sin corridas guardadas" });
    }
  });
});
