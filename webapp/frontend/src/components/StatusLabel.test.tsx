import { render, screen } from "@testing-library/react";
// Contract coverage: F-RESULT-017 execution/outcome vocabularies stay distinct; F-RESULT-018 text-only semantic chips; F-RESULT-019 unknown status values throw.
import { describe, expect, it } from "vitest";
import type { ExperimentStatus, Outcome, RunStatus } from "../api/types";
import { StatusLabel } from "./StatusLabel";

const EXECUTION_VALUES: (ExperimentStatus | RunStatus)[] = [
  "pending",
  "held",
  "running",
  "completed",
  "cancelled",
  "not_run",
  "interrupted",
  "failed",
];
const OUTCOME_VALUES: Outcome[] = ["goal", "ruin", "limit", "history_exhausted"];

describe("StatusLabel", () => {
  it("renders execution status text in Spanish, distinct from whether a goal was reached", () => {
    render(<StatusLabel kind="execution" value="completed" />);
    expect(screen.getByText("Ejecución completada")).toBeInTheDocument();
  });

  it("renders outcome text in Spanish, using different vocabulary than execution status", () => {
    render(<StatusLabel kind="outcome" value="goal" />);
    expect(screen.getByText("Meta alcanzada")).toBeInTheDocument();
    expect(screen.queryByText("Ejecución completada")).not.toBeInTheDocument();
  });

  it("never uses the same label for an execution status and an outcome", () => {
    render(
      <>
        <StatusLabel kind="execution" value="completed" />
        <StatusLabel kind="outcome" value="goal" />
      </>,
    );
    const completed = screen.getByText("Ejecución completada");
    const goal = screen.getByText("Meta alcanzada");
    expect(completed.textContent).not.toBe(goal.textContent);
  });

  it("gives every distinct execution status a unique Spanish label (text is the authoritative signal, not shape or color)", () => {
    const texts = EXECUTION_VALUES.map((value) => {
      const { unmount } = render(<StatusLabel kind="execution" value={value} className="status-under-test" />);
      const text = document.querySelector(".status-under-test")?.textContent;
      unmount();
      return text;
    });
    expect(new Set(texts).size).toBe(EXECUTION_VALUES.length);
  });

  it("gives every distinct outcome a unique Spanish label", () => {
    const texts = OUTCOME_VALUES.map((value) => {
      const { unmount } = render(<StatusLabel kind="outcome" value={value} className="status-under-test" />);
      const text = document.querySelector(".status-under-test")?.textContent;
      unmount();
      return text;
    });
    expect(new Set(texts).size).toBe(OUTCOME_VALUES.length);
  });

  it("never shares a label between the execution vocabulary and the outcome vocabulary (UX37)", () => {
    const executionTexts = new Set(
      EXECUTION_VALUES.map((value) => {
        const { unmount } = render(<StatusLabel kind="execution" value={value} className="status-under-test" />);
        const text = document.querySelector(".status-under-test")?.textContent;
        unmount();
        return text;
      }),
    );
    for (const value of OUTCOME_VALUES) {
      const { unmount } = render(<StatusLabel kind="outcome" value={value} className="status-under-test" />);
      const text = document.querySelector(".status-under-test")?.textContent;
      unmount();
      expect(executionTexts.has(text)).toBe(false);
    }
  });

  it("shapes may repeat within a tone family (e.g. cancelled/failed): the accompanying comment must say text is authoritative, not that every shape is unique", () => {
    const cancelled = render(<StatusLabel kind="execution" value="cancelled" />).getByText("Cancelado").closest("[data-status-shape]");
    const failed = render(<StatusLabel kind="execution" value="failed" />).getByText("Con error").closest("[data-status-shape]");
    expect(cancelled?.getAttribute("data-status-shape")).toBe(failed?.getAttribute("data-status-shape"));
  });

  it("uses semantic text-only stamps and hairline labels rather than color-only status", () => {
    const { unmount } = render(<StatusLabel kind="outcome" value="goal" />);
    const status = screen.getByText("Meta alcanzada");
    expect(status.closest(".ledger-chip")).toHaveClass("ledger-chip-success");
    expect(status.className).not.toMatch(/money-(?:positive|negative)/);
    unmount();
    render(<StatusLabel kind="execution" value="failed" />);
    expect(screen.getByText("Con error").closest(".ledger-chip")).toHaveClass("ledger-chip-danger");
    unmount();
    const { container } = render(<StatusLabel kind="execution" value="running" />);
    const label = screen.getByText("En curso");
    expect(label).toHaveAttribute("data-status-kind", "execution");
    expect(label).toHaveAttribute("data-status-value", "running");
    expect(label).toHaveAttribute("data-status-shape", "triangle");
    expect(label.closest(".ledger-chip")).toHaveClass("ledger-chip-neutral");
    expect(container.querySelector("svg")).toBeNull();
  });

  it("throws for an unknown status value instead of silently rendering nothing", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(() => render(<StatusLabel kind="execution" value={"bogus" as any} />)).toThrow();
  });
});
