import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { getRun, getRunOptions, listRunSessions, listSessionBets } from "../../api/runs";
import type { Page, RunSession } from "../../api/types";
import { runFixture, optionsFixture } from "./test-fixtures";
import { ResultPage } from "./ResultPage";

vi.mock("../../api/runs", () => ({ getRun: vi.fn(), getRunOptions: vi.fn(), listRunSessions: vi.fn(), listSessionBets: vi.fn() }));
const getRunMock = vi.mocked(getRun), optionsMock = vi.mocked(getRunOptions), sessionsMock = vi.mocked(listRunSessions), betsMock = vi.mocked(listSessionBets);
const session = { ordinal: 1, outcome: "ruin" as const, start_index: 0, end_index: 1, start_label: "2025-09-02", end_label: "2025-09-03", draws: 2, bets: 51, wagered: 20, paid: 0, final_balance: 1980, net: -20, detail_available: true };
const sessionPage = (offset = 0) => ({ total: 101, offset, limit: 50, items: Array.from({ length: 50 }, (_, index) => ({ ...session, ordinal: offset + index + 1 })) });
const betsPage = (offset = 0) => ({ session: { ...session, detail_available: true }, total: 51, offset, limit: 20, detail_available: true, items: [{ index: offset + 1, label: "2025-09-02 12:00", numbers: [0, 9, 22], results: [9, 22, 41], wagered: 10, paid: 60, balance: 2050 }] });
function mount(path = "/corridas/run-123") { return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/corridas/:id" element={<ResultPage />} /><Route path="*" element={<p>Destino</p>} /></Routes></MemoryRouter>); }
function RouteSwitcher() { const navigate = useNavigate(); return <button onClick={() => navigate("/corridas/run-2")}>Cambiar corrida</button>; }
function mountSwitcher() { return render(<MemoryRouter initialEntries={["/corridas/run-1"]}><RouteSwitcher /><Routes><Route path="/corridas/:id" element={<ResultPage />} /></Routes></MemoryRouter>); }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }

beforeEach(() => {
  vi.clearAllMocks();
  getRunMock.mockResolvedValue(runFixture);
  optionsMock.mockResolvedValue(optionsFixture);
  sessionsMock.mockResolvedValue(sessionPage());
  betsMock.mockResolvedValue(betsPage());
});

describe("run result", () => {
  it("loads the report and first 50 sessions with localized config and honest summary", async () => {
    mount();
    expect(await screen.findByRole("heading", { name: "Corrida base" })).toBeInTheDocument();
    expect(screen.getAllByText(/Transición 60 % \+ Fríos 40 %/)).toHaveLength(2);
    expect(screen.getAllByText("−RD$10")).toHaveLength(2);
    expect(screen.getByText(/no es una predicción ni garantiza resultados futuros/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Repetir con cambios" })).toHaveAttribute("href", "/corridas/nueva?base=run-123");
    expect(screen.getByText(/b{64}/)).toBeInTheDocument();
    expect(screen.getByText(/Cobertura de rankings/).parentElement).toHaveTextContent("1 de 1 sorteos tienen ranking");
    expect(screen.getByText("Motor y fecha").parentElement).toHaveTextContent("Motor v1");
    await waitFor(() => expect(sessionsMock).toHaveBeenCalledWith("run-123", { offset: 0, limit: 50 }, expect.objectContaining({ signal: expect.any(AbortSignal) })));
    expect(screen.getByText("Sesiones: 1–50 de 101 guardadas")).toBeInTheDocument();
  });

  it("uses outcome filtering, resets paging, and explicitly loads bets by selected ordinal", async () => {
    const user = userEvent.setup();
    sessionsMock.mockResolvedValueOnce(sessionPage()).mockResolvedValueOnce(sessionPage(50)).mockResolvedValueOnce(sessionPage()).mockResolvedValue(sessionPage());
    betsMock.mockResolvedValueOnce(betsPage()).mockResolvedValueOnce(betsPage(20)).mockResolvedValueOnce(betsPage()).mockResolvedValueOnce(betsPage(20)).mockResolvedValue(betsPage());
    mount();
    await screen.findByRole("heading", { name: "Corrida base" });
    await user.click(await screen.findByRole("button", { name: "Siguiente sesiones" }));
    await waitFor(() => expect(sessionsMock).toHaveBeenLastCalledWith("run-123", { offset: 50, limit: 50 }, expect.anything()));
    await user.click(screen.getByRole("button", { name: "Anterior sesiones" }));
    await waitFor(() => expect(sessionsMock).toHaveBeenLastCalledWith("run-123", { offset: 0, limit: 50 }, expect.anything()));
    await user.selectOptions(screen.getByLabelText("Filtrar sesiones"), "ruin");
    await waitFor(() => expect(sessionsMock).toHaveBeenLastCalledWith("run-123", { offset: 0, limit: 50, outcome: "ruin" }, expect.anything()));
    await user.click(await screen.findByRole("button", { name: "Ver apuestas de sesión 1" }));
    expect(await screen.findByText("00, 09, 22")).toBeInTheDocument();
    expect(betsMock).toHaveBeenCalledWith("run-123", 1, { offset: 0, limit: 20 }, expect.objectContaining({ signal: expect.any(AbortSignal) }));
    await user.click(screen.getByRole("button", { name: "Siguiente apuestas" }));
    await waitFor(() => expect(betsMock).toHaveBeenLastCalledWith("run-123", 1, { offset: 20, limit: 20 }, expect.anything()));
    await user.click(screen.getByRole("button", { name: "Ver apuestas de sesión 1" }));
    await waitFor(() => expect(betsMock).toHaveBeenLastCalledWith("run-123", 1, { offset: 0, limit: 20 }, expect.anything()));
    await user.click(screen.getByRole("button", { name: "Siguiente apuestas" }));
    await waitFor(() => expect(betsMock).toHaveBeenLastCalledWith("run-123", 1, { offset: 20, limit: 20 }, expect.anything()));
    await user.click(screen.getByRole("button", { name: "Anterior apuestas" }));
    await waitFor(() => expect(betsMock).toHaveBeenLastCalledWith("run-123", 1, { offset: 0, limit: 20 }, expect.anything()));
  });

  it("shows the unavailable-detail explanation without rendering fake bets or a pager", async () => {
    sessionsMock.mockResolvedValue({ ...sessionPage(), items: [{ ...session, detail_available: false }] });
    mount();
    await screen.findByRole("heading", { name: "Corrida base" });
    await userEvent.click(await screen.findByRole("button", { name: "Ver apuestas de sesión 1" }));
    expect(await screen.findByText("Detalle de apuestas no almacenado para esta sesión")).toBeInTheDocument();
    expect(betsMock).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Siguiente apuestas" })).not.toBeInTheDocument();
  });

  it("does not show a pager when the bets endpoint reports unavailable detail despite a nonzero total", async () => {
    betsMock.mockResolvedValue({ ...betsPage(), detail_available: false, items: [] });
    mount();
    await screen.findByRole("heading", { name: "Corrida base" });
    await userEvent.click(await screen.findByRole("button", { name: "Ver apuestas de sesión 1" }));
    expect(await screen.findByText("Detalle de apuestas no almacenado para esta sesión")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Siguiente apuestas" })).not.toBeInTheDocument();
    expect(screen.queryByText("00, 09, 22")).not.toBeInTheDocument();
  });

  it("falls back to safe catalog labels when loading options fails", async () => {
    const unknown = { ...runFixture, config: { ...runFixture.config, strategy: { ...runFixture.config.strategy, components: [{ system: "internal-system-secret", percent: 100 }] } } };
    getRunMock.mockResolvedValue(unknown);
    optionsMock.mockRejectedValue(new Error("catalog offline"));
    mount();
    expect(await screen.findAllByText(/Sistema no disponible 100 %/)).toHaveLength(2);
    expect(screen.queryByText(/internal-system-secret/)).not.toBeInTheDocument();
    expect(screen.getByText(/No se pudo cargar el catálogo actual/)).toBeInTheDocument();
  });

  it("retries failed session and bet pages with their stored page parameters", async () => {
    sessionsMock.mockRejectedValueOnce(new ApiError(500, "Error SQL." )).mockResolvedValue(sessionPage());
    mount();
    await screen.findByRole("heading", { name: "Corrida base" });
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudieron cargar las sesiones.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar sesiones" }));
    await screen.findByRole("button", { name: "Ver apuestas de sesión 1" });
    betsMock.mockRejectedValueOnce(new ApiError(500, "Error SQL." )).mockResolvedValue(betsPage());
    await userEvent.click(screen.getByRole("button", { name: "Ver apuestas de sesión 1" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudieron cargar las apuestas");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar apuestas" }));
    expect(await screen.findByText("00, 09, 22")).toBeInTheDocument();
  });

  it("retries a report 404 and exposes the missing run rather than a placeholder", async () => {
    getRunMock.mockRejectedValueOnce(new ApiError(404, "La corrida no existe."));
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent(/no se pudo cargar esta corrida/i);
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("heading", { name: "Corrida base" })).toBeInTheDocument();
  });

  it("aborts the old report read and ignores its late response after the run ID changes", async () => {
    const oldReport = deferred<typeof runFixture>();
    getRunMock.mockImplementation((id) => id === "run-1" ? oldReport.promise : Promise.resolve({ ...runFixture, id: "run-2", name: "Corrida dos" }));
    mountSwitcher();
    await waitFor(() => expect(getRunMock).toHaveBeenCalledWith("run-1", expect.objectContaining({ signal: expect.any(AbortSignal) })));
    const oldSignal = getRunMock.mock.calls[0][1]?.signal as AbortSignal;
    await userEvent.click(screen.getByRole("button", { name: "Cambiar corrida" }));
    expect(await screen.findByRole("heading", { name: "Corrida dos" })).toBeInTheDocument();
    expect(oldSignal.aborted).toBe(true);
    oldReport.resolve(runFixture);
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Corrida base" })).not.toBeInTheDocument());
  });

  it("aborts old session reads and ignores late rows from the previous run", async () => {
    const oldSessions = deferred<Page<RunSession>>();
    getRunMock.mockImplementation(async (id) => ({ ...runFixture, id, name: id === "run-1" ? "Corrida uno" : "Corrida dos" }));
    sessionsMock.mockImplementation((id) => id === "run-1" ? oldSessions.promise : Promise.resolve({ total: 1, offset: 0, limit: 50, items: [{ ...session, ordinal: 2 }] }));
    mountSwitcher();
    await screen.findByRole("heading", { name: "Corrida uno" });
    await waitFor(() => expect(sessionsMock).toHaveBeenCalledWith("run-1", { offset: 0, limit: 50 }, expect.objectContaining({ signal: expect.any(AbortSignal) })));
    const oldSignal = sessionsMock.mock.calls[0][2]?.signal as AbortSignal;
    await userEvent.click(screen.getByRole("button", { name: "Cambiar corrida" }));
    await screen.findByRole("heading", { name: "Corrida dos" });
    expect(await screen.findByText("Sesión 2")).toBeInTheDocument();
    expect(oldSignal.aborted).toBe(true);
    oldSessions.resolve({ total: 1, offset: 0, limit: 50, items: [{ ...session, ordinal: 1 }] });
    await waitFor(() => expect(screen.queryByText("Sesión 1")).not.toBeInTheDocument());
  });

  it("has no axe violations in the loaded result and no-detail state", async () => {
    const loaded = mount();
    await screen.findByRole("heading", { name: "Corrida base" });
    const { axe } = await import("jest-axe");
    expect(await axe(loaded.container)).toHaveNoViolations();
    loaded.unmount();
    sessionsMock.mockResolvedValue({ ...sessionPage(), items: [{ ...session, detail_available: false }] });
    const unavailable = mount();
    await screen.findByRole("heading", { name: "Corrida base" });
    await userEvent.click(await screen.findByRole("button", { name: "Ver apuestas de sesión 1" }));
    expect(await axe(unavailable.container)).toHaveNoViolations();
    unavailable.unmount();
  });
});
