import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import tailwindConfig from "../../tailwind.config";
import { Shell } from "./Shell";
import { QueueProvider } from "./QueueProvider";

function renderShell() {
  return render(
    <MemoryRouter>
      <QueueProvider><Shell title="Prueba">
        <p>contenido</p>
      </Shell></QueueProvider>
    </MemoryRouter>,
  );
}

describe("Shell nav toggle", () => {
  it("starts closed: aria-expanded=false, aria-controls points at the nav, nav marked closed", () => {
    renderShell();
    const toggle = screen.getByRole("button", { name: "Abrir navegación" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveAttribute("aria-controls", "primary-navigation");
    expect(screen.getByLabelText("Navegación principal")).toHaveAttribute("data-nav-open", "false");
  });

  it("opens on click: aria-expanded=true, label flips, nav marked open", async () => {
    const user = userEvent.setup();
    renderShell();
    const toggle = screen.getByRole("button", { name: "Abrir navegación" });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Cerrar navegación" })).toBe(toggle);
    expect(screen.getByLabelText("Navegación principal")).toHaveAttribute("data-nav-open", "true");
  });

  it("closes again on a second click", async () => {
    const user = userEvent.setup();
    renderShell();
    const toggle = screen.getByRole("button", { name: "Abrir navegación" });
    await user.click(toggle);
    await user.click(screen.getByRole("button", { name: "Cerrar navegación" }));
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByLabelText("Navegación principal")).toHaveAttribute("data-nav-open", "false");
  });

  it("closes on Escape while open, returning focus to the toggle", async () => {
    const user = userEvent.setup();
    renderShell();
    const toggle = screen.getByRole("button", { name: "Abrir navegación" });
    await user.click(toggle);
    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Abrir navegación" })).toHaveAttribute("aria-expanded", "false");
    expect(document.activeElement).toBe(toggle);
  });

  it("does nothing on Escape while already closed", async () => {
    const user = userEvent.setup();
    renderShell();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Abrir navegación" })).toHaveAttribute("aria-expanded", "false");
  });
});

describe("Shell breakpoint wiring (class presence only; real reflow needs a browser, LW18)", () => {
  it("wires the nav toggle bar to the 800px collapse breakpoint (max-nav)", () => {
    renderShell();
    const bar = screen.getByTestId("nav-toggle-bar");
    expect(bar.className).toMatch(/\bmax-nav:block\b/);
    expect(bar.className).not.toMatch(/\bmax-\[800px\]:/);
  });

  it("wires the sidebar visibility to the same 800px breakpoint (nav), not Tailwind's default md (768px)", () => {
    renderShell();
    const nav = screen.getByLabelText("Navegación principal");
    expect(nav.className).toMatch(/\bnav:block\b/);
    expect(nav.className).not.toMatch(/\bmd:/);
  });

  it("places the sidebar beside content at the 800px nav breakpoint, independently of the 1100px content breakpoint", () => {
    renderShell();
    const layout = screen.getByTestId("shell-layout");
    expect(tailwindConfig.theme.screens).toEqual({ nav: "800px", wide: "1100px" });
    expect(layout.className).toMatch(/\bnav:flex-row\b/);
    expect(layout.className).not.toMatch(/\bwide:flex-row\b|\bmd:flex-row\b/);
  });
});

describe("Shell content width (static check; jsdom has no real layout)", () => {
  it("main content never uses a fixed pixel width utility (max-width caps are fine)", () => {
    renderShell();
    const main = document.getElementById("main-content");
    const fixedWidthUtility = /(?<!max-)(?<!min-)\bw-\[\d/;
    expect(fixedWidthUtility.test(main?.className ?? "")).toBe(false);
  });
});

describe("Shell heading size (UX5: desktop h1 32-40px)", () => {
  it("uses a heading scale within the 32-40px band (text-4xl = 36px), not text-3xl (30px)", () => {
    renderShell();
    const heading = screen.getByRole("heading", { name: "Prueba" });
    expect(heading).toHaveClass("text-4xl");
    expect(heading.className).not.toMatch(/\btext-3xl\b/);
  });
});

describe("Shell fixed toggle does not overlap the header title", () => {
  it("keeps the toggle in the header's normal flow instead of position:fixed floating over the title", () => {
    renderShell();
    const toggle = screen.getByRole("button", { name: "Abrir navegación" });
    expect(toggle.className).not.toMatch(/\bfixed\b/);
  });
});
