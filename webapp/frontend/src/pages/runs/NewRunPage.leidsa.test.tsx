import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { getHistory } from "../../api/history";
import { createRun, getRun, getRunOptions } from "../../api/runs";
import type { RunOptions } from "../../api/types";
import { NewRunPage } from "./NewRunPage";
import { optionsFixture, runFixture } from "./test-fixtures";

vi.mock("../../api/runs", () => ({ createRun: vi.fn(), getRun: vi.fn(), getRunOptions: vi.fn() }));
vi.mock("../../api/history", () => ({ getHistory: vi.fn() }));
const reason = "No disponible para esta lista";
const leidsaOptions: RunOptions = {
  ...optionsFixture,
  list: { id: "leidsa_quiniela", name: "Quiniela Leidsa", positions: 3 },
  systems: [
    { id: "cold", label: "Fríos", available: true }, { id: "freq_recent", label: "Frecuencia reciente", available: true },
    { id: "transition", label: "Transición", available: false, reason },
  ],
  systems_available: ["cold", "freq_recent"],
  defaults: {
    ...optionsFixture.defaults,
    rules: { positions: 3, prizes: [60, 8, 4], minimum_stake: 1 },
    strategy: { kind: "mix", components: [{ system: "cold", percent: 60 }, { system: "freq_recent", percent: 40 }], coverage: 10 },
  },
  limits: { ...optionsFixture.limits, positions: { min: 1, max: 3 } },
  history: { ...optionsFixture.history, draws: 4239, first_label: "2023-01-04", last_label: "2026-11-16" },
};
function mount() { return render(<MemoryRouter initialEntries={["/corridas/nueva"]}><Routes><Route path="/corridas/nueva" element={<NewRunPage />} /><Route path="/corridas/:id" element={<p>Resultado</p>} /></Routes></MemoryRouter>); }
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getRunOptions).mockResolvedValue(leidsaOptions);
  vi.mocked(getHistory).mockRejectedValue(new ApiError(409, "Con Leidsa no hay historial importado."));
  vi.mocked(getRun).mockResolvedValue(runFixture);
});

describe("new run under Leidsa", () => {
  it("loads even though /history answers 409, caps positions at the list and shows three prizes", async () => {
    mount();
    const positions = await screen.findByLabelText("Posiciones (1–3)");
    expect(positions).toHaveValue("3");
    expect(within(positions).getAllByRole("option")).toHaveLength(3);
    expect(screen.getAllByLabelText(/Premio posición/).map((input) => (input as HTMLInputElement).value)).toEqual(["60", "8", "4"]);
    expect(screen.getByText("Lista:").closest("p")).toHaveTextContent("Quiniela Leidsa");
    expect(screen.queryByText(/SHA-256/)).not.toBeInTheDocument();
  });
  it("disables unavailable systems with their reason and posts three prizes with the list snapshot", async () => {
    const user = userEvent.setup(); vi.mocked(createRun).mockResolvedValue({ ...runFixture, id: "new" });
    mount();
    const select = await screen.findByLabelText("Sistema 1");
    const unavailable = within(select).getByRole("option", { name: `Transición — ${reason}` });
    expect(unavailable).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Correr" }));
    await waitFor(() => expect(createRun).toHaveBeenCalledTimes(1));
    expect(createRun).toHaveBeenCalledWith(expect.objectContaining({ rules: { positions: 3, prizes: [60, 8, 4], minimum_stake: 1 }, history_sha256: leidsaOptions.history.sha256 }));
  });
  it("does not offer an unavailable system as the next mix component", async () => {
    const user = userEvent.setup(); mount();
    await screen.findByLabelText("Sistema 1");
    expect(screen.getByRole("button", { name: "Agregar sistema" })).toBeDisabled();
    await user.click(screen.getAllByRole("button", { name: "Quitar sistema" })[1]);
    expect(screen.getByRole("button", { name: "Agregar sistema" })).toBeEnabled();
  });
});
