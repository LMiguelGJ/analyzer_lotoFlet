import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, MemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError, NetworkError } from "../api/client";
import type { QueueStatus } from "../api/types";
import { App } from "../App";
import { Shell } from "./Shell";
import { QueueProvider } from "./QueueProvider";

vi.mock("../pages/experiments", () => ({ ExperimentsPage: () => <p>Lista de prueba</p> }));
vi.mock("../pages/experiments/DetailPage", () => ({ DetailPage: () => <p>Detalle de prueba</p> }));
vi.mock("../pages/settings", () => ({ SettingsPage: () => <p>Ajustes de prueba</p> }));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getQueue: vi.fn(), getExperiment: vi.fn(), startHeld: vi.fn(), cancelJob: vi.fn() } };
});

function queue(pending: string[] = [], held: string[] = [], active_id: string | null = null): QueueStatus {
  return { active_id, pending: { total: pending.length, offset: 0, limit: 20, count: pending.length, items: pending }, held: { total: held.length, offset: 0, limit: 20, count: held.length, items: held }, last_failure: null };
}
function page(offset: number, pending: string[] = [], held: string[] = []): QueueStatus {
  return { active_id: null, pending: { total: 21, offset, limit: 20, count: pending.length, items: pending }, held: { total: 21, offset, limit: 20, count: held.length, items: held }, last_failure: null };
}
function detail(status: "held" | "pending" | "running" | "cancelled" | "completed") {
  return { status } as Awaited<ReturnType<typeof apiClient.getExperiment>>;
}
function setup() {
  const user = userEvent.setup();
  const view = render(<MemoryRouter><QueueProvider><Shell title="Prueba"><p>Contenido</p></Shell></QueueProvider></MemoryRouter>);
  return { user, ...view };
}
async function open(user: ReturnType<typeof userEvent.setup>) {
  const trigger = screen.getByRole("button", { name: "Cola" });
  await user.click(trigger);
  return screen.getByRole("dialog", { name: "Cola de experimentos" });
}
beforeEach(() => {
  vi.mocked(apiClient.getQueue).mockReset().mockResolvedValue(queue());
  vi.mocked(apiClient.getExperiment).mockReset().mockResolvedValue(detail("pending"));
  vi.mocked(apiClient.startHeld).mockReset().mockResolvedValue({ id: "held-1", status: "queued" });
  vi.mocked(apiClient.cancelJob).mockReset().mockResolvedValue({ id: "run-1", status: "cancellation_requested" });
});

describe("LW15 queue drawer", () => {
  it.each(["ack", "uncertain"])("retains %s cancellation across actual list → detail → settings → list route unmounts with one queue poll", async (outcome) => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue(["pending-1"]));
    if (outcome === "uncertain") vi.mocked(apiClient.cancelJob).mockRejectedValue(new NetworkError());
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail("pending"));
    const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: ["/experimentos"] });
    const user = userEvent.setup();
    render(<RouterProvider router={router} />);
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Cancelar pending-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(2));
    await user.click(within(dialog).getByRole("link", { name: "Inspeccionar pending-1" }));
    expect(await screen.findByText("Detalle de prueba")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Administración" }));
    expect(await screen.findByText("Ajustes de prueba")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Simulaciones" }));
    expect(await screen.findByText("Lista de prueba")).toBeInTheDocument();
    const reopened = await open(user);
    expect(within(reopened).getByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
    expect(apiClient.cancelJob).toHaveBeenCalledTimes(1);
    expect(apiClient.getQueue).toHaveBeenCalledTimes(2);
  });

  it("retains an in-flight cancellation across route unmount, without sending again on return", async () => {
    let resolveCancel!: (value: Awaited<ReturnType<typeof apiClient.cancelJob>>) => void;
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue(["pending-1"]));
    vi.mocked(apiClient.cancelJob).mockImplementation(() => new Promise((resolve) => { resolveCancel = resolve; }));
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail("pending"));
    const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: ["/experimentos"] });
    const user = userEvent.setup();
    render(<RouterProvider router={router} />);
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Cancelar pending-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    await user.click(within(dialog).getByRole("link", { name: "Inspeccionar pending-1" }));
    expect(await screen.findByText("Detalle de prueba")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Simulaciones" }));
    const reopened = await open(user);
    expect(within(reopened).getByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
    resolveCancel({ id: "pending-1", status: "cancellation_requested" });
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(2));
    expect(within(reopened).getByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
    expect(apiClient.cancelJob).toHaveBeenCalledTimes(1);
  });

  it.each(["ack", "uncertain"])("requires fresh detail and an explicit confirmed resend for %s pending cancellation", async (outcome) => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue(["pending-1"]));
    if (outcome === "uncertain") vi.mocked(apiClient.cancelJob).mockRejectedValueOnce(new NetworkError()).mockResolvedValue({ id: "pending-1", status: "cancellation_requested" });
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail("pending"));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Cancelar pending-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    const check = await within(dialog).findByRole("button", { name: "Comprobar estado pending-1" });
    expect(within(dialog).queryByRole("button", { name: "Reenviar cancelación pending-1" })).not.toBeInTheDocument();
    await user.click(check);
    const resend = await within(dialog).findByRole("button", { name: "Reenviar cancelación pending-1" });
    expect(apiClient.cancelJob).toHaveBeenCalledTimes(1);
    await user.click(resend);
    expect(apiClient.cancelJob).toHaveBeenCalledTimes(1);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cancelar" }));
    expect(apiClient.cancelJob).toHaveBeenCalledTimes(1);
    await user.click(resend);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar reenvío" }));
    await waitFor(() => expect(apiClient.cancelJob).toHaveBeenCalledTimes(2));
  });

  it("keeps a 409 rejection locked against a stale row until detail reconciliation", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue(["pending-1"]));
    vi.mocked(apiClient.cancelJob).mockRejectedValue(new ApiError(409, "private backend message"));
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail("pending"));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Cancelar pending-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/ya no puede cancelarse/);
    expect(within(dialog).getByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
    expect(within(dialog).queryByRole("button", { name: "Reenviar cancelación pending-1" })).not.toBeInTheDocument();
    expect(apiClient.cancelJob).toHaveBeenCalledTimes(1);
  });

  it("keeps an action locked after a failed explicit recheck, without enabling resend", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue(["pending-1"]));
    vi.mocked(apiClient.cancelJob).mockRejectedValue(new NetworkError());
    vi.mocked(apiClient.getExperiment).mockRejectedValue(new NetworkError());
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Cancelar pending-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    const check = await within(dialog).findByRole("button", { name: "Comprobar estado pending-1" });
    await user.click(check);
    expect(await within(dialog).findByText(/No se pudo comprobar el estado/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
    expect(within(dialog).queryByRole("button", { name: "Reenviar cancelación pending-1" })).not.toBeInTheDocument();
    expect(apiClient.cancelJob).toHaveBeenCalledTimes(1);
  });

  it("clears a terminal action only after the originating queue page catches up", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(queue(["pending-1"])).mockResolvedValueOnce(queue(["pending-1"])).mockResolvedValue(queue());
    vi.mocked(apiClient.cancelJob).mockRejectedValue(new NetworkError());
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail("cancelled"));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Cancelar pending-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    await waitFor(() => expect(within(dialog).getByText(/Estado final confirmado/)).toBeInTheDocument());
    expect(within(dialog).getByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
    await user.click(within(dialog).getByRole("button", { name: "Reintentar cola" }));
    await waitFor(() => expect(within(dialog).queryByRole("button", { name: "Cancelar pending-1" })).not.toBeInTheDocument());
    expect(apiClient.cancelJob).toHaveBeenCalledTimes(1);
  });

  it("does not offer a start resend when detail says pending despite a stale held row", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue([], ["held-1"]));
    vi.mocked(apiClient.startHeld).mockRejectedValue(new NetworkError());
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail("pending"));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Iniciar held-1" }));
    await user.click(await within(dialog).findByRole("button", { name: "Comprobar estado held-1" }));
    expect(within(dialog).queryByRole("button", { name: "Reintentar inicio held-1" })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Iniciar held-1" })).toBeDisabled();
    expect(apiClient.startHeld).toHaveBeenCalledTimes(1);
  });

  it("retries uncertain start only after fresh held detail and confirmation", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue([], ["held-1"]));
    vi.mocked(apiClient.startHeld).mockRejectedValueOnce(new NetworkError()).mockResolvedValue({ id: "held-1", status: "queued" });
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail("held"));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Iniciar held-1" }));
    const check = await within(dialog).findByRole("button", { name: "Comprobar estado held-1" });
    expect(within(dialog).queryByRole("button", { name: "Reintentar inicio held-1" })).not.toBeInTheDocument();
    await user.click(check);
    await user.click(await within(dialog).findByRole("button", { name: "Reintentar inicio held-1" }));
    expect(apiClient.startHeld).toHaveBeenCalledTimes(1);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar reintento" }));
    await waitFor(() => expect(apiClient.startHeld).toHaveBeenCalledTimes(2));
  });
  it.each(["ack", "uncertain"])("does not unlock a held request on page 0 → 20 → 0 after %s", async (outcome) => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(page(0, [], ["held-1"]))
      .mockResolvedValueOnce(page(0, [], ["held-1"]))
      .mockResolvedValueOnce(page(20, [], ["other-held"]))
      .mockResolvedValueOnce(page(0, [], ["held-1"]));
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail("held"));
    if (outcome === "uncertain") vi.mocked(apiClient.startHeld).mockRejectedValue(new NetworkError());
    const { user } = setup();
    const dialog = await open(user);
    const start = await within(dialog).findByRole("button", { name: "Iniciar held-1" });
    await user.click(start);
    await waitFor(() => expect(start).toBeDisabled());
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(2));
    await user.click(within(dialog).getByRole("button", { name: "Siguiente cola" }));
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(3));
    await user.click(within(dialog).getByRole("button", { name: "Anterior cola" }));
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(4));
    expect(await within(dialog).findByRole("button", { name: "Iniciar held-1" })).toBeDisabled();
    expect(apiClient.startHeld).toHaveBeenCalledTimes(1);
  });

  it.each(["ack", "uncertain"])("does not unlock a pending cancellation on page 0 → 20 → 0 after %s", async (outcome) => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(page(0, ["pending-1"]))
      .mockResolvedValueOnce(page(0, ["pending-1"]))
      .mockResolvedValueOnce(page(20, ["other-pending"]))
      .mockResolvedValueOnce(page(0, ["pending-1"]));
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail("pending"));
    if (outcome === "uncertain") vi.mocked(apiClient.cancelJob).mockRejectedValue(new NetworkError());
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Cancelar pending-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(2));
    await user.click(within(dialog).getByRole("button", { name: "Siguiente cola" }));
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(3));
    await user.click(within(dialog).getByRole("button", { name: "Anterior cola" }));
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(4));
    expect(await within(dialog).findByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
    expect(apiClient.cancelJob).toHaveBeenCalledTimes(1);
    expect(apiClient.getExperiment).toHaveBeenCalledWith("pending-1");
  });

  it.each(["pending", "running"] as const)("releases a start lock after authoritative %s, allowing cancellation", async (state) => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(queue([], ["held-1"]))
      .mockResolvedValueOnce(queue([], ["held-1"]))
      .mockResolvedValue(queue(["held-1"]));
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail(state));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Iniciar held-1" }));
    await waitFor(() => expect(apiClient.getExperiment).toHaveBeenCalledWith("held-1"));
    expect(within(dialog).getByRole("button", { name: "Iniciar held-1" })).toBeDisabled();
    await user.click(within(dialog).getByRole("button", { name: "Reintentar cola" }));
    const cancel = await within(dialog).findByRole("button", { name: "Cancelar held-1" });
    await waitFor(() => expect(cancel).toBeEnabled());
    expect(within(dialog).queryByRole("button", { name: "Iniciar held-1" })).not.toBeInTheDocument();
    expect(apiClient.startHeld).toHaveBeenCalledTimes(1);
  });

  it("keeps an uncertain cancellation locked while detail is unavailable, then releases on terminal state", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(queue(["pending-1"]))
      .mockResolvedValueOnce(queue(["pending-1"]))
      .mockResolvedValueOnce(queue(["pending-1"]))
      .mockResolvedValue(queue());
    vi.mocked(apiClient.cancelJob).mockRejectedValue(new NetworkError());
    vi.mocked(apiClient.getExperiment).mockRejectedValueOnce(new NetworkError()).mockResolvedValue(detail("cancelled"));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Cancelar pending-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    await waitFor(() => expect(apiClient.getExperiment).toHaveBeenCalledTimes(1));
    expect(within(dialog).getByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
    await user.click(within(dialog).getByRole("button", { name: "Reintentar cola" }));
    await waitFor(() => expect(apiClient.getExperiment).toHaveBeenCalledTimes(2));
    expect(within(dialog).getByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
    await user.click(within(dialog).getByRole("button", { name: "Reintentar cola" }));
    await waitFor(() => expect(within(dialog).queryByRole("button", { name: "Cancelar pending-1" })).not.toBeInTheDocument());
    expect(apiClient.cancelJob).toHaveBeenCalledTimes(1);
  });

  it("ignores stale detail after a start unlock and a new cancellation lock", async () => {
    let resolveOld!: (value: Awaited<ReturnType<typeof apiClient.getExperiment>>) => void;
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(queue([], ["held-1"]))
      .mockResolvedValueOnce(queue([], ["held-1"]))
      .mockImplementation(() => Promise.resolve(queue(["held-1"])));
    vi.mocked(apiClient.getExperiment).mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
      .mockResolvedValue(detail("pending"));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Iniciar held-1" }));
    await waitFor(() => expect(apiClient.getExperiment).toHaveBeenCalledTimes(1));
    await user.click(within(dialog).getByRole("button", { name: "Reintentar cola" }));
    expect(await within(dialog).findByRole("button", { name: "Cancelar held-1" })).toBeEnabled();
    await user.click(within(dialog).getByRole("button", { name: "Cancelar held-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    await waitFor(() => expect(apiClient.getExperiment).toHaveBeenCalledTimes(2));
    resolveOld(detail("completed"));
    expect(within(dialog).getByRole("button", { name: "Cancelar held-1" })).toBeDisabled();
  });

  it("retains an in-flight action across drawer close and reopen until reconciled", async () => {
    let resolveStart!: (value: Awaited<ReturnType<typeof apiClient.startHeld>>) => void;
    vi.mocked(apiClient.getQueue).mockImplementation(() => Promise.resolve(queue([], ["held-1"])));
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail("held"));
    vi.mocked(apiClient.startHeld).mockImplementation(() => new Promise((resolve) => { resolveStart = resolve; }));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Iniciar held-1" }));
    await user.click(within(dialog).getByRole("button", { name: "Cerrar cola" }));
    resolveStart({ id: "held-1", status: "queued" });
    const reopened = await open(user);
    await waitFor(() => expect(apiClient.getExperiment).toHaveBeenCalledWith("held-1"));
    expect(within(reopened).getByRole("button", { name: "Iniciar held-1" })).toBeDisabled();
    expect(apiClient.startHeld).toHaveBeenCalledTimes(1);
  });

  it("deduplicates detail reads across shared queue refreshes while an inspection is in flight", async () => {
    let resolveDetail!: (value: Awaited<ReturnType<typeof apiClient.getExperiment>>) => void;
    vi.mocked(apiClient.getQueue).mockImplementation(() => Promise.resolve(queue(["pending-1"])));
    vi.mocked(apiClient.getExperiment).mockImplementation(() => new Promise((resolve) => { resolveDetail = resolve; }));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Cancelar pending-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    await waitFor(() => expect(apiClient.getExperiment).toHaveBeenCalledTimes(1));
    await user.click(within(dialog).getByRole("button", { name: "Reintentar cola" }));
    await user.click(within(dialog).getByRole("button", { name: "Reintentar cola" }));
    expect(apiClient.getExperiment).toHaveBeenCalledTimes(1);
    resolveDetail(detail("cancelled"));
    await waitFor(() => expect(within(dialog).getByText(/Estado final confirmado/)).toBeInTheDocument());
    expect(within(dialog).getByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
  });

  it("uses plain queue states and keeps protocol details closed until requested", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue(["pending-1"], ["held-1"], "run-1"));
    const { user } = setup();
    const dialog = await open(user);
    expect(within(dialog).getByRole("heading", { name: "En curso" })).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: /Esperando/ })).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: /Detenido/ })).toBeInTheDocument();
    const technical = within(dialog).getByText("Detalles técnicos").closest("details")!;
    expect(technical).not.toHaveAttribute("open");
    const protocol = within(technical).getByText(/reintentos|páginas|reinicio/i);
    expect(protocol).not.toBeVisible();
    expect(within(dialog).queryByText(/Pendientes y retenidos se consultan por páginas independientes/)).not.toBeInTheDocument();
    await user.click(within(technical).getByText("Detalles técnicos"));
    expect(technical).toHaveAttribute("open");
    expect(protocol).toBeVisible();
  });

  it("opens on demand, traps Tab, Escape closes and returns focus, with no closed portal", async () => {
    const { user } = setup();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    const dialog = await open(user);
    expect(dialog).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cola" })).toHaveFocus();
  });

  it("nested cancel confirmation absorbs Escape, then cancellation request does not claim terminal status", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue([], [], "run-1"));
    const { user } = setup();
    const dialog = await open(user);
    await screen.findByRole("link", { name: /run-1/ });
    const cancel = within(dialog).getByRole("button", { name: /Cancelar run-1/ });
    await user.click(cancel);
    expect(screen.getByRole("alertdialog")).toHaveAccessibleName("¿Cancelar el experimento run-1?");
    expect(screen.getByRole("alertdialog")).toHaveTextContent(/resultados ya terminados de run-1/);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(dialog).toBeInTheDocument();
    expect(cancel).toHaveFocus();
    await user.click(cancel);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    expect(apiClient.cancelJob).toHaveBeenCalledWith("run-1");
    expect(await screen.findByText(/Solicitud de cancelación enviada/)).toBeInTheDocument();
    expect(screen.queryByText(/Cancelado/)).not.toBeInTheDocument();
  });

  it("restores the held-row Cancelar trigger after nested Escape under native inert focus rules", async () => {
    // jsdom does not enforce inert: model the browser's blur when a focused
    // descendant becomes inert and its refusal to focus inert descendants.
    const setAttribute = HTMLElement.prototype.setAttribute;
    const focus = HTMLElement.prototype.focus;
    HTMLElement.prototype.setAttribute = function (name, value) {
      setAttribute.call(this, name, value);
      if (name === "inert" && this.contains(document.activeElement)) {
        (document.activeElement as HTMLElement).blur();
      }
    };
    HTMLElement.prototype.focus = function (options) {
      if (this.closest("[inert]")) return;
      focus.call(this, options);
    };
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue([], ["held-1"]));
    const appRoot = document.createElement("div");
    appRoot.id = "root";
    document.body.appendChild(appRoot);
    const user = userEvent.setup();
    const view = render(<MemoryRouter><QueueProvider><Shell title="Prueba"><p>Contenido</p></Shell></QueueProvider></MemoryRouter>, { container: appRoot });
    try {
      const drawer = await open(user);
      const cancel = await within(drawer).findByRole("button", { name: "Cancelar held-1" });
      await user.click(cancel);
      const confirmation = screen.getByRole("alertdialog");
      expect(confirmation.contains(document.activeElement)).toBe(true);
      view.rerender(<MemoryRouter><QueueProvider><Shell title="Prueba"><p>Contenido</p></Shell></QueueProvider></MemoryRouter>);
      expect(confirmation.contains(document.activeElement)).toBe(true);
      await user.keyboard("{Escape}");
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
      expect(drawer).toBeInTheDocument();
      expect(appRoot).toHaveAttribute("inert");
      expect(cancel.isConnected).toBe(true);
      expect(cancel).toHaveFocus();
      await user.keyboard("{Escape}");
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Cola" })).toHaveFocus();
    } finally {
      view.unmount();
      appRoot.remove();
      HTMLElement.prototype.setAttribute = setAttribute;
      HTMLElement.prototype.focus = focus;
    }
  });

  it("keeps status focused when a confirmed held cancellation removes its trigger", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(queue([], ["held-1"])).mockResolvedValue(queue());
    const { user } = setup();
    const drawer = await open(user);
    const cancel = await within(drawer).findByRole("button", { name: "Cancelar held-1" });
    await user.click(cancel);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    await waitFor(() => expect(cancel.isConnected).toBe(false));
    expect(within(drawer).getByRole("status", { name: "" })).toHaveFocus();
    expect(apiClient.cancelJob).toHaveBeenCalledOnce();
  });

  it("retains focused success status after its four-second expiry, then clears it when focus moves", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(queue([], ["held-1"])).mockResolvedValue(queue());
    const { user } = setup();
    const drawer = await open(user);
    const cancel = await within(drawer).findByRole("button", { name: "Cancelar held-1" });
    await user.click(cancel);
    vi.useFakeTimers();
    try {
      await act(async () => {
        fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
      });
      expect(cancel.isConnected).toBe(false);
      const status = within(drawer).getByRole("status");
      expect(status).toHaveFocus();
      act(() => vi.advanceTimersByTime(4100));
      expect(status.isConnected).toBe(true);
      expect(status).toHaveFocus();
      expect(document.activeElement).not.toBe(document.body);
      const retry = within(drawer).getByRole("button", { name: "Reintentar cola" });
      act(() => retry.focus());
      expect(within(drawer).queryByRole("status")).not.toBeInTheDocument();
      expect(retry).toHaveFocus();
    } finally {
      vi.useRealTimers();
    }
  });

  it("expires an unfocused success status without taking focus from the next control", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(queue([], ["held-1"])).mockResolvedValue(queue());
    const { user } = setup();
    const drawer = await open(user);
    await user.click(await within(drawer).findByRole("button", { name: "Cancelar held-1" }));
    vi.useFakeTimers();
    try {
      await act(async () => {
        fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
      });
      const status = within(drawer).getByRole("status");
      expect(status).toHaveFocus();
      const retry = within(drawer).getByRole("button", { name: "Reintentar cola" });
      act(() => retry.focus());
      expect(status.isConnected).toBe(true);
      act(() => vi.advanceTimersByTime(4100));
      expect(status.isConnected).toBe(false);
      expect(retry).toHaveFocus();
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps mobile navigation closed when Escape dismisses only the drawer", async () => {
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Abrir navegación" }));
    await user.click(screen.getByRole("button", { name: "Cola" }));
    expect(screen.getByRole("button", { name: "Abrir navegación" })).toHaveAttribute("aria-expanded", "false");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cola" })).toHaveFocus();
  });

  it("offers explicit start only on held jobs, never resume on the interrupted active job", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue(["pending-1"], ["held-1"]));
    const { user } = setup();
    await open(user);
    expect(await screen.findByRole("button", { name: /Iniciar held-1/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Iniciar pending-1/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Iniciar held-1/ }));
    expect(apiClient.startHeld).toHaveBeenCalledWith("held-1");
    expect(screen.queryByText(/reanudar/i)).not.toBeInTheDocument();
  });

  it.each([404, 409, 507])("keeps start error %i inline, distinguishing disk quota", async (status) => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue([], ["held-1"]));
    vi.mocked(apiClient.startHeld).mockRejectedValue(new ApiError(status, "private backend message"));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: /Iniciar held-1/ }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(status === 507 ? /espacio|cuota/i : status === 404 ? /ya no existe/ : /no puede iniciarse/);
    expect(dialog).not.toHaveTextContent("private backend message");
  });

  it.each([404, 409])("keeps cancellation error %i beside its active row", async (status) => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue([], [], "run-1"));
    vi.mocked(apiClient.cancelJob).mockRejectedValue(new ApiError(status, "private backend message"));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: /Cancelar run-1/ }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(status === 404 ? /ya no existe/ : /ya no puede cancelarse/);
    expect(dialog).not.toHaveTextContent("private backend message");
  });

  it("retains last known state on disconnection and does not claim a stopped calculation", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(queue([], [], "run-1")).mockRejectedValue(new NetworkError());
    const { user } = setup();
    await open(user);
    await screen.findByRole("link", { name: /run-1/ });
    await user.click(screen.getByRole("button", { name: "Reintentar cola" }));
    expect(await screen.findByText(/Sin conexión con el servidor/)).toBeInTheDocument();
    expect(screen.getByText(/El cálculo puede continuar en el servidor; comprobá el estado desde la cola/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /run-1/ })).toBeInTheDocument();
    // Failure and pending lanes never coexist.
    expect(screen.getByRole("dialog").textContent).not.toMatch(/Actualizando…/);
    expect(screen.getByRole("dialog").textContent).not.toMatch(/se detuvo|Esto no detiene/i);
  });

  it("names the uncertain lane and the concrete check, with one primary action per row", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue(["pending-1"], ["held-1"]));
    vi.mocked(apiClient.cancelJob).mockRejectedValue(new NetworkError());
    const { user } = setup();
    const dialog = await open(user);
    const heldRow = (await within(dialog).findByRole("link", { name: "Inspeccionar held-1" })).closest("li")!;
    const pendingRow = within(dialog).getByRole("link", { name: "Inspeccionar pending-1" }).closest("li")!;
    // Idle rows: exactly one primary; held keeps Cancelar as the legal secondary.
    expect(heldRow.querySelectorAll(".btn-primary")).toHaveLength(1);
    expect(within(heldRow as HTMLElement).getByRole("button", { name: "Iniciar held-1" })).toHaveClass("btn-primary");
    expect(within(heldRow as HTMLElement).getByRole("button", { name: "Cancelar held-1" })).toHaveClass("btn-secondary");
    expect(pendingRow.querySelectorAll(".btn-primary")).toHaveLength(1);
    expect(within(pendingRow as HTMLElement).getByRole("button", { name: "Cancelar pending-1" })).toHaveClass("btn-primary");
    await user.click(within(pendingRow as HTMLElement).getByRole("button", { name: "Cancelar pending-1" }));
    // Long consequences live in the confirmation, not in the row.
    const confirmation = screen.getByRole("alertdialog");
    expect(confirmation).toHaveTextContent(/resultados ya terminados/);
    expect(pendingRow).not.toHaveTextContent(/resultados ya terminados/);
    await user.click(within(confirmation).getByRole("button", { name: "Confirmar cancelación" }));
    await waitFor(() => expect(pendingRow).toHaveTextContent(/La solicitud puede haber llegado; comprobá el estado desde la cola antes de reintentar/));
    expect(pendingRow).toHaveAttribute("data-lane", "uncertain");
    expect(pendingRow).not.toHaveTextContent(/Actualizando…|Sin conexión/);
    expect(pendingRow.querySelectorAll(".btn-primary")).toHaveLength(1);
    expect(within(pendingRow as HTMLElement).getByRole("button", { name: "Comprobar estado pending-1" })).toHaveClass("btn-primary");
    expect(within(pendingRow as HTMLElement).getByRole("button", { name: "Cancelar pending-1" })).toBeDisabled();
  });

  it("shows the pending lane while a request is in flight and never mixes it with a failure", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValue(queue([], [], "run-1"));
    vi.mocked(apiClient.cancelJob).mockImplementation(() => new Promise(() => {}));
    const { user } = setup();
    const dialog = await open(user);
    await user.click(await within(dialog).findByRole("button", { name: "Cancelar run-1" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirmar cancelación" }));
    const row = within(dialog).getByRole("link", { name: "Inspeccionar run-1" }).closest("li")!;
    expect(row).toHaveAttribute("data-lane", "pending");
    expect(row).toHaveTextContent("Actualizando…");
    expect(row).not.toHaveTextContent(/Sin conexión|puede haber llegado/);
    expect(row.querySelectorAll(".btn-primary")).toHaveLength(0);
  });

  it("does not describe an unpersisted last failure as a durable failed status", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValue({ ...queue(), last_failure: { experiment_id: "run-1", persisted: false, reason: "OSError", persistence_error: "OSError" } });
    const { user } = setup();
    await open(user);
    expect(await screen.findByText(/no se pudo confirmar en el almacenamiento/)).toBeInTheDocument();
    expect(screen.getByRole("dialog")).not.toHaveTextContent("OSError");
  });
});
