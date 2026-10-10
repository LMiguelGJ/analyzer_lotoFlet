import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ListPage } from "./ListPage";
import { optionsFixture, runFixture } from "./test-fixtures";
import type { Page, RunReport } from "../../api/types";
import { deleteRun, getRunOptions, listRuns } from "../../api/runs";

vi.mock("../../api/runs", () => ({ listRuns: vi.fn(), deleteRun: vi.fn(), getRunOptions: vi.fn() }));
const listMock = vi.mocked(listRuns), deleteMock = vi.mocked(deleteRun), optionsMock = vi.mocked(getRunOptions);
const page = (items: RunReport[], total = items.length, offset = 0): Page<RunReport> => ({ items, total, offset, limit: 20 });
function mount() { return render(<MemoryRouter initialEntries={["/corridas"]}><Routes><Route path="/corridas" element={<ListPage />} /><Route path="*" element={<p>Destino</p>} /></Routes></MemoryRouter>); }
beforeEach(() => { vi.clearAllMocks(); optionsMock.mockResolvedValue(optionsFixture); });

describe("runs list", () => {
  it("teaches the empty state and offers a new run", async () => { listMock.mockResolvedValue(page([])); mount(); expect(await screen.findByText("Todavía no hay corridas")).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Nueva corrida" })).toBeInTheDocument(); });
  it("announces loading and offers retry after an error", async () => { listMock.mockRejectedValueOnce(new Error("offline")).mockResolvedValue(page([])); mount(); expect(screen.getByRole("status")).toHaveTextContent("Cargando corridas"); await userEvent.click(await screen.findByRole("button", { name: "Reintentar" })); expect(await screen.findByText("Todavía no hay corridas")).toBeInTheDocument(); });
  it("pages with 20 records and aborts stale reads on unmount", async () => { listMock.mockResolvedValue(page([runFixture], 21)); const { unmount } = mount(); expect(await screen.findByRole("link", { name: "Abrir" })).toBeInTheDocument(); await userEvent.click(screen.getByRole("button", { name: "Siguiente" })); await waitFor(() => expect(listMock).toHaveBeenLastCalledWith({ offset: 20, limit: 20 }, expect.objectContaining({ signal: expect.any(AbortSignal) }))); unmount(); });
  it("asks before deletion, supports cancel, and reports delete failure", async () => { listMock.mockResolvedValue(page([runFixture])); deleteMock.mockRejectedValue(new Error("offline")); mount(); await screen.findByRole("link", { name: "Abrir" }); await userEvent.click(screen.getByRole("button", { name: "Borrar" })); expect(deleteMock).not.toHaveBeenCalled(); const dialog = screen.getByRole("alertdialog", { name: "Borrar esta corrida" }); await userEvent.click(within(dialog).getByRole("button", { name: "Cancelar" })); expect(deleteMock).not.toHaveBeenCalled(); await userEvent.click(screen.getByRole("button", { name: "Borrar" })); await userEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Borrar" })); expect(await screen.findByText(/No se pudo contactar al servidor local/)).toBeInTheDocument(); });
  it("navigates to page two, deletes its only row, then reloads and shows page one", async () => {
    const firstPage = Array.from({ length: 20 }, (_, index) => ({ ...runFixture, id: `page-one-${index}` }));
    listMock.mockResolvedValueOnce(page(firstPage, 21, 0)).mockResolvedValueOnce(page([runFixture], 21, 20)).mockResolvedValueOnce(page(firstPage, 20, 0));
    deleteMock.mockResolvedValue();
    mount();
    await screen.findAllByRole("link", { name: "Abrir" });
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(listMock.mock.calls.map(([params]) => params?.offset)).toEqual([0, 20]));
    const pageTwo = within(screen.getByRole("region", { name: "Lista de corridas" }));
    await userEvent.click(pageTwo.getByRole("button", { name: "Borrar" }));
    await userEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Borrar" }));
    await waitFor(() => expect(listMock.mock.calls.map(([params]) => params?.offset)).toEqual([0, 20, 0]));
    expect(await screen.findByText("20 corridas · 1–20")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
  });
  it("uses localized API catalog labels and never displays system IDs", async () => {
    const parity = { ...runFixture, id: "parity-run", config: { ...runFixture.config, strategy: { kind: "parity" as const, components: [], coverage: 7 } } };
    listMock.mockResolvedValue(page([runFixture, parity])); mount();
    expect(await screen.findByText("Transición 60 % + Fríos 40 % · 10 números")).toBeInTheDocument();
    expect(screen.getByText("Paridad · 7 números")).toBeInTheDocument();
    expect(optionsMock).toHaveBeenCalledWith(expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });
  it("uses a human fallback when the actual catalog cannot be loaded", async () => {
    optionsMock.mockRejectedValue(new Error("catalog unavailable"));
    const stale: RunReport = { ...runFixture, config: { ...runFixture.config, strategy: { kind: "mix", components: [{ system: "stale-internal-id", percent: 100 }], coverage: 4 } } };
    listMock.mockResolvedValue(page([stale])); mount();
    expect(await screen.findByText("Sistema no disponible 100 % · 4 números")).toBeInTheDocument();
    expect(screen.queryByText(/stale-internal-id/)).not.toBeInTheDocument();
  });
  it("uses signed money, detail words and the saved run links", async () => { listMock.mockResolvedValue(page([runFixture])); mount(); expect(await screen.findAllByText("−RD$10")).toHaveLength(1); expect(screen.getByText("Detalle completo")).toBeInTheDocument(); expect(screen.getByRole("link", { name: "Repetir con cambios" })).toHaveAttribute("href", "/corridas/nueva?base=run-123"); });
  it("has no axe violations in the loaded table", async () => { listMock.mockResolvedValue(page([runFixture])); const { container } = mount(); await screen.findByRole("link", { name: "Abrir" }); const { axe } = await import("jest-axe"); expect(await axe(container)).toHaveNoViolations(); });
});
