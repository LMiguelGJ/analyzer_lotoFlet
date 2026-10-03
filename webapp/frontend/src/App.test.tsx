import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { App } from "./App";

function renderAt(path: string) {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: [path] });
  return render(<RouterProvider router={router} />);
}

describe("routing", () => {
  it("redirects the root path to /experimentos", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { name: "Simulaciones" })).toBeInTheDocument();
  });

  it("renders stable URLs including the data-import destination", () => {
    renderAt("/configuraciones");
    expect(screen.getByRole("heading", { name: "Estrategias" })).toBeInTheDocument();

    renderAt("/datos");
    expect(screen.getByRole("heading", { name: "Datos del laboratorio" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Simulaciones" }).at(-1)).toHaveAttribute("href", "/experimentos");

    renderAt("/ajustes");
    expect(screen.getByRole("heading", { name: "Administración del laboratorio" })).toBeInTheDocument();

    renderAt("/experimentos/nuevo");
    expect(screen.getByRole("heading", { name: "Crear simulación" })).toBeInTheDocument();

    renderAt("/experimentos/nuevo/perfil");
    expect(screen.getByRole("heading", { name: "Simulación con perfil" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sesión con perfil registrado" })).toBeInTheDocument();
  });

  it("renders an honest not-found state for unknown paths", () => {
    renderAt("/algo-inexistente");
    expect(screen.getByRole("heading", { name: "Página no encontrada" })).toBeInTheDocument();
    expect(screen.getByText(/Elegí una sección de la navegación/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir a Simulaciones" })).toHaveAttribute("href", "/experimentos");
  });

  it("marks the current nav destination as active", () => {
    renderAt("/configuraciones");
    const link = screen.getByRole("link", { name: "Estrategias" });
    expect(link).toHaveAttribute("aria-current", "page");
  });
});

describe("skip link", () => {
  it("is the first focusable element and moves focus to main content", async () => {
    const user = userEvent.setup();
    renderAt("/experimentos");

    await user.tab();
    expect(screen.getByText("Saltar al contenido principal")).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(document.getElementById("main-content")).toHaveFocus();
  });
});

describe("keyboard focus order", () => {
  it("moves skip link -> nav toggle -> nav links -> enabled queue control", async () => {
    const user = userEvent.setup();
    renderAt("/experimentos");

    const order = [
      "Saltar al contenido principal",
      "Abrir navegación",
      "Simulaciones",
      "Perfiles de juego",
      "Historiales",
      "Estrategias",
      "Administración",
    ];

    for (const name of order) {
      await user.tab();
      const candidate = screen.getByText(name, { selector: "a, button" });
      expect(candidate).toHaveFocus();
    }

    const queueButton = screen.getByRole("button", { name: /Cola/ });
    expect(queueButton).toBeEnabled();
    await user.tab();
    expect(queueButton).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("dialog", { name: "Cola de experimentos" })).toBeInTheDocument();
  });
});

describe("shell accessibility", () => {
  it("has no axe violations on the default screen", async () => {
    const { container } = renderAt("/experimentos");
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
