import { fireEvent, render, screen } from "@testing-library/react";
// Contract coverage: F-RESULT-006 backend-only financial values and unavailable/null handling; F-RESULT-007 money signs remain textual and neutral; F-RESULT-008 technical terminology remains folded.
import { describe, expect, it } from "vitest";
import { FinancialMetrics } from "./FinancialMetrics";

const money = (amount: number) => `RD$${amount}`;

function mount(overrides: Record<string, unknown> = {}, omitNet = false) {
  return render(<FinancialMetrics money={money} omitNet={omitNet} result={{
    wagered: 200,
    paid: 350,
    net: 150,
    roi: 0.75,
    return_per_wagered: 1.75,
    max_drawdown: 80,
    ...overrides,
  }} />);
}

describe("FinancialMetrics", () => {
  it("shows server-derived financial values and formats ratios as tabular figures", () => {
    mount();
    expect(screen.getByText("RD$200")).toBeInTheDocument();
    expect(screen.getByText("RD$350")).toBeInTheDocument();
    expect(screen.getByText("RD$150")).toHaveClass("ledger-figure");
    expect(screen.getByText("RD$150")).not.toHaveClass("ledger-money-positive", "ledger-money-negative");
    expect(screen.getByText("1.750000")).toHaveClass("ledger-figure");
    expect(screen.getByText("0.750000")).toHaveClass("ledger-figure");
    expect(screen.getByText("Detalles técnicos").closest("details")).not.toHaveAttribute("open");
  });

  it("keeps gains and losses textual and neutral, never coloring amounts or ratios", () => {
    mount({ net: -10, roi: -0.25, return_per_wagered: -0.5 });
    expect(screen.getByText("RD$-10")).toHaveClass("ledger-figure");
    expect(screen.getByText("RD$-10")).not.toHaveClass("ledger-money-positive", "ledger-money-negative");
    expect(screen.getByText("RD$200")).not.toHaveClass("ledger-money-positive", "ledger-money-negative");
    expect(screen.getByText("-0.500000")).not.toHaveClass("ledger-money-negative");
    expect(screen.getByText("-0.500000").className).toContain("ledger-figure");
  });

  it("keeps calculation terminology inside the closed technical disclosure", () => {
    mount();
    const summary = screen.getByText("Detalles técnicos");
    expect(summary.closest("details")).not.toHaveAttribute("open");
    fireEvent.click(summary);
    expect(screen.getByText(/ROI.*HALF_UP/)).toBeInTheDocument();
  });

  it("does not invent unavailable values or repeat net when the verdict owns it", () => {
    const first = mount({ net: undefined, roi: null, return_per_wagered: null, max_drawdown: undefined });
    expect(screen.getAllByText("N/D")).toHaveLength(2);
    expect(screen.getAllByText("No disponible")).toHaveLength(2);
    first.unmount();
    const second = mount({ net: 10 }, true);
    expect(screen.queryByText("Neto")).not.toBeInTheDocument();
    second.unmount();
  });
});
