import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
vi.mock("./pages/runs/NewRunPage", () => ({ NewRunPage: () => <p>Formulario de corrida</p> }));
vi.mock("./pages/runs/ListPage", () => ({ ListPage: () => <p>Lista de corridas</p> }));
vi.mock("./pages/runs/ResultPage", () => ({ ResultPage: () => <p>Informe de corrida cargado</p> }));

describe("run routes", () => {
  it("routes root and unknown paths back to Corridas", async () => {
    const { unmount } = render(<MemoryRouter initialEntries={["/"]}><App /></MemoryRouter>);
    expect(await screen.findByText("Lista de corridas")).toBeInTheDocument();
    unmount();
    render(<MemoryRouter initialEntries={["/unknown"]}><App /></MemoryRouter>);
    expect(await screen.findByText("Lista de corridas")).toBeInTheDocument();
  });
  it("gives /corridas/nueva precedence over the result route", async () => {
    render(<MemoryRouter initialEntries={["/corridas/nueva"]}><App /></MemoryRouter>);
    expect(await screen.findByText("Formulario de corrida")).toBeInTheDocument();
  });
  it("loads settings and routes result IDs to the report", async () => {
    const { unmount } = render(<MemoryRouter initialEntries={["/ajustes"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando ajustes e historial");
    unmount();
    render(<MemoryRouter initialEntries={["/corridas/run-1"]}><App /></MemoryRouter>);
    expect(await screen.findByText("Informe de corrida cargado")).toBeInTheDocument();
  });
});
