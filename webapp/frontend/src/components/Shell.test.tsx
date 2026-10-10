import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Shell } from "./Shell";

describe("Shell navigation foundation", () => {
  it("keeps the skip link, main landmark, and two active page links", () => {
    render(<MemoryRouter initialEntries={["/corridas"]}><Routes><Route path="*" element={<Shell title="Corridas"><p>Contenido</p></Shell>} /></Routes></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Saltar al contenido principal" })).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("navigation", { name: "Navegación principal" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Corridas" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Ajustes" })).toHaveAttribute("href", "/ajustes");
    expect(screen.getAllByRole("link")).toHaveLength(3);
  });

  it("moves keyboard focus from the skip link to main content", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/corridas"]}><Routes><Route path="*" element={<Shell title="Corridas"><p>Contenido</p></Shell>} /></Routes></MemoryRouter>);
    const skip = screen.getByRole("link", { name: "Saltar al contenido principal" });
    await user.tab();
    expect(skip).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("main")).toHaveFocus();
  });

  it("has no automated accessibility violations", async () => {
    const { container } = render(<MemoryRouter initialEntries={["/ajustes"]}><Routes><Route path="*" element={<Shell title="Ajustes"><p>Contenido</p></Shell>} /></Routes></MemoryRouter>);
    const { axe } = await import("jest-axe");
    expect(await axe(container)).toHaveNoViolations();
  });
});
