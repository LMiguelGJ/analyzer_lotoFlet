import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NewRunPage } from "./NewRunPage";
import { optionsFixture, runFixture } from "./test-fixtures";
import { createRun, getRun, getRunOptions } from "../../api/runs";
import { getHistory } from "../../api/history";
import type { HistoryResponse } from "../../api/types";

vi.mock("../../api/runs", () => ({ createRun: vi.fn(), getRun: vi.fn(), getRunOptions: vi.fn() }));
vi.mock("../../api/history", () => ({ getHistory: vi.fn() }));
const createMock = vi.mocked(createRun), getRunMock = vi.mocked(getRun), optionsMock = vi.mocked(getRunOptions), historyMock = vi.mocked(getHistory);
const baseHistory = { ...optionsFixture.history, sha256: runFixture.config.history.sha256, origin: runFixture.config.history.origin, active: false };
const historyResponse: HistoryResponse = { active: optionsFixture.history, sources: [optionsFixture.history, baseHistory] };
const created = { ...runFixture, id: "created-1" };
function mount(path = "/corridas/nueva") { return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/corridas/nueva" element={<NewRunPage />} /><Route path="/corridas/:id" element={<p>Resultado</p>} /><Route path="*" element={<p>Otra ruta</p>} /></Routes></MemoryRouter>); }
beforeEach(() => { vi.clearAllMocks(); optionsMock.mockResolvedValue(optionsFixture); historyMock.mockResolvedValue(historyResponse); getRunMock.mockResolvedValue(runFixture); });

describe("new run form", () => {
  it("loads real defaults, posts the example configuration once and navigates to the returned run", async () => {
    const user = userEvent.setup(); createMock.mockResolvedValue(created); mount();
    expect(await screen.findByLabelText("Posiciones (1–5)")).toHaveValue("3");
    expect(screen.getByLabelText("Capital (RD$)")).toHaveValue("2000");
    expect(screen.getByText(/No es una predicción/)).toBeInTheDocument();
    expect(screen.getByText("Transición 60 % + Fríos 40 % · 10 números")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Correr" }));
    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(createMock).toHaveBeenCalledWith(expect.objectContaining({ rules: { positions: 3, prizes: [60, 10, 5], minimum_stake: 1 }, strategy: { kind: "mix", components: [{ system: "transition", percent: 60 }, { system: "cold", percent: 40 }], coverage: 10 }, conditions: { capital: 2000, goal: 2800, max_draws: null }, history_sha256: optionsFixture.history.sha256 }));
    expect(await screen.findByText("Resultado")).toBeInTheDocument();
  });
  it("clones the base configuration and exact history SHA without mutating its name", async () => {
    const user = userEvent.setup(); createMock.mockResolvedValue(created); mount("/corridas/nueva?base=run-123");
    expect(await screen.findByRole("heading", { name: "Repetir con cambios" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Nombre/)).toHaveValue("Corrida base"); expect(screen.getByText(runFixture.config.history.sha256)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Correr" }));
    await waitFor(() => expect(createMock).toHaveBeenCalledWith(expect.objectContaining({ name: "Corrida base", history_sha256: runFixture.config.history.sha256 })));
  });
  it("blocks invalid raw integers and date ranges with associated errors", async () => {
    const user = userEvent.setup(); mount(); await screen.findByRole("heading", { name: "Nueva corrida" });
    await user.clear(screen.getByLabelText("Capital (RD$)")); await user.type(screen.getByLabelText("Capital (RD$)"), "1.5");
    await user.clear(screen.getByLabelText("Meta (RD$)")); await user.type(screen.getByLabelText("Meta (RD$)"), "2000");
    await user.click(screen.getByRole("button", { name: "Correr" }));
    expect(createMock).not.toHaveBeenCalled(); expect((await screen.findAllByText(/capital debe ser un entero/)).length).toBeGreaterThan(0);
  });
  it("switches to parity without sending mix components and keeps optional max draws null", async () => {
    const user = userEvent.setup(); createMock.mockResolvedValue(created); mount(); await screen.findByRole("heading", { name: "Nueva corrida" });
    await user.click(screen.getByLabelText("Paridad")); await user.click(screen.getByRole("button", { name: "Correr" }));
    await waitFor(() => expect(createMock).toHaveBeenCalledWith(expect.objectContaining({ strategy: { kind: "parity", components: [], coverage: 10 }, conditions: expect.objectContaining({ max_draws: null }) })));
  });
  it("prevents duplicate submission while the API call is pending", async () => {
    const user = userEvent.setup(); let resolve!: (value: typeof created) => void; createMock.mockReturnValue(new Promise((done) => { resolve = done; })); mount();
    await screen.findByRole("heading", { name: "Nueva corrida" }); const submit = screen.getByRole("button", { name: "Correr" }); await user.click(submit); expect(await screen.findByRole("button", { name: "Calculando…" })).toBeDisabled(); expect(createMock).toHaveBeenCalledTimes(1); resolve(created);
  });
  it("shows server errors and allows editing and retry", async () => {
    const user = userEvent.setup(); createMock.mockRejectedValueOnce(new Error("El servidor rechazó la solicitud.")).mockResolvedValue(created); mount(); await screen.findByRole("heading", { name: "Nueva corrida" });
    await user.click(screen.getByRole("button", { name: "Correr" })); expect(await screen.findByText("El servidor rechazó la solicitud.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Correr" })); await waitFor(() => expect(createMock).toHaveBeenCalledTimes(2));
  });
  it("adds and removes distinct mix systems without leaving the editor", async () => { const user = userEvent.setup(); mount(); await screen.findByLabelText("Sistema 1"); await user.click(screen.getByRole("button", { name: "Agregar sistema" })); expect(screen.getByLabelText("Sistema 3")).toHaveValue("hot"); const chosen = ["Sistema 1", "Sistema 2", "Sistema 3"].map((label) => (screen.getByLabelText(label) as HTMLSelectElement).value); expect(new Set(chosen).size).toBe(3); await user.click(screen.getAllByRole("button", { name: "Quitar sistema" })[2]); expect(screen.queryByLabelText("Sistema 3")).not.toBeInTheDocument(); });
  it("does not substitute defaults if the source run is missing", async () => { const { ApiError } = await import("../../api/client"); getRunMock.mockRejectedValueOnce(new ApiError(404, "La corrida no existe.")); mount("/corridas/nueva?base=missing"); expect(await screen.findByText(/No se pudo cargar la corrida de origen/)).toBeInTheDocument(); expect(screen.queryByLabelText("Capital (RD$)")).not.toBeInTheDocument(); });
  it("has no axe violations in the representative loaded form", async () => { const { container } = mount(); await screen.findByLabelText("Sistema 1"); const { axe } = await import("jest-axe"); expect(await axe(container)).toHaveNoViolations(); });
});
