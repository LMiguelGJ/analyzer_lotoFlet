import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Shell } from "./Shell";
import { QueueProvider } from "./QueueProvider";

function renderShell(path = "/experimentos") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <QueueProvider><Shell title="Prueba"><p>contenido</p></Shell></QueueProvider>
    </MemoryRouter>,
  );
}

describe("Shell navigation", () => {
  it("# F-SHELL-003 F-SHELL-004 exposes four canonical mobile destinations and the extended action", () => {
    renderShell();
    const navigation = screen.getByRole("navigation", { name: "Navegación principal" });
    const destinations = [
      ["Experimentos", "/experimentos"],
      ["Estrategias", "/configuraciones"],
      ["Datos", "/datos"],
      ["Ajustes", "/ajustes"],
    ];
    expect(navigation.querySelectorAll("a")).toHaveLength(4);
    for (const [name, href] of destinations) {
      const link = navigation.querySelector<HTMLAnchorElement>(`a[href="${href}"]`);
      expect(link).not.toBeNull();
      expect(link).toHaveTextContent(name);
      if (name !== "Experimentos") expect(within(navigation).getByRole("link", { name })).toHaveAttribute("href", href);
    }
    expect(screen.getByRole("link", { name: "Acceso rápido: Nueva simulación" })).toHaveAttribute("href", "/experimentos/nuevo");
  });

  it("# F-SHELL-006 marks the current destination with the Material 3 active indicator", () => {
    renderShell("/configuraciones");
    const link = screen.getByRole("link", { name: "Estrategias" });
    expect(link).toHaveAttribute("aria-current", "page");
    expect(link.className).toMatch(/shell-nav-link/);
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

  it("# F-SHELL-011 does not break route titles mid-word", () => {
    renderShell();
    const heading = screen.getByRole("heading", { name: "Prueba" });
    expect(heading.className).toMatch(/\bbreak-normal\b/);
    expect(heading.className).not.toMatch(/\bbreak-(?:all|words)\b/);
  });

  it("# F-SHELL-012 keeps bottom navigation as the mobile base and exposes theme controls", () => {
    renderShell();
    const nav = screen.getByRole("navigation", { name: "Navegación principal" });
    expect(nav.className).toMatch(/shell-navigation/);
    expect(nav.className).not.toMatch(/hidden/);
    expect(screen.getByRole("button", { name: /Cambiar tema/ })).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(6); // Skip link, four destinations, and extended FAB.
  });
});
