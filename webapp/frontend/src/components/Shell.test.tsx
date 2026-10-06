import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Shell } from "./Shell";
import { QueueProvider } from "./QueueProvider";

const originalInnerWidth = window.innerWidth;
afterEach(() => {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: originalInnerWidth });
  window.dispatchEvent(new Event("resize"));
});

function renderShell(path = "/simulaciones", options: { mobileTitle?: string; primaryAction?: { label: string; to: string } | null } = { primaryAction: { label: "Nueva simulación", to: "/simulaciones/nueva" } }) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <QueueProvider><Shell title="Prueba" {...options}><p>contenido</p></Shell></QueueProvider>
    </MemoryRouter>,
  );
}

describe("Shell navigation", () => {
  it("# F-SHELL-003 F-SHELL-004 exposes four canonical mobile destinations and the extended action", () => {
    renderShell();
    const navigation = screen.getByRole("navigation", { name: "Navegación principal" });
    const destinations = [
      ["Simulaciones", "/simulaciones"],
      ["Estrategias", "/configuraciones"],
      ["Datos", "/datos"],
      ["Ajustes", "/ajustes"],
    ];
    expect(navigation.querySelectorAll("a")).toHaveLength(4);
    for (const [name, href] of destinations) {
      const link = navigation.querySelector<HTMLAnchorElement>(`a[href="${href}"]`);
      expect(link).not.toBeNull();
      expect(link).toHaveTextContent(name);
      expect(within(navigation).getByRole("link", { name })).toHaveAttribute("href", href);
    }
    expect(screen.getByRole("link", { name: "Acceso rápido: Nueva simulación" })).toHaveAttribute("href", "/simulaciones/nueva");
  });

  it("suppresses the global FAB on settings, guided creation, data, detail, and comparison routes", () => {
    for (const path of ["/ajustes", "/simulaciones/nueva/perfil", "/datos", "/simulaciones/resultado-1", "/simulaciones/resultado-1/comparacion"]) {
      const { unmount } = renderShell(path, { primaryAction: null });
      expect(screen.queryByRole("link", { name: "Acceso rápido: Nueva simulación" }), path).not.toBeInTheDocument();
      unmount();
    }
    renderShell("/simulaciones");
    expect(screen.getByRole("link", { name: "Acceso rápido: Nueva simulación" })).toHaveAttribute("href", "/simulaciones/nueva");
  });

  it("# F-SHELL-006 marks the current destination and keeps its icon and label inside the item", () => {
    renderShell("/configuraciones");
    const link = screen.getByRole("link", { name: "Estrategias" });
    expect(link).toHaveAttribute("aria-current", "page");
    expect(link.className).toMatch(/shell-nav-link/);
    expect(link.className).toMatch(/is-active/);
    expect(within(link).getByText("◇", { selector: ".shell-nav-icon" })).toBeInTheDocument();
    expect(within(link).getByText("Estrategias")).toBeInTheDocument();
    expect(link.className).not.toMatch(/border-l-2/);
  });

  it("# F-SHELL-010 keeps the queue control accessible and connected to QueueDrawer", async () => {
    const user = userEvent.setup();
    renderShell();
    const queue = screen.getByRole("button", { name: "Abrir cola de cálculo" });
    expect(queue).toHaveAttribute("aria-haspopup", "dialog");
    expect(queue).toHaveAttribute("aria-expanded", "false");
    expect(queue).toHaveAccessibleDescription("Sin cálculos en curso");
    await user.click(queue);
    expect(screen.getByRole("dialog", { name: "Cola de cálculo" })).toBeInTheDocument();
  });

  it("# F-SHELL-011 uses route-declared mobile titles without inferring from paths", () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    for (const [path, title] of [["/simulaciones/historicas", "Corridas históricas"], ["/simulaciones/nueva-historica", "Nueva corrida histórica"]]) {
      const { unmount } = renderShell(path, { mobileTitle: title, primaryAction: null });
      expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
      unmount();
    }
    renderShell("/simulaciones/run", { mobileTitle: "Resultado", primaryAction: null });
    expect(screen.getByRole("heading", { name: "Resultado" })).toBeInTheDocument();
  });

  it("keeps route titles from breaking mid-word", () => {
    renderShell();
    const heading = screen.getByRole("heading", { name: "Prueba" });
    expect(heading.className).toMatch(/\bbreak-normal\b/);
    expect(heading.className).not.toMatch(/\bbreak-(?:all|words)\b/);
  });

  it("defaults to dark regardless of system preference and lets the user choose light", async () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });
    window.localStorage.removeItem("laboratorio-theme");
    renderShell();
    expect(document.documentElement.dataset.theme).toBe("dark");
    const toggle = screen.getByRole("button", { name: /Cambiar tema/ });
    await userEvent.setup().click(toggle);
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("falls back to a session-only theme when localStorage is unavailable", async () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("storage blocked"); });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("storage blocked"); });
    try {
      const user = userEvent.setup();
      renderShell();
      const toggle = screen.getByRole("button", { name: /Cambiar tema/ });
      expect(toggle).toBeInTheDocument();
      await user.click(toggle);
      expect(document.documentElement.dataset.theme).toMatch(/light|dark/);
    } finally {
      getItem.mockRestore();
      setItem.mockRestore();
      delete document.documentElement.dataset.theme;
    }
  });

  it("# F-SHELL-012 keeps bottom navigation as the mobile base and exposes theme controls", () => {
    renderShell();
    const nav = screen.getByRole("navigation", { name: "Navegación principal" });
    expect(nav.className).toMatch(/shell-navigation/);
    expect(nav.className).not.toMatch(/hidden/);
    const theme = screen.getByRole("button", { name: /Cambiar tema/ });
    expect(theme).toBeInTheDocument();
    const queue = screen.getByRole("button", { name: "Abrir cola de cálculo" });
    expect(theme.compareDocumentPosition(queue) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(theme.closest(".shell-app-bar-actions")).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(6); // Skip link, four destinations, and extended FAB.
  });
});
