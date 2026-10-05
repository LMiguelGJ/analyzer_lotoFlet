import { render, screen, waitFor } from "@testing-library/react";
// Contract coverage: F-LIST-026 flat labels with enum preservation and accessible stake/error help, including bare components.N errors.
import { describe, expect, it, vi } from "vitest";
import { StrategyEditor } from "./StrategyEditor";
import { newStrategy } from "../pages/new-experiment/model";
import type { Catalog } from "../api/types";

const catalog: Catalog = { game: { name: "Q80", numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], allows_repeats: true, minimum_stake: 1 }, systems: { cold: "Fríos", transition: "Transición" }, selectors: ["system", "blend", "random", "parity"], coverages: [1, 10, 50], parity_coverage: 50, starting_draws: [], starting_draws_total: 0, sources: { history_sha256: "", rankings_sha256: "", history_id: "", rankings_id: "", code_version: "" } };

describe("shared strategy vocabulary", () => {
  it("shows mapped selector and staking labels while keeping the saved enum values", () => {
    render(<StrategyEditor value={newStrategy(1)} index={0} catalog={catalog} errors={{}} onChange={vi.fn()} />);
    const selector = screen.getByRole("combobox", { name: "Método de la estrategia 1" });
    expect(selector).toHaveValue("system");
    expect(screen.getByRole("option", { name: "Un sistema de selección" })).toHaveValue("system");
    expect(screen.getByRole("option", { name: "Selección al azar reproducible" })).toHaveValue("random");
    const staking = screen.getByRole("combobox", { name: "Forma de ajustar la apuesta" });
    expect(staking).toHaveValue("flat");
    expect(staking).toHaveAccessibleDescription("Importe base constante por número.");
    expect(staking).toHaveAttribute("aria-describedby", "strategies.0.staking.help");
    expect(document.querySelectorAll(".ledger-control")).toHaveLength(0);
    expect(document.querySelector(".ledger-block")).toBeInTheDocument();
  });

  it("announces both the staking help and an error without dangling references", () => {
    render(<StrategyEditor value={newStrategy(1)} index={0} catalog={catalog} errors={{ "strategies.0.staking": "Elegí una modalidad válida." }} onChange={vi.fn()} />);
    const staking = screen.getByRole("combobox", { name: "Forma de ajustar la apuesta" });
    expect(staking).toHaveAccessibleDescription("Importe base constante por número. Elegí una modalidad válida.");
    expect(staking).toHaveAttribute("aria-describedby", "strategies.0.staking.help strategies.0.staking.error");
    expect(staking).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("combobox", { name: "Método de la estrategia 1" })).not.toHaveAttribute("aria-describedby");
  });
});

describe("progressive advanced disclosure", () => {
  it("opens advanced settings when an advanced field has a validation error", async () => {
    const { rerender } = render(<StrategyEditor value={newStrategy(1)} index={0} catalog={catalog} errors={{}} onChange={vi.fn()} progressiveDisclosure />);
    const disclosure = screen.getByText("Avanzado").closest("details")!;
    expect(disclosure).not.toHaveAttribute("open");
    rerender(<StrategyEditor value={newStrategy(1)} index={0} catalog={catalog} errors={{ "strategies.0.coverage": "Elegí una cobertura válida." }} onChange={vi.fn()} progressiveDisclosure />);
    await waitFor(() => expect(disclosure).toHaveAttribute("open"));
    expect(screen.getByRole("combobox", { name: "Cobertura de la estrategia 1" })).toHaveAttribute("aria-invalid", "true");
  });
});

describe("mix component errors", () => {
  it("shows a bare components.N server error and associates it with a focusable field", () => {
    render(<StrategyEditor value={{ ...newStrategy(1), selector: "blend" }} index={0} catalog={catalog} errors={{ "strategies.0.components.1": { message: "Componente rechazado", detail: "invalid component" } }} onChange={vi.fn()} />);
    expect(screen.getByText("Componente rechazado")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Sistema 2" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("combobox", { name: "Sistema 2" })).toHaveAttribute("aria-describedby", "strategies.0.components.1.error");
  });
});
