import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BalanceChart } from "./BalanceChart";

describe("LW11 balance chart", () => {
  it("plots only persisted balances and the actual goal, with a textual alternative", () => {
    render(<BalanceChart points={[{ ordinal: 1, balance: 140 }, { ordinal: 2, balance: 90 }]} goal={200} total={4} />);
    expect(screen.getByText(/2 de 4 apuestas/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /saldos registrados/ })).toBeInTheDocument();
    expect(screen.getByText(/Apuesta 1:.*140/)).toBeInTheDocument();
    expect(screen.getByText(/Meta:.*200/)).toBeInTheDocument();
    expect(screen.queryByText(/Apuesta 3:/)).not.toBeInTheDocument();
  });
  it("handles empty pages without a fictional outcome", () => {
    render(<BalanceChart points={[]} goal={200} total={0} />);
    expect(screen.getByText(/No hay apuestas registradas/)).toBeInTheDocument();
  });
});
