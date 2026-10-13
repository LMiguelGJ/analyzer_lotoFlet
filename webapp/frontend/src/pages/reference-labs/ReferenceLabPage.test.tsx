import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, NetworkError } from "../../api/client";
import { createReferenceRun, deleteReferenceRun, getReferenceLab, getReferenceRun, listReferenceRuns, listReferenceSessions } from "../../api/referenceLabs";
import type { ReferenceLabDetail, ReferenceRun, ReferenceSessionPage } from "../../api/referenceLabs";
import { ReferenceLabPage } from "./ReferenceLabPage";
vi.mock("../../api/referenceLabs", () => ({ getReferenceLab: vi.fn(), listReferenceRuns: vi.fn(), createReferenceRun: vi.fn(), getReferenceRun: vi.fn(), listReferenceSessions: vi.fn(), deleteReferenceRun: vi.fn() }));

const sha = "d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711";
const lab: ReferenceLabDetail = { contract_version: 1, reference_history: { sha256: sha, origin: "frozen_reference", draws: 105426, ranked_draws: 100000, first_label: "2025-03-05", last_label: "2026-09-25" }, capabilities: { session_summary: true, per_bet_trace: false }, lab: { lab_id: "transicion_1_audaz", system: "transition", coverage: 1, stake_style: "bold", selection_kind: "ranking", capital: 2000, goal: 2800, prizes: [80, 8, 4, 2, 1], window: { start: "2025-09-02 05:10", end: "2026-09-25 18:20" }, duration_cap: null, editable: false } };
const run: ReferenceRun = { id: "11111111-1111-4111-8111-111111111111", lab_id: "transicion_1_audaz", contract_version: 1, created_at: "2026-10-11T12:00:00.000Z", config: lab.lab, provenance: { history_sha256: sha, history_origin: "frozen" }, summary: { eligible_draws: 10, gaps: 0, first: "2025-09-02", last: "2025-09-12", session_sha256: "f".repeat(64), session_count: 2, totals: { completed: 1, incomplete: 1, goals: 1, ruins: 0, sessions_total: 2, total_wagered: 10, total_paid: 12, total_net: 2, total_steps: 10, mean_net_closed: 5.5 } }, capabilities: { session_summary: true, per_bet_trace: false } };
const sessionPage: ReferenceSessionPage = { run_id: run.id, total: 2, offset: 0, limit: 50, items: [{ ordinal: 0, summary: { outcome: "goal", start_index: 0, end_index: 4, draws: 5, final_balance: 2005, wagered: 10, paid: 15 } }, { ordinal: 1, summary: { outcome: "incomplete", start_index: 5, end_index: 9, draws: 5, final_balance: 1997, wagered: 0, paid: 0 } }] };
const mocks = { getLab: vi.mocked(getReferenceLab), listRuns: vi.mocked(listReferenceRuns), create: vi.mocked(createReferenceRun), getRun: vi.mocked(getReferenceRun), sessions: vi.mocked(listReferenceSessions), remove: vi.mocked(deleteReferenceRun) };
beforeEach(() => {
  Object.values(mocks).forEach((mock) => mock.mockReset());
  mocks.getLab.mockResolvedValue(lab); mocks.listRuns.mockResolvedValue({ total: 0, offset: 0, limit: 20, items: [] });
  mocks.create.mockResolvedValue(run); mocks.getRun.mockResolvedValue(run); mocks.sessions.mockResolvedValue(sessionPage); mocks.remove.mockResolvedValue(undefined);
});
function renderPage() { return render(<MemoryRouter initialEntries={["/laboratorios/transicion_1_audaz"]}><Routes><Route path="/laboratorios/:labId" element={<ReferenceLabPage />} /></Routes></MemoryRouter>); }

describe("first faithful reference laboratory page", () => {
  it("shows immutable contract, executes only with source SHA, and distinguishes incomplete from closed means", async () => {
    const user = userEvent.setup();
    const { container } = renderPage();
    expect(await screen.findByRole("heading", { name: "Transición · 1 número · Audaz" })).toBeInTheDocument();
    const { axe } = await import("jest-axe");
    expect(await axe(container)).toHaveNoViolations();
    expect(screen.getByText("+RD$2.000")).toBeInTheDocument();
    expect(screen.getByText("Sin límite")).toBeInTheDocument();
    expect(screen.getByText(sha)).toBeInTheDocument();
    expect(await screen.findByText("Todavía no hay corridas guardadas para este laboratorio.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ejecutar laboratorio" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith("transicion_1_audaz", sha, expect.objectContaining({ signal: expect.any(AbortSignal) })));
    expect(await screen.findByRole("heading", { name: "Resultado guardado" })).toBeInTheDocument();
    expect(screen.getByText("+RD$5,5")).toBeInTheDocument();
    expect(screen.getByText(/Las sesiones incompletas aportan a los totales/)).toBeInTheDocument();
    expect(screen.getByText(/no incluye el detalle de cada apuesta/)).toBeInTheDocument();
    expect(mocks.sessions).toHaveBeenCalledWith("transicion_1_audaz", run.id, { offset: 0, limit: 50 }, expect.any(Object));
  });

  it("does not resubmit after an ambiguous network failure and requires explicit reconciliation", async () => {
    const user = userEvent.setup();
    mocks.create.mockRejectedValueOnce(new NetworkError());
    renderPage();
    expect(await screen.findByText("Todavía no hay corridas guardadas para este laboratorio.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ejecutar laboratorio" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("alert")).toHaveTextContent("No hay confirmación de si el servidor guardó esta ejecución");
    expect(mocks.create).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Ejecutar laboratorio" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Actualizar corridas guardadas" }));
    await waitFor(() => expect(mocks.listRuns).toHaveBeenCalledTimes(2));
    expect(mocks.create).toHaveBeenCalledTimes(1);
  });

  it("keeps an unknown lab error on its named route instead of redirecting to Corridas", async () => {
    mocks.getLab.mockRejectedValueOnce(new ApiError(404, "El laboratorio de referencia no existe."));
    render(<MemoryRouter initialEntries={["/laboratorios/desconocido"]}><Routes><Route path="/laboratorios/:labId" element={<ReferenceLabPage />} /><Route path="/corridas" element={<p>Corridas</p>} /></Routes></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("El laboratorio de referencia no existe.");
    expect(screen.queryByText("Corridas")).not.toBeInTheDocument();
  });
});
