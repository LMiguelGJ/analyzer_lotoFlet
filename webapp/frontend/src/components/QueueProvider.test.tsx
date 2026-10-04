import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient, NetworkError } from "../api/client";
import type { QueueStatus } from "../api/types";
import { Shell } from "./Shell";
import { QueueProvider } from "./QueueProvider";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getQueue: vi.fn() } };
});
function snapshot(offset: number, pendingTotal: number, heldTotal: number, pending: string[], held: string[]): QueueStatus {
  return { active_id: null, pending: { offset, limit: 20, total: pendingTotal, count: pending.length, items: pending }, held: { offset, limit: 20, total: heldTotal, count: held.length, items: held }, last_failure: null };
}
beforeEach(() => vi.mocked(apiClient.getQueue).mockReset());

describe("shared bounded queue poll", () => {
  it("requests one page for Shell and drawer and pages both independent totals with one request", async () => {
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(snapshot(0, 22, 2, ["pending-first"], ["held-first"]))
      .mockResolvedValueOnce(snapshot(20, 22, 2, ["pending-last"], []));
    const user = userEvent.setup();
    render(<MemoryRouter><QueueProvider><Shell title="Prueba">Contenido</Shell></QueueProvider></MemoryRouter>);
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "Cola" }));
    expect(await screen.findByRole("link", { name: "Inspeccionar pending-first" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Detenido" })).toHaveTextContent("2");
    expect(apiClient.getQueue).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Siguiente cola" }));
    expect(await screen.findByRole("link", { name: "Inspeccionar pending-last" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Inspeccionar held-first" })).not.toBeInTheDocument();
    expect(apiClient.getQueue).toHaveBeenNthCalledWith(2, 20, 20);
    expect(within(screen.getByRole("region", { name: "Detenido" })).getByText(/No hay elementos en esta página/)).toBeInTheDocument();
  });

  it("discards an old page response and reconciles an out-of-range page after queue shrink", async () => {
    let resolveOld!: (value: QueueStatus) => void;
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(snapshot(0, 25, 0, ["first"], []))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
      .mockResolvedValueOnce(snapshot(20, 1, 0, [], []))
      .mockResolvedValueOnce(snapshot(0, 1, 0, ["survivor"], []));
    const user = userEvent.setup();
    render(<MemoryRouter><QueueProvider><Shell title="Prueba">Contenido</Shell></QueueProvider></MemoryRouter>);
    await user.click(screen.getByRole("button", { name: "Cola" }));
    await screen.findByRole("link", { name: "Inspeccionar first" });
    await user.click(screen.getByRole("button", { name: "Siguiente cola" }));
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(2));
    await user.click(screen.getByRole("button", { name: "Reintentar cola" }));
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(4));
    resolveOld(snapshot(20, 25, 0, ["stale"], []));
    expect(await screen.findByRole("link", { name: "Inspeccionar survivor" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Inspeccionar stale" })).not.toBeInTheDocument();
    expect(screen.getByText("Página 1")).toBeInTheDocument();
  });

  it("never shows the failure lane together with the pending lane while a retry is in flight", async () => {
    let resolveRetry!: (value: QueueStatus) => void;
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce(snapshot(0, 1, 0, ["first"], []))
      .mockRejectedValueOnce(new NetworkError())
      .mockImplementationOnce(() => new Promise((resolve) => { resolveRetry = resolve; }));
    const user = userEvent.setup();
    render(<MemoryRouter><QueueProvider><Shell title="Prueba">Contenido</Shell></QueueProvider></MemoryRouter>);
    await user.click(screen.getByRole("button", { name: "Cola" }));
    await screen.findByRole("link", { name: "Inspeccionar first" });
    await user.click(screen.getByRole("button", { name: "Reintentar cola" }));
    const dialog = screen.getByRole("dialog");
    expect(await within(dialog).findByText(/Sin conexión con el servidor/)).toBeInTheDocument();
    expect(dialog.textContent).not.toMatch(/Actualizando…/);
    await user.click(screen.getByRole("button", { name: "Reintentar cola" }));
    await waitFor(() => expect(apiClient.getQueue).toHaveBeenCalledTimes(3));
    expect(dialog.textContent).not.toMatch(/Sin conexión con el servidor/);
    resolveRetry(snapshot(0, 1, 0, ["first"], []));
    await screen.findByRole("link", { name: "Inspeccionar first" });
  });
});
