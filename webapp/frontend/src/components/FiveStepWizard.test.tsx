import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { FiveStepWizard, useFiveStepWizard } from "./FiveStepWizard";

const steps = ["Estrategia", "Reglas", "Alcance", "Capital y datos", "Revisión"].map((title) => ({ title, description: title }));

function Harness({ validate = () => true, busy = false }: { validate?: (step: number) => boolean; busy?: boolean }) {
  const wizard = useFiveStepWizard(steps.length, validate);
  const [draft, setDraft] = useState("conservar");
  return <FiveStepWizard steps={steps} activeStep={wizard.step} maxReachableStep={wizard.maxReachableStep} onSelectStep={wizard.goTo} onNext={wizard.next} onBack={wizard.back} busy={busy}>
    <label>Dato del paso {wizard.step + 1}<input value={draft} onChange={(event) => setDraft(event.target.value)} /></label>
  </FiveStepWizard>;
}

describe("FiveStepWizard", () => {
  it("owns five-step navigation, validates before advancing, and retains mounted draft state", () => {
    const validate = vi.fn((step: number) => step !== 0);
    render(<Harness validate={validate} />);
    expect(screen.getByRole("progressbar", { name: "Paso 1 de 5" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(validate).toHaveBeenCalledWith(0);
    expect(screen.getByRole("progressbar", { name: "Paso 1 de 5" })).toBeInTheDocument();
  });

  it("advances and returns to the same draft without losing the active value", () => {
    render(<Harness />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "draft" } });
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("progressbar", { name: "Paso 2 de 5" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Atrás" }));
    expect(screen.getByRole("textbox")).toHaveValue("draft");
  });

  it("renders the five-cell frame and marks the current step", () => {
    render(<Harness />);
    expect(screen.getByRole("navigation", { name: "Pasos de la simulación" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "1 Estrategia" })).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("button", { name: "5 Revisión" })).toHaveAttribute("aria-disabled", "true");
  });

  it("allows direct activation of reached steps by keyboard", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    const rules = screen.getByRole("button", { name: "2 Reglas" });
    expect(rules).toHaveAttribute("aria-disabled", "false");
    rules.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("progressbar", { name: "Paso 2 de 5" })).toBeInTheDocument();
    expect(rules).toHaveAttribute("aria-current", "step");
  });

  it("keeps steps beyond the reachable step disabled and out of tab order", () => {
    render(<Harness />);
    const future = screen.getByRole("button", { name: "3 Alcance" });
    expect(future).toBeDisabled();
    expect(future).toHaveAttribute("aria-disabled", "true");
    expect(future).toHaveAttribute("tabindex", "-1");
    fireEvent.click(future);
    expect(screen.getByRole("progressbar", { name: "Paso 1 de 5" })).toBeInTheDocument();
  });

  it("blocks admission while busy", () => {
    render(<Harness busy />);
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Atrás" })).toBeDisabled();
  });
});
