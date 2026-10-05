import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { App } from "./App";

function renderAt(path: string) {
  cleanup();
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: [path] });
  return render(<RouterProvider router={router} />);
}

describe("routing", () => {
  it("# F-SHELL-001 redirects the root path to /experimentos", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { name: "Simulaciones" })).toBeInTheDocument();
  });

  it.each([
    ["/experimentos", "Simulaciones"],
    ["/experimentos/nuevo", "Crear simulación"],
    ["/experimentos/nuevo/sesion", "Crear varias simulaciones"],
    ["/experimentos/nuevo/perfil", "Crear simulación con perfil de juego"],
    ["/experimentos/ejemplo", "Resultado de la simulación"],
    ["/experimentos/ejemplo/comparacion", "Comparar simulaciones"],
    ["/configuraciones", "Estrategias"],
    ["/datos", "Datos e historial"],
    ["/ajustes", "Ajustes"],
  ])("# F-SHELL-002 shows the canonical title for %s", (path, title) => {
    renderAt(path);
    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
  });

  it("# F-SHELL-003 keeps route paths and canonical destinations stable", () => {
    renderAt("/configuraciones");
    expect(screen.getByRole("link", { name: "Estrategias" })).toHaveAttribute("href", "/configuraciones");
    renderAt("/datos");
    expect(screen.getByRole("link", { name: "Datos" })).toHaveAttribute("href", "/datos");
    renderAt("/ajustes");
    expect(screen.getByRole("link", { name: "Ajustes" })).toHaveAttribute("href", "/ajustes");
    renderAt("/experimentos");
    expect(screen.getByRole("link", { name: "Simulaciones" })).toHaveAttribute("href", "/experimentos");
  });

  it("# F-SHELL-005 renders an honest not-found state for unknown paths", () => {
    renderAt("/algo-inexistente");
    expect(screen.getByRole("heading", { name: "Página no encontrada" })).toBeInTheDocument();
    expect(screen.getByText(/Elegí una sección de la navegación/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir a Simulaciones" })).toHaveAttribute("href", "/experimentos");
  });

  it("# F-SHELL-006 marks the current nav destination as active", () => {
    renderAt("/configuraciones");
    expect(screen.getByRole("link", { name: "Estrategias" })).toHaveAttribute("aria-current", "page");
  });
});

describe("skip link", () => {
  it("# F-SHELL-007 is the first focusable element and moves focus to main content", async () => {
    const user = userEvent.setup();
    renderAt("/experimentos");
    await user.tab();
    expect(screen.getByText("Saltar al contenido principal")).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(document.getElementById("main-content")).toHaveFocus();
  });
});

describe("keyboard access", () => {
  it("# F-SHELL-008 keeps all destinations and the queue control in the tab order", async () => {
    const user = userEvent.setup();
    renderAt("/experimentos");
    await user.tab();
    expect(screen.getByText("Saltar al contenido principal")).toHaveFocus();
    const queue = screen.getByRole("button", { name: "Abrir cola de cálculo" });
    await user.tab();
    expect(queue).toHaveFocus();
    for (const name of ["Simulaciones", "Estrategias", "Datos", "Ajustes"]) {
      await user.tab();
      expect(screen.getByRole("link", { name })).toHaveFocus();
    }
    expect(queue).toBeEnabled();
  });
});

describe("shell accessibility", () => {
  it("# F-SHELL-009 has no axe violations on the default screen", async () => {
    const { container } = renderAt("/experimentos");
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
