import { describe, expect, it } from "vitest";
import type { ReferenceLab } from "../../api/referenceLabs";
import { labTitle, stakeLabel, systemLabel } from "./lab-model";
const lab: ReferenceLab = { lab_id: "transicion_1_audaz", system: "transition", coverage: 1, stake_style: "bold", selection_kind: "ranking", capital: 2000, goal: 2800, prizes: [80, 8, 4, 2, 1], window: { start: "2025-09-02 05:10", end: "2026-09-25 18:20" }, duration_cap: null, editable: false };
describe("reference laboratory labels", () => {
  it("names the first direct laboratory page from its authoritative contract", () => {
    expect(labTitle(lab)).toBe("Transición · 1 número · Audaz");
  });
  it("describes fixed stake styles without implying editable presets", () => {
    expect(stakeLabel("ladder")).toBe("Escalera");
    expect(stakeLabel("flat")).toBe("Plana");
  });
  it("names every system a Leidsa laboratory can use instead of showing its raw id", () => {
    expect(["transition", "cold", "parity", "ensemble"].map(systemLabel)).toEqual(["Transición", "Fríos", "Paridad", "Ensemble"]);
    expect(systemLabel("freq_hist")).toBe("Frecuencia histórica");
    expect(systemLabel("freq_recent")).toBe("Frecuencia reciente");
    expect(systemLabel("decay")).toBe("Decaimiento");
    expect(systemLabel("overdue")).toBe("Ciclo vencido");
    expect(systemLabel("digits")).toBe("Terminaciones y decenas");
    expect(systemLabel("notebook")).toBe("notebook");
  });
});
