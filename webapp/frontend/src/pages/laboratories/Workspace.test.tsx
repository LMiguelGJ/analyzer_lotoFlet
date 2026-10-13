import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NetworkError, ApiError } from "../../api/client";
import * as api from "../../api/laboratories";
import { getReferenceLabs } from "../../api/referenceLabs";
import { Workspace } from "./Workspace";

vi.mock("../../api/laboratories");
vi.mock("../../api/referenceLabs", () => ({ getReferenceLabs: vi.fn() }));

const SHA = "d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711";
const ID = "3f2b8c4e-1a2b-4c3d-8e9f-0a1b2c3d4e5f";
const config = { schema_version: 1, system: "transition", coverage: 1, stake_style: "bold" as const, capital: 2000, goal: 2800, prizes: [80, 8, 4, 2, 1], window_start: "2025-09-02 05:10", window_end: "2026-09-25 18:20" };
const definition = { schema_version: 1, id: ID, name: "Transición propia", reference_id: null, config };
const totals = { completed: 3, incomplete: 1, goals: 2, ruins: 1, sessions_total: 4, total_wagered: 1000, total_paid: 1100, total_net: 100, total_steps: 10, mean_net_closed: 50 };
const runItem = { id: "run-1", created_at: "2026-10-01T10:00:00Z", summary: { eligible_draws: 10, gaps: 1, totals } };
const run = { id: "run-1", owner_laboratory_id: ID, lab_id: ID, contract_version: 1, created_at: "2026-10-01T10:00:00Z", snapshot: { schema_version: 1, kind: "owned_laboratory_run" as const, definition, provenance: { history_sha256: SHA, rankings_sha256: "b".repeat(64), history_origin: "frozen" as const } }, summary: { eligible_draws: 10, gaps: 1, first: null, last: null, session_sha256: "c".repeat(64), session_count: 4, totals }, capabilities: { session_summary: true as const, per_bet_trace: false as const } };

const m = vi.mocked(api);
function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/laboratorios" element={<Workspace />} />
    <Route path="/laboratorios/:labId" element={<Workspace />} />
  </Routes></MemoryRouter>);
}
beforeEach(() => {
  vi.resetAllMocks();
  m.listLaboratories.mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [definition] });
  m.getLaboratory.mockResolvedValue({ definition, owned_run_count: 1, owned_session_count: 4 });
  m.listLaboratoryRuns.mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [runItem] });
  m.getLaboratoryRun.mockResolvedValue(run);
  m.listLaboratorySessions.mockResolvedValue({ run_id: "run-1", total: 1, offset: 0, limit: 50, items: [{ ordinal: 0, summary: { outcome: "goal", start_index: 0, end_index: 3, draws: 4, final_balance: 2800, wagered: 100, paid: 900 } }] });
  vi.mocked(getReferenceLabs).mockResolvedValue({ contract_version: 1, reference_history: { sha256: SHA, origin: "frozen_reference", draws: 1, ranked_draws: 1, first_label: null, last_label: null }, capabilities: { session_summary: true, per_bet_trace: false }, items: [] });
});

describe("laboratory workspace", () => {
  it("lists saved laboratories at the side with a direct route each and an invitation when none are selected", async () => {
    renderAt("/laboratorios");
    const link = await screen.findByRole("link", { name: /Transición propia/ });
    expect(link).toHaveAttribute("href", `/laboratorios/${ID}`);
    expect(screen.getByRole("heading", { name: "Elegí un laboratorio" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Nuevo laboratorio" })).toHaveAttribute("href", "/laboratorios/nuevo");
  });

  it("marks the workspace as having a selection so narrow screens can show the content first", async () => {
    const { container, unmount } = renderAt("/laboratorios");
    await screen.findByRole("link", { name: /Transición propia/ });
    expect(container.querySelector(".lab-workspace")).toHaveAttribute("data-selected", "false");
    unmount();
    const created = renderAt("/laboratorios/nuevo");
    await screen.findByRole("button", { name: "Crear laboratorio" });
    expect(created.container.querySelector(".lab-workspace")).toHaveAttribute("data-selected", "true");
  });

  it("shows an honest empty state instead of resurrecting any laboratory", async () => {
    m.listLaboratories.mockResolvedValue({ total: 0, offset: 0, limit: 20, items: [] });
    renderAt("/laboratorios");
    expect(await screen.findByText(/No hay laboratorios guardados/)).toBeInTheDocument();
  });

  it("validates before sending and creates with the exact payload", async () => {
    m.createLaboratory.mockResolvedValue(definition);
    const user = userEvent.setup();
    renderAt("/laboratorios/nuevo");
    await user.click(await screen.findByRole("button", { name: "Crear laboratorio" }));
    expect(await screen.findByText(/Escribí un nombre/)).toBeInTheDocument();
    expect(m.createLaboratory).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Nombre"), "Transición propia");
    await user.click(screen.getByRole("button", { name: "Crear laboratorio" }));
    await waitFor(() => expect(m.createLaboratory).toHaveBeenCalledTimes(1));
    expect(m.createLaboratory).toHaveBeenCalledWith("Transición propia", config);
    expect(await screen.findByRole("heading", { name: "Transición propia", level: 2 })).toBeInTheDocument();
  });

  it("keeps a server conflict visible in the form", async () => {
    m.createLaboratory.mockRejectedValue(new ApiError(409, "No se pudo crear el laboratorio por un conflicto o límite de cuota."));
    const user = userEvent.setup();
    renderAt("/laboratorios/nuevo");
    await user.type(await screen.findByLabelText("Nombre"), "Repetido");
    await user.click(screen.getByRole("button", { name: "Crear laboratorio" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("conflicto o límite de cuota");
  });

  it("executes with the frozen history digest and opens the stored result", async () => {
    m.createLaboratoryRun.mockResolvedValue(run);
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    const execute = await screen.findByRole("button", { name: "Ejecutar laboratorio" });
    await waitFor(() => expect(execute).toBeEnabled());
    await user.click(execute);
    await waitFor(() => expect(m.createLaboratoryRun).toHaveBeenCalledTimes(1));
    expect(m.createLaboratoryRun.mock.calls[0].slice(0, 2)).toEqual([ID, SHA]);
    expect(await screen.findByRole("heading", { name: "Resultado guardado" })).toBeInTheDocument();
    expect(screen.getByText(SHA, { selector: ".reference-sha" })).toBeInTheDocument();
    expect(screen.getByText("+RD$50,00")).toBeInTheDocument();
  });

  it("never retries an ambiguous network failure and asks the user to reconcile", async () => {
    m.createLaboratoryRun.mockRejectedValue(new NetworkError());
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    const execute = await screen.findByRole("button", { name: "Ejecutar laboratorio" });
    await waitFor(() => expect(execute).toBeEnabled());
    await user.click(execute);
    expect(await screen.findByText(/No hay confirmación de si el servidor guardó/)).toBeInTheDocument();
    expect(m.createLaboratoryRun).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Ejecutar laboratorio" })).toBeDisabled();
  });

  it("names the runs that will be lost and deletes with the confirmed count", async () => {
    m.deleteLaboratory.mockResolvedValue({ id: ID, name: "Transición propia" });
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Eliminar laboratorio" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("1 corrida guardada y 4 sesiones");
    expect(dialog).toHaveTextContent("no se vuelve a crear solo");
    await user.click(within(dialog).getByRole("button", { name: "Eliminar laboratorio y corridas" }));
    await waitFor(() => expect(m.deleteLaboratory).toHaveBeenCalledWith(ID, 1));
    expect(await screen.findByRole("heading", { name: "Elegí un laboratorio" })).toBeInTheDocument();
  });

  it("reloads after a changed-run-count conflict instead of deleting blindly", async () => {
    m.deleteLaboratory.mockRejectedValue(new ApiError(409, "El laboratorio cambió; recárgalo antes de eliminarlo."));
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Eliminar laboratorio" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Eliminar laboratorio y corridas" }));
    expect(await screen.findByText(/recárgalo antes de eliminarlo/)).toBeInTheDocument();
    await waitFor(() => expect(m.getLaboratory.mock.calls.length).toBeGreaterThan(1));
  });

  it("uses correct singular and plural forms for counts", async () => {
    renderAt(`/laboratorios/${ID}`);
    expect(await screen.findByText("1 corrida")).toBeInTheDocument();
    expect(screen.getByText(/4 · 1 incompleta$/)).toBeInTheDocument();
    expect(screen.getByText("1 laboratorio")).toBeInTheDocument();
  });

  it("has no detectable accessibility violations in the create form", async () => {
    renderAt("/laboratorios/nuevo");
    await screen.findByRole("button", { name: "Crear laboratorio" });
    const { axe } = await import("jest-axe");
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
