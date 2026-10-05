import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Block, Button, Chip, Disclosure, EmptyState, ErrorBanner, Field, Figure, Loading, Money, OrderSummary, SectionHeader, Stat, Verdict } from "./index";

const styles = readFileSync(resolve(import.meta.dirname, "../../styles/index.css"), "utf8");

describe("ledger blocks and headers", () => {
  it("renders a flat document block with a hairline contract class", () => {
    const { container } = render(<Block aria-label="Extracto">Contenido</Block>);
    expect(screen.getByRole("region", { name: "Extracto" }).classList.contains("ledger-block")).toBe(true);
    expect(container.firstElementChild?.classList.contains("ledger-block-top-rule")).toBe(false);
  });

  it("supports top-rule blocks and serif section headers with meaningful sequence labels", () => {
    const { container } = render(<><Block border="top">Fila</Block><SectionHeader kicker="ORDEN" number="02" title="Selección" /></>);
    expect(container.querySelector(".ledger-block-top-rule")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Selección" })).toBeTruthy();
    expect(container.querySelector("h2 span[aria-hidden='true']")?.textContent).toBe("02 ");
    expect(screen.getByText("ORDEN").classList.contains("ledger-kicker")).toBe(true);
  });
});

describe("ledger figures and states", () => {
  it("formats Dominican pesos and uses mono tabular figure classes", () => {
    render(<Money amount={2800} align="right" variant="positive" />);
    const figure = screen.getByText("RD$2,800");
    expect(figure.classList.contains("ledger-figure")).toBe(true);
    expect(figure.classList.contains("ledger-figure-right")).toBe(true);
    expect(figure.classList.contains("ledger-money-positive")).toBe(true);
  });

  it("renders generic figures, stat label/value/delta and semantic variants", () => {
    render(<><Figure value="42%" variant="negative" /><Stat label="Probabilidad" value="18%" delta="−2 puntos" variant="positive" /></>);
    expect(screen.getByText("42%").classList.contains("ledger-money-negative")).toBe(true);
    expect(screen.getByText("Probabilidad").classList.contains("ledger-label")).toBe(true);
    expect(screen.getByText("18%").classList.contains("ledger-figure")).toBe(true);
    expect(screen.getByText("−2 puntos")).toBeTruthy();
  });

  it.each(["success", "neutral", "warning", "danger", "info"] as const)("renders %s chip with color-only text/border class", (variant) => {
    render(<Chip variant={variant}>En curso</Chip>);
    const chip = screen.getByText("En curso");
    expect(chip.classList.contains("ledger-chip")).toBe(true);
    expect(chip.classList.contains(`ledger-chip-${variant}`)).toBe(true);
    const variantRule = styles.match(new RegExp(`\\.ledger-chip-${variant}\\s*\\{([^}]+)\\}`))?.[1] ?? "";
    expect(variantRule).toContain("color:");
    expect(variantRule).not.toMatch(/background(?:-color)?:/);
  });

  it("keeps chip fills transparent and figures tabular", () => {
    const chipRule = styles.match(/\.ledger-chip\s*\{([^}]+)\}/)?.[1] ?? "";
    const figureRule = styles.match(/\.ledger-figure\s*\{([^}]+)\}/)?.[1] ?? "";
    expect(chipRule).toMatch(/background:\s*transparent/);
    expect(figureRule).toContain("font-variant-numeric: tabular-nums");
    expect(figureRule).toContain('font-feature-settings: "tnum"');
  });
});

describe("ledger controls", () => {
  it("renders primary, secondary and ghost buttons with native disabled semantics", () => {
    render(<><Button variant="primary">Crear</Button><Button variant="secondary">Volver</Button><Button variant="ghost" disabled>Más</Button></>);
    expect(screen.getByRole("button", { name: "Crear" }).classList.contains("ledger-button-primary")).toBe(true);
    expect(screen.getByRole("button", { name: "Volver" }).classList.contains("ledger-button-secondary")).toBe(true);
    expect((screen.getByRole("button", { name: "Más" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("wires field label, hint, error and optional detail descriptions accessibly", () => {
    render(<Field id="capital" label="Capital inicial" hint="Pesos enteros" error="Ingresá un capital válido" detail="Mínimo RD$1" />);
    const control = screen.getByRole("textbox", { name: "Capital inicial" });
    expect(control.getAttribute("aria-invalid")).toBe("true");
    expect(control.getAttribute("aria-describedby")).toBe("capital-hint capital-error capital-detail");
    expect(screen.getByText("Pesos enteros").id).toBe("capital-hint");
    expect(screen.getByText("Ingresá un capital válido").id).toBe("capital-error");
    expect(screen.getByText("Mínimo RD$1").id).toBe("capital-detail");
  });

  it("provides a native details disclosure for advanced information", () => {
    render(<Disclosure summary="Avanzado">Contenido técnico</Disclosure>);
    const disclosure = screen.getByText("Avanzado").closest("details");
    expect(disclosure).not.toBeNull();
    expect(disclosure?.open).toBe(false);
    fireEvent.click(screen.getByText("Avanzado"));
    expect(within(disclosure as HTMLElement).getByText("Contenido técnico")).toBeTruthy();
  });
});

describe("ledger feedback states", () => {
  it("renders an empty state with one next-step action and optional hint", () => {
    const action = vi.fn();
    render(<EmptyState title="Sin simulaciones" description="Creá una para empezar." actionLabel="Crear simulación" onAction={action} hint="Podés cambiarla luego." />);
    expect(screen.getByRole("heading", { name: "Sin simulaciones" })).toBeTruthy();
    expect(screen.getByText("Podés cambiarla luego.")).toBeTruthy();
    expect(screen.getAllByRole("button")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Crear simulación" }));
    expect(action).toHaveBeenCalledOnce();
  });

  it("names the error cause and recovery and only confirms preserved data when told so", () => {
    render(<ErrorBanner cause="No se pudo guardar." recovery="Revisá la conexión y reintentá." actionLabel="Reintentar" onAction={() => undefined} detail="Código interno 422" />);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("No se pudo guardar.");
    expect(alert.textContent).toContain("Revisá la conexión y reintentá.");
    expect(alert.textContent).not.toContain("Tu información se conserva.");
    expect(within(alert).getByRole("button", { name: "Reintentar" })).toBeTruthy();
    expect(screen.getByText("Código interno 422").closest("details")?.open).toBe(false);
  });

  it("states that data is preserved only when explicitly flagged", () => {
    render(<ErrorBanner preserved cause="No se pudo cargar." recovery="Reintentá." actionLabel="Reintentar" onAction={() => undefined} />);
    expect(screen.getByRole("alert").textContent).toContain("Tu información se conserva.");
  });

  it("uses static skeleton rows and an accessible status announcement", () => {
    const { container } = render(<Loading rows={3} label="Cargando simulaciones…" />);
    expect(screen.getByRole("status").textContent).toBe("Cargando simulaciones…");
    expect(container.querySelectorAll(".ledger-skeleton-row")).toHaveLength(3);
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });
});

describe("signature components", () => {
  it("leads with a verdict, three monetary figures, close reason and simulation caveat", () => {
    render(<Verdict phrase="Meta alcanzada" figures={[{ label: "Capital", amount: 1000 }, { label: "Saldo final", amount: 1400, variant: "positive" }, { label: "Duración", amount: 12 }]} closeReason="La meta se alcanzó en el sorteo 12." />);
    const verdict = screen.getByRole("region", { name: "Veredicto" });
    expect(within(verdict).getByRole("heading", { name: "Meta alcanzada", level: 2 })).toBeTruthy();
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(within(verdict).getAllByText(/^RD\$/)).toHaveLength(3);
    expect(within(verdict).getByText("La meta se alcanzó en el sorteo 12.")).toBeTruthy();
    expect(verdict.textContent).toContain("Esto simula escenarios");
  });

  it("renders a count figure without the RD$ prefix", () => {
    render(<Verdict phrase="Meta alcanzada" figures={[{ label: "Capital", amount: 1000 }, { label: "Saldo final", amount: 1400 }, { label: "Sorteos jugados", amount: 12, kind: "count" }]} closeReason="Cierre." />);
    const verdict = screen.getByRole("region", { name: "Veredicto" });
    expect(within(verdict).getAllByText(/^RD\$/)).toHaveLength(2);
    expect(within(verdict).getByText("12")).toBeTruthy();
  });

  it("accepts a custom order caveat replacing the default", () => {
    render(<OrderSummary capital={1000} goal={1500} duration="30 sorteos" coverage="25 números" caveat="Texto propio." />);
    expect(screen.getByText("Texto propio.")).toBeTruthy();
    expect(screen.queryByText(/Esto simula escenarios/)).toBeNull();
  });

  it("renders each order label and value as a separate cell, with the selection on its own row", () => {
    render(<OrderSummary capital={2000} goal={2800} duration="12 sorteos" coverage="Fríos: números que menos salieron" />);
    const summary = screen.getByRole("region", { name: "Resumen de la orden" });
    const cells = Array.from(summary.querySelectorAll(".ledger-summary-cell"));
    expect(cells).toHaveLength(3);
    expect(cells.map((cell) => cell.querySelector(".ledger-label")?.textContent)).toEqual(["Capital", "Meta de saldo", "Duración"]);
    expect(cells[0].textContent).toMatch(/^Capital.*2[.,]000$/);
    const selection = summary.querySelector(".ledger-summary-selection")!;
    expect(selection.querySelector(".ledger-label")?.textContent).toBe("Cobertura");
    expect(selection.querySelector("p")?.textContent).toBe("Fríos: números que menos salieron");
    expect(cells.some((cell) => cell.contains(selection))).toBe(false);
  });

  it("shows all live order figures and keeps the caveat visible", () => {
    const { rerender } = render(<OrderSummary capital={1000} goal={1500} duration="30 sorteos" coverage="25 números" />);
    const summary = screen.getByRole("region", { name: "Resumen de la orden" });
    expect(summary.textContent).toContain("Capital");
    expect(summary.textContent).toContain("Meta de saldo");
    expect(summary.textContent).toContain("Duración");
    expect(summary.textContent).toContain("Cobertura");
    expect(summary.textContent).toContain("Esto simula escenarios");
    rerender(<OrderSummary capital={2000} goal={2800} duration="40 sorteos" coverage="50 números" />);
    expect(screen.getByRole("region", { name: "Resumen de la orden" }).textContent).toContain("RD$2,000");
  });
});
