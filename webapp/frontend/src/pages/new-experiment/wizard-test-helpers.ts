import { screen, waitFor, within } from "@testing-library/react";
import type { UserEvent } from "@testing-library/user-event";

export type WizardStep = "Estrategia" | "Reglas" | "Alcance" | "Capital y meta" | "Revisión";

/** Select a wizard step that has already been reached through valid prior steps. */
export async function goToStep(user: UserEvent, step: WizardStep): Promise<void> {
  const button = screen.getByRole("button", { name: step });
  if (button.getAttribute("aria-current") === "step") return;
  await user.click(button);
  await waitFor(() => expect(screen.getByRole("button", { name: step })).toHaveAttribute("aria-current", "step"));
}

/** Advance one valid step and wait for its heading and any step-owned async content. */
export async function nextWizardStep(user: UserEvent): Promise<void> {
  const before = Number(screen.getByRole("progressbar").getAttribute("aria-valuenow"));
  const headings = [
    /¿Cómo elegimos los números/,
    /Reglas del sorteo/,
    /¿Desde qué sorteo empezar/,
    /Capital y datos/,
    /Revisá y lanzá/,
  ];
  const target = before;
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await waitFor(() => {
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", String(target + 1));
    expect(within(screen.getByRole("region", { name: "Asistente para crear una simulación" })).getByRole("heading", { name: headings[target] })).toBeInTheDocument();
  });
  if (target === 2) {
    await waitFor(() => {
      const draw = screen.queryByRole("combobox", { name: "Sorteo inicial" }) as HTMLSelectElement | null;
      if (!draw) throw new Error("Waiting for starting-draw catalog loading");
      const emptyState = screen.queryByText(/No hay sorteos.*disponibles|Ningún sorteo.*ranking/);
      if (draw.disabled && !emptyState) throw new Error("Waiting for starting-draw catalog loading");
      if (draw.options.length <= 1 && !emptyState)
        throw new Error("Waiting for starting-draw catalog results");
    });
  }
}

/** Reach a later step by validating each preceding step via its Next button. */
export async function advanceTo(user: UserEvent, step: number): Promise<void> {
  while (Number(screen.getByRole("progressbar").getAttribute("aria-valuenow")) < step + 1) {
    await nextWizardStep(user);
  }
}
