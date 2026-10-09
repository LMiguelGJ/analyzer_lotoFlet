import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../api/client";
import type { QueueStatus } from "../api/types";
import { Shell } from "./Shell";
import { QueueProvider } from "./QueueProvider";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getQueue: vi.fn() } };
});

const emptyQueue: QueueStatus = {
  active_id: null,
  pending: { total: 0, offset: 0, limit: 20, count: 0, items: [] },
  held: { total: 0, offset: 0, limit: 20, count: 0, items: [] },
  last_failure: null,
};
beforeEach(() => vi.mocked(apiClient.getQueue).mockResolvedValue(emptyQueue));

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

  it("# F-SHELL-006 marks the current destination with its legend label", () => {
    renderShell("/configuraciones");
    const link = screen.getByRole("link", { name: "Estrategias" });
    expect(link).toHaveAttribute("aria-current", "page");
    expect(link.className).toMatch(/shell-nav-link/);
    expect(link.className).toMatch(/is-active/);
    expect(within(link).getByText("Estrategias")).toBeInTheDocument();
    expect(link.querySelector(".shell-nav-icon")).toBeNull();
    expect(link.className).not.toMatch(/border-l-2/);
  });

  it("shows the authoritative pending total in the queue control", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce({
      ...emptyQueue,
      pending: { ...emptyQueue.pending, total: 2, count: 2, items: ["one", "two"] },
    });
    renderShell();
    expect(await screen.findByRole("button", { name: "Abrir cola de cálculo" })).toHaveTextContent("Cola · Sin cálculos en curso · 2 en espera");
  });

  it("# F-SHELL-010 keeps the queue control accessible and connected to QueueDrawer", async () => {
    const user = userEvent.setup();
    renderShell();
    const queue = screen.getByRole("button", { name: "Abrir cola de cálculo" });
    expect(queue).toHaveAttribute("aria-haspopup", "dialog");
    expect(queue).toHaveAttribute("aria-expanded", "false");
    expect(queue).toHaveAccessibleDescription("Sin cálculos en curso");
    expect(queue).toHaveTextContent("Cola · Sin cálculos en curso");
    await user.click(queue);
    expect(screen.getByRole("dialog", { name: "Cola de cálculo" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Cola de cálculo" })).not.toBeInTheDocument();
    expect(queue).toHaveFocus();
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

  it("keeps the dark-only shell, clears the legacy theme key, and exposes no theme toggle", () => {
    window.localStorage.setItem("laboratorio-theme", "light");
    renderShell();
    expect(window.localStorage.getItem("laboratorio-theme")).toBeNull();
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(screen.queryByRole("button", { name: /Cambiar tema/ })).not.toBeInTheDocument();
  });

  it("clears the legacy key best-effort when localStorage is unavailable", () => {
    const removeItem = vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("storage blocked"); });
    try {
      renderShell();
      expect(removeItem).toHaveBeenCalledWith("laboratorio-theme");
      expect(screen.queryByRole("button", { name: /Cambiar tema/ })).not.toBeInTheDocument();
    } finally {
      removeItem.mockRestore();
    }
  });

  it("# F-SHELL-012 keeps bottom navigation as the mobile base without theme controls", () => {
    renderShell();
    const nav = screen.getByRole("navigation", { name: "Navegación principal" });
    expect(nav.className).toMatch(/shell-navigation/);
    expect(nav.className).not.toMatch(/hidden/);
    expect(screen.queryByRole("button", { name: /Cambiar tema/ })).not.toBeInTheDocument();
    const queue = screen.getByRole("button", { name: "Abrir cola de cálculo" });
    expect(queue.closest(".shell-app-bar-actions")).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(6); // Skip link, four destinations, and primary action.
  });
});
