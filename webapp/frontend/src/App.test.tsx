import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { App } from "./App";

function renderAt(path: string) {
  cleanup();
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: [path] });
  const view = render(<RouterProvider router={router} />);
  return { ...view, router };
}

describe("routing", () => {
  it("# F-SHELL-001 redirects the root path to /simulaciones", () => {
    const { router } = renderAt("/");
    expect(screen.getByRole("heading", { name: "Simulaciones" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/simulaciones");
  });

  it("# F-SHELL-002 redirects legacy experiment paths and preserves query strings", () => {
    const cases = [
      ["/experimentos", "/simulaciones"],
      ["/experimentos/nuevo?base=x", "/simulaciones/nueva?base=x"],
      ["/experimentos/nuevo/sesion?dataset_sha256=abc", "/simulaciones/nueva/sesion?dataset_sha256=abc"],
      ["/experimentos/nuevo/perfil?dataset_sha256=abc", "/simulaciones/nueva/perfil?dataset_sha256=abc"],
      ["/experimentos/historicas?page=2", "/simulaciones/historicas?page=2"],
      ["/experimentos/historicas/run-1?view=all", "/simulaciones/historicas/run-1?view=all"],
      ["/experimentos/nueva-historica?dataset=latest", "/simulaciones/nueva-historica?dataset=latest"],
      ["/experimentos/run-1?run=2", "/simulaciones/run-1?run=2"],
      ["/experimentos/run-1/comparacion?sort=name", "/simulaciones/run-1/comparacion?sort=name"],
    ] as const;
    for (const [from, to] of cases) {
      const { router } = renderAt(from);
      expect(`${router.state.location.pathname}${router.state.location.search}`).toBe(to);
    }
  });

  it.each([
    ["/simulaciones", "Simulaciones"],
    ["/simulaciones/nueva", "Crear simulación"],
    ["/simulaciones/historicas", "Corridas históricas"],
    ["/simulaciones/nueva-historica", "Nueva corrida histórica"],
    ["/simulaciones/historicas/ejemplo", "Resultado de corrida histórica"],
    ["/simulaciones/nueva/sesion", "Crear varias simulaciones"],
    ["/simulaciones/nueva/perfil", "Crear simulación con perfil de juego"],
    ["/simulaciones/ejemplo", "Resultado de la simulación"],
    ["/simulaciones/ejemplo/comparacion", "Comparar simulaciones"],
    ["/configuraciones", "Estrategias"],
    ["/datos", "Datos e historial"],
    ["/ajustes", "Ajustes"],
  ])("# F-SHELL-002 shows the canonical title for %s", (path, title) => {
    renderAt(path);
    expect(screen.getByRole("heading", { name: title, level: 1 })).toBeInTheDocument();
  });

  it("# F-SHELL-003 keeps route paths and canonical destinations stable", () => {
    renderAt("/configuraciones");
    expect(screen.getByRole("link", { name: "Estrategias" })).toHaveAttribute("href", "/configuraciones");
    renderAt("/datos");
    expect(screen.getByRole("link", { name: "Datos" })).toHaveAttribute("href", "/datos");
    renderAt("/ajustes");
    expect(screen.getByRole("link", { name: "Ajustes" })).toHaveAttribute("href", "/ajustes");
    renderAt("/simulaciones");
    expect(within(document.getElementById("primary-navigation")!).getByRole("link", { name: "Simulaciones" })).toHaveAttribute("href", "/simulaciones");
  });

  it("# F-SHELL-005 renders an honest not-found state for unknown paths", () => {
    renderAt("/algo-inexistente");
    expect(screen.getByRole("heading", { name: "Página no encontrada" })).toBeInTheDocument();
    expect(screen.getByText(/Elegí una sección de la navegación/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir a Simulaciones" })).toHaveAttribute("href", "/simulaciones");
  });

  it("# F-SHELL-006 marks the current nav destination as active", () => {
    renderAt("/configuraciones");
    expect(screen.getByRole("link", { name: "Estrategias" })).toHaveAttribute("aria-current", "page");
  });
});

describe("skip link", () => {
  it("# F-SHELL-010 adapts the Experimentos FAB to the historical view without adding a destination", () => {
    renderAt("/simulaciones/historicas");
    expect(screen.getByRole("link", { name: "Acceso rápido: Nueva corrida histórica" })).toHaveAttribute("href", "/simulaciones/nueva-historica");
    expect(screen.getAllByRole("link").filter((link) => link.getAttribute("href") === "/ajustes")).toHaveLength(1);
  });

  it("# F-SHELL-007 is the first focusable element and moves focus to main content", async () => {
    const user = userEvent.setup();
    renderAt("/simulaciones");
    await user.tab();
    expect(screen.getByText("Saltar al contenido principal")).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(document.getElementById("main-content")).toHaveFocus();
  });
});

describe("keyboard access", () => {
  it("# F-SHELL-008 keeps all destinations and the queue control in the tab order", async () => {
    const user = userEvent.setup();
    renderAt("/simulaciones");
    await user.tab();
    expect(screen.getByText("Saltar al contenido principal")).toHaveFocus();
    const theme = screen.getByRole("button", { name: /Cambiar tema/ });
    const queue = screen.getByRole("button", { name: "Abrir cola de cálculo" });
    await user.tab();
    expect(theme).toHaveFocus();
    await user.tab();
    expect(queue).toHaveFocus();
    for (const name of ["Simulaciones", "Estrategias", "Datos", "Ajustes"]) {
      await user.tab();
      expect(within(document.getElementById("primary-navigation")!).getByRole("link", { name })).toHaveFocus();
    }
    expect(queue).toBeEnabled();
  });
});

describe("shell accessibility", () => {
  it("# F-SHELL-009 has no axe violations on the default screen", async () => {
    const { container } = renderAt("/simulaciones");
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
