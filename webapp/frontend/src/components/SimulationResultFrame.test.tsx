import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SimulationResultFrame } from "./SimulationResultFrame";

const model = {
  family: "profile-v3" as const,
  title: "Ejecución 2",
  status: "En curso",
  source: `Dataset: ${"a".repeat(64)}`,
  sections: ["Resultado", "Apuestas", "Parámetros y datos"],
  actions: [{ label: "Comparar simulaciones", href: "/simulaciones/id/comparacion" }],
  payload: {} as never,
};

describe("SimulationResultFrame", () => {
  it("presents shared identity, native family, status, provenance, and section metadata around native content", () => {
    render(<SimulationResultFrame model={model}><div>Contenido nativo</div></SimulationResultFrame>);
    const frame = screen.getByRole("region", { name: "Ejecución 2" });
    expect(frame).toHaveAttribute("data-result-family", "profile-v3");
    expect(screen.getByText("En curso")).toBeInTheDocument();
    expect(screen.getByText(model.source)).toBeInTheDocument();
    expect(screen.getByLabelText("Secciones: Resultado, Apuestas, Parámetros y datos")).toHaveTextContent("Contenido nativo");
  });

  it("leaves unsupported native payloads untouched instead of coercing their family", () => {
    render(<SimulationResultFrame model={null}><div>Estado conservado</div></SimulationResultFrame>);
    expect(screen.getByText("Estado conservado")).toBeInTheDocument();
    expect(document.querySelector("[data-result-family]")).toBeNull();
  });
});
