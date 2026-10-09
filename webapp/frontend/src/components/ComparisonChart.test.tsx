import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
// Contract coverage: F-RESULT-021 shared date axis, persisted endpoints, non-color patterns, textual legend/data and scroll alternative; F-RESULT-022 keyboard series toggles preserve text data.
import { describe, expect, it } from "vitest";
import { ComparisonChart } from "./ComparisonChart";

const series = [
  { ordinal: 0, name: "A", visible: true, total: 2, points: [{ ordinal: 0, label: "2025-01-01 10:00", balance: 100 }, { ordinal: 1, label: "2025-01-01 10:30", balance: 120 }] },
  { ordinal: 1, name: "B", visible: true, total: 1, points: [{ ordinal: 0, label: "2025-01-01 10:15", balance: 90 }] },
];
describe("comparison chronological chart", () => {
  it("positions distinct dates on one time axis, ends series on its last persisted point, and labels patterns", () => {
    render(<ComparisonChart series={series} onToggle={() => {}} />);
    const figure = screen.getByRole("figure", { name: /Evolución comparada/ });
    const a = within(figure).getByTestId("series-0");
    const b = within(figure).getByTestId("series-1");
    expect(a).toHaveAttribute("stroke-dasharray", "none");
    expect(b).toHaveAttribute("stroke-dasharray", "8 5");
    expect(a).toHaveAttribute("stroke", "var(--bf-legend)");
    expect(b).toHaveAttribute("stroke", "var(--bf-legend-dim)");
    expect(within(figure).getByText("A · RD$120")).toBeInTheDocument();
    expect(within(figure).getByText("B · RD$90")).toBeInTheDocument();
    expect(a.getAttribute("points")?.split(" ")).toHaveLength(2);
    expect(b.getAttribute("points")?.split(" ")).toHaveLength(1);
    const [start, end] = a.getAttribute("points")!.split(" ").map((point) => Number(point.split(",")[0]));
    const middle = Number(b.getAttribute("points")!.split(",")[0]);
    expect(start).toBeLessThan(middle);
    expect(middle).toBeLessThan(end);
    expect(screen.getByText(/2025-01-01 10:15.*RD\$90/)).toBeInTheDocument();
    expect(screen.getByText(/líneas conectan observaciones/)).toBeInTheDocument();
    expect(within(figure).getByRole("img")).toHaveAttribute("aria-label", expect.stringContaining("trazos y marcadores"));
    expect(within(figure).getByText(/A · circle, línea continua/)).toBeInTheDocument();
    expect(within(figure).getByText(/B · square, línea a trazos/)).toBeInTheDocument();
    expect(within(figure).getByRole("img").closest("svg")).toHaveClass("min-w-[640px]");
    expect(within(figure).getByRole("region", { name: "Gráfico comparado" })).toHaveClass("overflow-x-auto");
  });
  it("offers keyboard-accessible toggles and textual data without changing metrics", async () => {
    const user = userEvent.setup();
    let hidden = false;
    const { rerender } = render(<ComparisonChart series={series} onToggle={() => { hidden = !hidden; rerender(<ComparisonChart series={[series[0], { ...series[1], visible: !hidden }]} onToggle={() => {}} />); }} />);
    const toggle = screen.getByRole("checkbox", { name: "Mostrar B" });
    toggle.focus();
    await user.keyboard(" ");
    expect(toggle).not.toBeChecked();
    expect(screen.queryByTestId("series-1")).not.toBeInTheDocument();
    expect(screen.getByText(/B: 2025-01-01 10:15.*RD\$90/)).toBeInTheDocument();
  });
});
