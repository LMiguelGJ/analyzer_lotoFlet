import { render, screen } from "@testing-library/react";
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
  it("exposes exactly four canonical destinations", () => {
    renderShell();
    const navigation = screen.getByRole("navigation", { name: "Navegación principal" });
    const destinations = [
      ["Simulaciones", "/experimentos"],
      ["Estrategias", "/configuraciones"],
      ["Datos", "/datos"],
      ["Ajustes", "/ajustes"],
    ];
    expect(navigation.querySelectorAll("a")).toHaveLength(4);
    for (const [name, href] of destinations) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
    }
  });

  it("marks the current destination and uses a two-pixel active accent rule", () => {
    renderShell("/configuraciones");
    const link = screen.getByRole("link", { name: "Estrategias" });
    expect(link).toHaveAttribute("aria-current", "page");
    expect(link.className).toMatch(/border-l-2/);
    expect(link.className).toMatch(/border-accent/);
  });

  it("keeps the queue control accessible and connected to QueueDrawer", async () => {
    const user = userEvent.setup();
    renderShell();
    const queue = screen.getByRole("button", { name: "Abrir cola de cálculo" });
    expect(queue).toHaveAttribute("aria-haspopup", "dialog");
    expect(queue).toHaveAttribute("aria-expanded", "false");
    expect(queue).toHaveAccessibleDescription("Sin cálculos en curso");
    await user.click(queue);
    expect(screen.getByRole("dialog", { name: "Cola de cálculo" })).toBeInTheDocument();
  });

  it("does not break route titles mid-word", () => {
    renderShell();
    const heading = screen.getByRole("heading", { name: "Prueba" });
    expect(heading.className).toMatch(/\bbreak-normal\b/);
    expect(heading.className).not.toMatch(/\bbreak-(?:all|words)\b/);
  });

  it("keeps navigation visible and compact below the desktop rail breakpoint", () => {
    renderShell();
    const nav = screen.getByRole("navigation", { name: "Navegación principal" });
    expect(nav.className).toMatch(/w-full/);
    expect(nav.className).toMatch(/min-\[900px\]:w-\[210px\]/);
    expect(nav.className).not.toMatch(/hidden/);
    expect(screen.getAllByRole("link")).toHaveLength(5); // Skip link plus four destinations.
  });
});
