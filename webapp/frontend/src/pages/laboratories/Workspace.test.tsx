import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NetworkError, ApiError } from "../../api/client";
import * as api from "../../api/laboratories";
import { getReferenceLabs } from "../../api/referenceLabs";
import { Workspace } from "./Workspace";

vi.mock("../../api/laboratories", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/laboratories")>();
  return {
    ...actual,
    listLaboratories: vi.fn(),
    createLaboratory: vi.fn(),
    getLaboratory: vi.fn(),
    deleteLaboratory: vi.fn(),
    listLaboratoryRuns: vi.fn(),
    createLaboratoryRun: vi.fn(actual.createLaboratoryRun),
    getLaboratoryRun: vi.fn(),
    listLaboratorySessions: vi.fn(),
  };
});
vi.mock("../../api/referenceLabs", () => ({ getReferenceLabs: vi.fn() }));

const SHA = "d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711";
const ID = "3f2b8c4e-1a2b-4c3d-8e9f-0a1b2c3d4e5f";
const config = { schema_version: 1, system: "transition", coverage: 1, stake_style: "bold" as const, capital: 2000, goal: 2800, prizes: [80, 8, 4, 2, 1], window_start: "2025-09-02 05:10", window_end: "2026-09-25 18:20" };
const definition = { schema_version: 1, id: ID, name: "Transición propia", reference_id: null, config };
const totals = { completed: 3, incomplete: 1, goals: 2, ruins: 1, sessions_total: 4, total_wagered: 1000, total_paid: 1100, total_net: 100, total_steps: 10, mean_net_closed: 50 };
const runItem = { id: "run-1", created_at: "2026-10-01T10:00:00Z", summary: { eligible_draws: 10, gaps: 1, totals } };
const run = { id: "run-1", owner_laboratory_id: ID, lab_id: ID, contract_version: 1, created_at: "2026-10-01T10:00:00Z", snapshot: { schema_version: 1, kind: "owned_laboratory_run" as const, definition, provenance: { history_sha256: SHA, rankings_sha256: "b".repeat(64), history_origin: "frozen" as const } }, summary: { eligible_draws: 10, gaps: 1, first: null, last: null, session_sha256: "c".repeat(64), session_count: 4, wallet: { policy: "retain-gains-top-up-v1" as const, out_of_pocket: 2000, final_wealth: 2800 }, totals }, capabilities: { session_summary: true as const, per_bet_trace: false as const } };

const m = vi.mocked(api);
function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/laboratorios" element={<Workspace />} />
    <Route path="/laboratorios/:labId" element={<Workspace />} />
  </Routes></MemoryRouter>);
}
beforeEach(() => {
  vi.unstubAllGlobals();
  vi.resetAllMocks();
  m.listLaboratories.mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [definition] });
  m.getLaboratory.mockResolvedValue({ definition, owned_run_count: 1, owned_session_count: 4 });
  m.listLaboratoryRuns.mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [runItem] });
  m.getLaboratoryRun.mockResolvedValue(run);
  m.listLaboratorySessions.mockResolvedValue({ run_id: "run-1", total: 1, offset: 0, limit: 50, items: [{ ordinal: 0, summary: { outcome: "goal", start_index: 0, end_index: 3, draws: 4, final_balance: 2800, wagered: 100, paid: 900 } }] });
  vi.mocked(getReferenceLabs).mockResolvedValue({ contract_version: 1, reference_history: { sha256: SHA, origin: "frozen_reference", draws: 1, ranked_draws: 1, first_label: null, last_label: null }, capabilities: { session_summary: true, per_bet_trace: false }, items: [] });
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

const savedRuns = { total: 1, offset: 0, limit: 20, items: [runItem] };

async function makeUncertain(user: ReturnType<typeof userEvent.setup>) {
  m.createLaboratoryRun.mockRejectedValue(new NetworkError());
  const execute = await screen.findByRole("button", { name: "Ejecutar laboratorio" });
  await waitFor(() => expect(execute).toBeEnabled());
  await user.click(execute);
  await screen.findByText(/No hay confirmación de si el servidor guardó/);
  return execute;
}

function viewport(width: number) {
  let compact = width <= 860;
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  const media = {
    get matches() { return compact; }, media: "(max-width: 860px)",
    addEventListener: vi.fn((_name: string, listener: (event: MediaQueryListEvent) => void) => listeners.add(listener)),
    removeEventListener: vi.fn((_name: string, listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener)),
  };
  vi.stubGlobal("matchMedia", vi.fn(() => media));
  return { media, resize(next: number) { compact = next <= 860; listeners.forEach((listener) => listener({ matches: compact } as MediaQueryListEvent)); } };
}

describe("laboratory workspace", () => {
  it("U5 reorders real DOM at 860/861 while preserving draft, focus and requests", async () => {
    const screenSize = viewport(861);
    const user = userEvent.setup();
    const { container, unmount } = renderAt("/laboratorios/nuevo");
    const input = await screen.findByLabelText("Nombre");
    await user.type(input, "Borrador");
    const workspace = container.querySelector(".lab-workspace")!;
    expect(workspace.children[0]).toHaveClass("lab-sidebar");
    await act(async () => screenSize.resize(860));
    expect(workspace.children[0]).toHaveClass("lab-stage");
    expect(screen.getByLabelText("Nombre")).toBe(input);
    expect(input).toHaveValue("Borrador");
    expect(input).toHaveFocus();
    await act(async () => screenSize.resize(861));
    expect(workspace.children[0]).toHaveClass("lab-sidebar");
    expect(input).toHaveFocus();
    expect(m.listLaboratories).toHaveBeenCalledTimes(1);
    expect(m.createLaboratory).not.toHaveBeenCalled();
    expect(m.createLaboratoryRun).not.toHaveBeenCalled();
    unmount();
    expect(screenSize.media.removeEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });

  it("U5 keeps the unselected mobile list first and focuses a user-selected panel", async () => {
    viewport(860);
    const user = userEvent.setup();
    const { container } = renderAt("/laboratorios");
    await screen.findByRole("link", { name: "Nuevo laboratorio" });
    const workspace = container.querySelector(".lab-workspace")!;
    expect(workspace.children[0]).toHaveClass("lab-sidebar");
    await user.click(screen.getByRole("link", { name: "Nuevo laboratorio" }));
    expect(workspace.children[0]).toHaveClass("lab-stage");
    expect(workspace.children[0]).toHaveFocus();
    expect(m.listLaboratories).toHaveBeenCalledTimes(1);
  });

  it("U5 focuses only after user navigation, not initial load or result refresh", async () => {
    viewport(861);
    const user = userEvent.setup();
    const { container } = renderAt("/laboratorios");
    const link = await screen.findByRole("link", { name: /Transición propia/ });
    const stage = container.querySelector(".lab-stage")!;
    expect(stage).not.toHaveFocus();
    await user.click(link);
    expect(stage).toHaveFocus();
    const view = await screen.findByRole("button", { name: "Ver resultado" });
    await user.click(view);
    await screen.findByRole("heading", { name: "Resultado guardado" });
    expect(view).toHaveFocus();
  });

  it("U5 announces invalid fields and focuses the first without submitting", async () => {
    const user = userEvent.setup();
    renderAt("/laboratorios/nuevo");
    const coverage = await screen.findByLabelText("Cobertura (números)");
    await user.clear(coverage);
    await user.type(coverage, "0");
    await user.click(screen.getByRole("button", { name: "Crear laboratorio" }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByRole("link", { name: "Nombre" })).toBeInTheDocument();
    expect(screen.getByLabelText("Nombre")).toHaveFocus();
    expect(m.createLaboratory).not.toHaveBeenCalled();
    await user.click(within(alert).getByRole("link", { name: "Cobertura (números)" }));
    expect(coverage).toHaveFocus();
    expect(coverage).toHaveAttribute("aria-describedby", expect.stringContaining("lab-coverage-error"));
    expect(coverage).toHaveValue("0");
  });

  it.each([
    ["Ventana: inicio", "Ventana: inicio", "fecha inválida", "lab-window-start"],
    ["Ventana: fin", "Ventana: fin", "fecha inválida", "lab-window-end"],
    ["1.º", "Premio 1.º", "0", "lab-prize_1"],
  ])("U5 targets invalid field links for %s", async (label, errorLabel, value, id) => {
    const user = userEvent.setup();
    renderAt("/laboratorios/nuevo");
    const name = await screen.findByLabelText("Nombre");
    await user.type(name, "Fechas de prueba");
    const input = screen.getByLabelText(label);
    await user.clear(input);
    await user.type(input, value);
    await user.click(screen.getByRole("button", { name: "Crear laboratorio" }));
    const alert = await screen.findByRole("alert");
    expect(input).toHaveFocus();
    await user.click(name);
    const link = within(alert).getByRole("link", { name: errorLabel });
    expect(link).toHaveAttribute("href", `#${id}`);
    await user.click(link);
    expect(input).toHaveFocus();
    expect(input).toHaveValue(value);
    expect(input).toHaveAttribute("aria-describedby", expect.stringContaining(`${id}-error`));
    expect(name).toHaveValue("Fechas de prueba");
    expect(m.createLaboratory).not.toHaveBeenCalled();
    expect(m.createLaboratoryRun).not.toHaveBeenCalled();
  });

  it("U5 targets a reversed window error without submitting", async () => {
    const user = userEvent.setup();
    renderAt("/laboratorios/nuevo");
    const name = await screen.findByLabelText("Nombre");
    await user.type(name, "Ventana invertida");
    const start = screen.getByLabelText("Ventana: inicio");
    const end = screen.getByLabelText("Ventana: fin");
    await user.clear(start);
    await user.type(start, "2026-09-26 00:00");
    await user.clear(end);
    await user.type(end, "2026-09-25 18:20");
    await user.click(screen.getByRole("button", { name: "Crear laboratorio" }));
    const alert = await screen.findByRole("alert");
    expect(end).toHaveFocus();
    await user.click(name);
    const link = within(alert).getByRole("link", { name: "Ventana: fin" });
    expect(link).toHaveAttribute("href", "#lab-window-end");
    await user.click(link);
    expect(end).toHaveFocus();
    expect(start).toHaveValue("2026-09-26 00:00");
    expect(end).toHaveValue("2026-09-25 18:20");
    expect(m.createLaboratory).not.toHaveBeenCalled();
    expect(m.createLaboratoryRun).not.toHaveBeenCalled();
  });

  it("U5 preserves wallet totals while paging sessions without refetching the run", async () => {
    m.getLaboratoryRun.mockResolvedValue({ ...run, summary: { ...run.summary, wallet: { policy: "retain-gains-top-up-v1", out_of_pocket: 2000, final_wealth: 2100 }, totals: { ...totals, total_net: 100 } } });
    const screenSize = viewport(861);
    const user = userEvent.setup();
    m.listLaboratorySessions.mockImplementation(async (_lab, _run, params) => ({ run_id: "run-1", total: 51, offset: params?.offset ?? 0, limit: 50, items: [{ ordinal: params?.offset ?? 0, summary: { outcome: "goal", start_index: 0, end_index: 3, draws: 4, final_balance: 2800, wagered: 100, paid: 900 } }] }));
    const { container } = renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    await screen.findByRole("region", { name: "Resúmenes de sesiones" });
    expect(screen.getByText("Aportado de tu bolsillo").parentElement).toHaveTextContent("RD$2.000");
    expect(screen.getByText("Patrimonio al final").parentElement).toHaveTextContent("RD$2.100");
    await user.click(within(screen.getByRole("navigation", { name: "Paginación de sesiones" })).getByRole("button", { name: "Siguiente" }));
    await screen.findByRole("heading", { name: "Sesiones 51–51 de 51" });
    expect(screen.getByText("Aportado de tu bolsillo").parentElement).toHaveTextContent("RD$2.000");
    expect(screen.getByText("Patrimonio al final").parentElement).toHaveTextContent("RD$2.100");
    await act(async () => screenSize.resize(860));
    expect(container.querySelector(".lab-workspace")!.children[0]).toHaveClass("lab-stage");
    expect(screen.getByRole("heading", { name: "Sesiones 51–51 de 51" })).toBeInTheDocument();
    expect(m.getLaboratory).toHaveBeenCalledTimes(1);
    expect(m.getLaboratoryRun).toHaveBeenCalledTimes(1);
    expect(m.listLaboratorySessions).toHaveBeenCalledTimes(2);
    expect(m.createLaboratoryRun).not.toHaveBeenCalled();
  });

  it.each([
    [-1482496, 30303350, "−4,89 %"],
    [50, 100, "+50,00 %"],
    [0, 100, "+0,00 %"],
    [0, 0, "No disponible"],
    [-1, 1000000, "+0,00 %"],
  ])("U4 presents ROI without changing totals (%s/%s)", async (net, wagered, expected) => {
    m.getLaboratoryRun.mockResolvedValue({ ...run, summary: { ...run.summary, totals: { ...totals, total_net: net, total_wagered: wagered } } });
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    const result = await screen.findByRole("region", { name: "Resultado guardado" });
    expect(within(result).getByText("Retorno sobre apostado").parentElement).toHaveTextContent(expected);
    expect(within(result).getByText("Media neta de cerradas").parentElement).toHaveTextContent("+RD$50,00");
    expect(within(result).getByText("Incompletas").parentElement).toHaveTextContent("1");
  });

  it("shows the certified three-value wallet and keeps existing metrics in their disclosures", async () => {
    m.getLaboratoryRun.mockResolvedValue({ ...run, summary: { ...run.summary, totals: { ...totals, total_net: 800 } } });
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    const result = await screen.findByRole("region", { name: "Resultado guardado" });
    expect(within(result).getByRole("heading", { name: "Tu dinero · Simulación" })).toBeInTheDocument();
    for (const [label, value] of [["Aportado de tu bolsillo", "RD$2.000"], ["Patrimonio al final", "RD$2.800"], ["Ganancia / pérdida", "+RD$800"]]) {
      expect(within(result).getByText(label).parentElement).toHaveTextContent(value);
    }
    expect(within(result).getByText("Movimiento de apuestas")).toBeInTheDocument();
    expect(within(result).getByText("Volumen apostado").parentElement).toHaveTextContent("+RD$1.000");
    expect(within(result).getByText("Premios recibidos").parentElement).toHaveTextContent("+RD$1.100");
    const help = within(result).getByText("ⓘ Cómo se calcula").closest("details")!;
    expect(help).not.toHaveAttribute("open");
    expect(help).toHaveTextContent("no hay retiros");
    const sessionDetails = within(result).getByText("Detalle de sesiones").closest("details")!;
    expect(sessionDetails).not.toHaveAttribute("open");
    expect(sessionDetails).toHaveTextContent("Media neta de cerradas");
    expect(within(result).queryByText("Neto total")).not.toBeInTheDocument();
  });

  it.each([
    ["absent", undefined],
    ["unknown policy", { policy: "future-policy", out_of_pocket: 2000, final_wealth: 2800 } as unknown as typeof run.summary.wallet],
    ["inconsistent", { policy: "retain-gains-top-up-v1" as const, out_of_pocket: 2000, final_wealth: 2800 }],
  ])("shows unavailable wallet values for %s without hiding existing totals", async (_case, wallet) => {
    m.getLaboratoryRun.mockResolvedValue({ ...run, summary: { ...run.summary, wallet, totals: { ...totals, total_net: 100 } } });
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    const result = await screen.findByRole("region", { name: "Resultado guardado" });
    expect(within(result).getByText("Aportado de tu bolsillo").parentElement).toHaveTextContent("No disponible");
    expect(within(result).getByText("Patrimonio al final").parentElement).toHaveTextContent("No disponible");
    expect(within(result).getByText("Ganancia / pérdida").parentElement).toHaveTextContent("+RD$100");
    expect(within(result).getByText("Volumen apostado").parentElement).toHaveTextContent("+RD$1.000");
  });

  it("U4 shows selected coverage and complete reproduction provenance", async () => {
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    expect(await screen.findByText("1 número seleccionado")).toBeInTheDocument();
    expect(screen.queryByText("1 de 50 números")).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    const result = await screen.findByRole("region", { name: "Resultado guardado" });
    expect(within(result).getByText("Sorteos evaluados").parentElement).toHaveTextContent("10");
    expect(within(result).getByText("Sin ranking entre extremos").parentElement).toHaveTextContent("1");
    const disclosure = within(result).getByText("Datos de la reproducción").closest("details")!;
    expect(disclosure).toHaveTextContent(SHA);
    expect(disclosure).toHaveTextContent("b".repeat(64));
    expect(disclosure).toHaveTextContent("c".repeat(64));
    expect(disclosure).toHaveTextContent(config.window_start);
  });

  it("U4 renders empty sessions without an inverted range", async () => {
    m.listLaboratorySessions.mockResolvedValue({ run_id: "run-1", total: 0, offset: 0, limit: 50, items: [] });
    m.getLaboratoryRun.mockResolvedValue({ ...run, summary: { ...run.summary, eligible_draws: 0, first: null, last: null, session_count: 0, totals: { ...totals, completed: 0, incomplete: 0, goals: 0, ruins: 0, sessions_total: 0, total_wagered: 0, total_paid: 0, total_net: 0, mean_net_closed: null } } });
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    expect(await screen.findByRole("heading", { name: "Sesiones 0 de 0" })).toBeInTheDocument();
    expect(screen.getByText("Sin sorteos elegibles")).toBeInTheDocument();
    expect(screen.queryByText(/Sesiones 1–0/)).not.toBeInTheDocument();
  });

  it.each(["success", "failure", "abort"])("U2 reconciles only after the current fresh list succeeds: %s", async (outcome) => {
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    const execute = await makeUncertain(user);
    const fresh = deferred<typeof savedRuns>();
    m.listLaboratoryRuns.mockImplementationOnce(() => fresh.promise);
    await user.click(screen.getByRole("button", { name: "Actualizar corridas guardadas" }));
    expect(execute).toBeDisabled();
    expect(screen.getByRole("button", { name: "Actualizar corridas guardadas" })).toBeDisabled();
    expect(m.createLaboratoryRun).toHaveBeenCalledTimes(1);
    expect(m.listLaboratoryRuns.mock.calls.at(-1)?.slice(0, 2)).toEqual([ID, { offset: 0, limit: 20 }]);
    await act(async () => {
      if (outcome === "success") fresh.resolve(savedRuns);
      else fresh.reject(outcome === "abort" ? new DOMException("Aborted", "AbortError") : new NetworkError());
    });
    if (outcome !== "success") {
      expect(execute).toBeDisabled();
      expect(screen.getByText(/No hay confirmación de si el servidor guardó/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Actualizar corridas guardadas" })).toBeEnabled();
      await user.click(screen.getByRole("button", { name: "Actualizar corridas guardadas" }));
    }
    await waitFor(() => expect(execute).toBeEnabled());
    expect(m.createLaboratoryRun).toHaveBeenCalledTimes(1);
    m.createLaboratoryRun.mockResolvedValue(run);
    await user.click(execute);
    await waitFor(() => expect(m.createLaboratoryRun).toHaveBeenCalledTimes(2));
  });

  it("U2 ignores a stale reconciliation after changing laboratories", async () => {
    const other = { ...definition, id: "other-lab", name: "Otro laboratorio" };
    m.listLaboratories.mockResolvedValue({ total: 2, offset: 0, limit: 20, items: [definition, other] });
    m.getLaboratory.mockImplementation(async (id) => ({ definition: id === ID ? definition : other, owned_run_count: 1, owned_session_count: 4 }));
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await makeUncertain(user);
    const stale = deferred<typeof savedRuns>();
    m.listLaboratoryRuns.mockImplementationOnce(() => stale.promise);
    await user.click(screen.getByRole("button", { name: "Actualizar corridas guardadas" }));
    await user.click(screen.getByRole("link", { name: /Otro laboratorio/ }));
    const execute = await makeUncertain(user);
    const current = deferred<typeof savedRuns>();
    m.listLaboratoryRuns.mockImplementationOnce(() => current.promise);
    await user.click(screen.getByRole("button", { name: "Actualizar corridas guardadas" }));
    await act(async () => stale.resolve(savedRuns));
    expect(execute).toBeDisabled();
    expect(screen.getByRole("button", { name: "Actualizar corridas guardadas" })).toBeDisabled();
    expect(m.createLaboratoryRun).toHaveBeenCalledTimes(2);
    await act(async () => current.resolve(savedRuns));
    await waitFor(() => expect(execute).toBeEnabled());
  });

  it("U2 keeps immutable details while paging and retries only failed sessions", async () => {
    const first = { run_id: "run-1", total: 51, offset: 0, limit: 50, items: [{ ordinal: 0, summary: { outcome: "goal" as const, start_index: 0, end_index: 3, draws: 4, final_balance: 2800, wagered: 100, paid: 900 } }] };
    m.listLaboratorySessions.mockResolvedValue(first);
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    await screen.findByRole("region", { name: "Resúmenes de sesiones" });
    const pending = deferred<typeof first>();
    m.listLaboratorySessions.mockImplementationOnce(() => pending.promise);
    await user.click(within(screen.getByRole("navigation", { name: "Paginación de sesiones" })).getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("heading", { name: "Resultado guardado" })).toBeInTheDocument();
    expect(m.getLaboratoryRun).toHaveBeenCalledTimes(1);
    await act(async () => pending.reject(new NetworkError()));
    const error = await screen.findByRole("alert");
    expect(screen.getByRole("heading", { name: "Resultado guardado" })).toBeInTheDocument();
    m.listLaboratorySessions.mockResolvedValue({ ...first, offset: 50, items: [{ ...first.items[0], ordinal: 50 }] });
    await user.click(within(error).getByRole("button", { name: "Reintentar" }));
    await screen.findByRole("heading", { name: "Sesiones 51–51 de 51" });
    expect(m.getLaboratoryRun).toHaveBeenCalledTimes(1);
    expect(m.listLaboratorySessions).toHaveBeenCalledTimes(3);
  });

  it("U2 retries only failed immutable details", async () => {
    m.getLaboratoryRun.mockRejectedValueOnce(new NetworkError());
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    const error = await screen.findByRole("alert");
    await user.click(within(error).getByRole("button", { name: "Reintentar" }));
    await screen.findByRole("heading", { name: "Resultado guardado" });
    expect(m.getLaboratoryRun).toHaveBeenCalledTimes(2);
    expect(m.listLaboratorySessions).toHaveBeenCalledTimes(1);
  });
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

  it("shows fixed rules without redundant editing guidance", async () => {
    renderAt(`/laboratorios/${ID}`);
    const rules = await screen.findByRole("region", { name: "Reglas del laboratorio" });
    expect(within(rules).getByRole("heading", { name: "Reglas fijadas" })).toBeInTheDocument();
    expect(within(rules).queryByText(/Las reglas no se editan:/)).not.toBeInTheDocument();
  });

  it("keeps the execute action without redundant save guidance", async () => {
    renderAt(`/laboratorios/${ID}`);
    const execute = await screen.findByRole("button", { name: "Ejecutar laboratorio" });
    await waitFor(() => expect(execute).toBeEnabled());
    expect(screen.queryByText("Se guardará una corrida nueva con estas reglas.")).not.toBeInTheDocument();
    expect(m.createLaboratoryRun).not.toHaveBeenCalled();
  });

  it("shows saved runs without redundant selection guidance", async () => {
    renderAt(`/laboratorios/${ID}`);
    expect(await screen.findByRole("button", { name: "Ver resultado" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Corridas guardadas" })).toBeInTheDocument();
    expect(screen.queryByText("Seleccioná una corrida para abrir su resultado.")).not.toBeInTheDocument();
  });

  it("preserves source-loading errors and disables execution", async () => {
    vi.mocked(getReferenceLabs).mockRejectedValue(new NetworkError());
    renderAt(`/laboratorios/${ID}`);
    expect(await screen.findByText("No se pudo leer la fuente congelada: No se pudo contactar al servidor local.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ejecutar laboratorio" })).toBeDisabled();
    expect(m.createLaboratoryRun).not.toHaveBeenCalled();
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

  it("removes incomplete-session guidance without changing financial summaries", async () => {
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    const result = await screen.findByRole("region", { name: "Resultado guardado" });
    expect(within(result).getByText("Ganancia / pérdida").parentElement).toHaveTextContent("+RD$100");
    expect(within(result).getByText("Incompletas").parentElement).toHaveTextContent("1");
    expect(within(result).getByText("Media neta de cerradas").parentElement).toHaveTextContent("+RD$50,00");
    expect(within(result).queryByText("Las sesiones incompletas aportan a los totales de dinero, pero no al promedio neto de sesiones cerradas.")).not.toBeInTheDocument();
  });

  it("removes per-bet limitation guidance without inventing detail controls", async () => {
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    const result = await screen.findByRole("region", { name: "Resultado guardado" });
    expect(within(result).getByRole("region", { name: "Resúmenes de sesiones" })).toBeInTheDocument();
    expect(within(result).queryByRole("button", { name: /apuestas/i })).not.toBeInTheDocument();
    expect(within(result).queryByText("Este contrato guarda resúmenes de sesión; no incluye el detalle de cada apuesta.")).not.toBeInTheDocument();
  });

  it("removes page-only guidance while preserving session pagination", async () => {
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    await user.click(await screen.findByRole("button", { name: "Ver resultado" }));
    const result = await screen.findByRole("region", { name: "Resultado guardado" });
    expect(within(result).getByRole("heading", { name: "Sesiones 1–1 de 1" })).toBeInTheDocument();
    const pagination = within(result).getByRole("navigation", { name: "Paginación de sesiones" });
    expect(within(pagination).getByRole("button", { name: "Anterior" })).toBeDisabled();
    expect(within(pagination).getByRole("button", { name: "Siguiente" })).toBeDisabled();
    expect(m.listLaboratorySessions.mock.calls[0].slice(0, 3)).toEqual([ID, "run-1", { offset: 0, limit: 50 }]);
    expect(within(result).queryByText("Se consulta solo esta página de resúmenes.")).not.toBeInTheDocument();
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

  it("blocks a second POST when the actual request receives unreadable HTTP 201", async () => {
    const response = new Response("{}", { status: 201 });
    vi.spyOn(response, "json").mockRejectedValueOnce(new SyntaxError("cannot decode body"));
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderAt(`/laboratorios/${ID}`);
    const execute = await screen.findByRole("button", { name: "Ejecutar laboratorio" });
    await waitFor(() => expect(execute).toBeEnabled());

    await user.click(execute);

    expect(await screen.findByText(/No hay confirmación de si el servidor guardó esta ejecución/)).toBeInTheDocument();
    expect(execute).toBeDisabled();
    await user.click(execute);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST" });
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
