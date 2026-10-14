import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { Shell } from "./Shell";

describe("Shell navigation foundation", () => {
  it("uses Quiniela as the app brand without the old numeric suffix", () => {
    render(<MemoryRouter><Shell title="Laboratorios"><p>Contenido</p></Shell></MemoryRouter>);
    expect(screen.getByText("Quiniela", { selector: ".shell-brand" })).toBeInTheDocument();
    expect(screen.queryByText(/Quiniela 80/i)).not.toBeInTheDocument();
  });

  it("uses Quiniela as the browser document title", () => {
    const html = readFileSync("index.html", "utf8");
    expect(new DOMParser().parseFromString(html, "text/html").title).toBe("Quiniela");
  });

  it("keeps the skip link and main landmark with only Laboratorios and Ajustes in navigation", () => {
    render(<MemoryRouter initialEntries={["/corridas"]}><Routes><Route path="*" element={<Shell title="Corridas"><p>Contenido</p></Shell>} /></Routes></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Saltar al contenido principal" })).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("navigation", { name: "Navegación principal" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Corridas" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Laboratorios" })).toHaveAttribute("href", "/laboratorios");
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
