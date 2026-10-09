import { render, screen } from "@testing-library/react";
// Contract coverage: F-RESULT-020 persisted-only balances, real goal and textual alternative; empty state has no fictional outcome.
import { describe, expect, it } from "vitest";
import { BalanceChart } from "./BalanceChart";

describe("LW11 balance chart", () => {
  it("plots only persisted balances and the actual goal, with a textual alternative", () => {
    render(<BalanceChart points={[{ ordinal: 1, balance: 140 }, { ordinal: 2, balance: 90 }]} goal={200} total={4} />);
    expect(screen.getByText(/2 de 4 sorteos/)).toBeInTheDocument();
    const image = screen.getByRole("img", { name: /saldos registrados/ });
    expect(image).toBeInTheDocument();
    expect(image.querySelector('line[stroke="var(--bf-legend-dim)"]')).toHaveAttribute("stroke-dasharray", "2 4");
    expect(image.querySelector('polyline[stroke="var(--bf-legend)"]')).toBeInTheDocument();
    expect(image).toHaveTextContent("Saldo · RD$");
    expect(screen.getByRole("row", { name: /Sorteo 1.*140/ })).toBeInTheDocument();
    expect(screen.getByText(/Meta de saldo:/)).toHaveTextContent("200");
    expect(screen.queryByRole("row", { name: /Sorteo 3/ })).not.toBeInTheDocument();
  });
  it("handles empty pages without a fictional outcome", () => {
    render(<BalanceChart points={[]} goal={200} total={0} />);
    expect(screen.getByText(/Todavía no hay sorteos jugados/)).toBeInTheDocument();
  });
});
