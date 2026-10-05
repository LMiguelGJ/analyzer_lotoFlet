import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
// Contract coverage: F-RESULT-023 bounded trajectory/reduction/index selection; F-RESULT-024 canonical/local v5 indexes; F-RESULT-025 exact lookup links without replay; F-RESULT-026 empty/error/unmount/malformed-index handling; F-RESULT-006 backend metrics.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../api/client";
import type { Trajectory } from "../api/types";
import { RunTrajectory } from "./RunTrajectory";
import { FinancialMetrics } from "./FinancialMetrics";

vi.mock("../api/client", () => ({ apiClient: { getTrajectory: vi.fn() } }));
const long: Trajectory = {
  result_kind: "profile", schema_version: 4, initial_capital: 10000, total: 1001,
  max_points: 500, reduction_method: "minmax-even-v1",
  minimum: { balance: 0, source_index: 700 }, maximum: { balance: 50000, source_index: 400 },
  points: [0, 400, 700, 1000].map((i) => ({ source_index: i, label: `2025-01-01 10:00`, balance: i === 700 ? 0 : i === 400 ? 50000 : 10000, replay: `replay?offset=${i}&limit=1` })),
};
const money = (n: number) => `EUR ${(n / 100).toFixed(2)}`;
const props = { id: "exp", ordinal: 0, name: "Perfil", goal: 20000, money };
beforeEach(() => { vi.mocked(apiClient.getTrajectory).mockReset().mockResolvedValue(long); });
describe("whole-run trajectories", () => {
  it("loads once, discloses reduction/extrema/baseline and selects original indexes", async () => {
    const select = vi.fn(); const user = userEvent.setup();
    render(<RunTrajectory {...props} onSelect={select} />);
    expect(await screen.findByText(/4 de 1001 sorteos/)).toBeInTheDocument();
    const technical = screen.getByText("Detalles técnicos · Perfil");
    expect(technical.closest("details")).not.toHaveAttribute("open");
    await user.click(technical);
    expect(screen.getByText(/modo minmax-even-v1/)).toBeInTheDocument();
    await user.click(screen.getByText("Consultar detalle técnico de un punto"));
    await user.click(screen.getByRole("button", { name: /Apuesta 1001/ }));
    expect(select).toHaveBeenLastCalledWith(1000);
    await user.type(screen.getByRole("spinbutton"), "601");
    await user.click(screen.getByRole("button", { name: "Ver apuesta exacta" }));
    expect(select).toHaveBeenLastCalledWith(600);
    expect(apiClient.getTrajectory).toHaveBeenCalledExactlyOnceWith("exp", 0, 500);
    expect(screen.queryByText(/gráfico incompleto/)).not.toBeInTheDocument();
    expect(screen.getByRole("img").querySelectorAll("circle")).toHaveLength(5);
  });
  it("keeps canonical v5 source indexes separate from local replay bet indexes", async () => {
    const select = vi.fn(); const user = userEvent.setup();
    vi.mocked(apiClient.getTrajectory).mockResolvedValue({ ...long, schema_version: 5, total: 2, reduction_method: "none", points: [
      { source_index: 900, bet_index: 0, label: "2025-01-01 10:00", balance: 9900, replay: "replay?offset=0&limit=1" },
      { source_index: 905, bet_index: 1, label: "2025-01-02 10:00", balance: 9800, replay: "replay?offset=1&limit=1" },
    ] });
    render(<RunTrajectory {...props} onSelect={select} />);
    expect(await screen.findByText(/2 de 2 sorteos/)).toBeInTheDocument();
    await user.click(screen.getByText("Consultar detalle técnico de un punto"));
    await user.click(screen.getByRole("button", { name: /Apuesta 2 · sorteo n.º 905/ }));
    expect(select).toHaveBeenLastCalledWith(1);
    expect(screen.getByRole("img").querySelectorAll("circle")).toHaveLength(3);
  });
  it("uses all >20 unreduced points and links exact lookup without replay downloads", async () => {
    const points = Array.from({ length: 30 }, (_, i) => ({ ...long.points[0], source_index: i }));
    vi.mocked(apiClient.getTrajectory).mockResolvedValue({ ...long, total: 30, reduction_method: "none", points });
    render(<MemoryRouter><RunTrajectory {...props} chart={false} /></MemoryRouter>);
    expect(await screen.findByRole("region", { name: "Trayectoria de Perfil" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Apuesta 30/ })).toHaveAttribute("href", "/experimentos/exp?run=0&bet=29&from=comparison");
  });
  it("handles empty data and retries failed/malformed responses", async () => {
    vi.mocked(apiClient.getTrajectory).mockRejectedValueOnce(new Error("offline"));
    const user = userEvent.setup(); render(<RunTrajectory {...props} onSelect={() => {}} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo cargar");
    vi.mocked(apiClient.getTrajectory).mockResolvedValue({ ...long, total: 0, points: [], reduction_method: "none" });
    await user.click(screen.getByRole("button", { name: /Reintentar trayectoria/ }));
    expect(await screen.findByText(/Todavía no hay sorteos jugados/)).toBeInTheDocument();
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
  it("ignores late responses after unmount", async () => {
    let resolve!: (t: Trajectory) => void;
    vi.mocked(apiClient.getTrajectory).mockReturnValue(new Promise((done) => { resolve = done; }));
    const loaded = vi.fn(); const { unmount } = render(<RunTrajectory {...props} onLoad={loaded} />);
    unmount(); await act(async () => { resolve(long); });
    expect(loaded).not.toHaveBeenCalled();
  });
  it("rejects malformed indexes without publishing a graph", async () => {
    vi.mocked(apiClient.getTrajectory).mockResolvedValue({ ...long, points: [{ ...long.points[0], source_index: -1 }] });
    const loaded = vi.fn(); render(<RunTrajectory {...props} onLoad={loaded} />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(loaded).not.toHaveBeenCalled();
  });
});
describe("server-derived finance display", () => {
  it("displays backend values verbatim and null ratios as N/A", () => {
    render(<FinancialMetrics money={money} result={{ wagered: 0, paid: 0, net: 123, max_drawdown: 456, roi: null, return_per_wagered: null }} />);
    expect(screen.getByText("Neto").nextElementSibling).toHaveTextContent("EUR 1.23");
    expect(screen.getByText("Máximo de saldo perdido desde un pico").nextElementSibling).toHaveTextContent("EUR 4.56");
    expect(screen.getByText("Cambio sobre lo apostado").nextElementSibling).toHaveTextContent("N/D");
  });
  it("does not replace missing metrics with financial zero", () => {
    render(<FinancialMetrics money={money} result={{ wagered: 20, paid: 60 }} />);
    expect(screen.getByText("Neto").nextElementSibling).toHaveTextContent("No disponible");
    expect(screen.getByText("Retorno por peso apostado").nextElementSibling).toHaveTextContent("N/D");
  });
});
