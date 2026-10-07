import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient, NetworkError } from "../api/client";
import type { BacktestBetsPage, BacktestReport, BacktestSessionsPage, BacktestTraceMetadata } from "../api/types";
import { BacktestSessions } from "./BacktestSessions";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient,
    getBacktestSessions: vi.fn(), getBacktestSessionBets: vi.fn() } };
});
const trace: Exclude<BacktestTraceMetadata, { status: "not_stored" }> = {
  version: 1, status: "complete", reason: null, unit: "native-RD$-integer",
  total_sessions: 21, stored_sessions: 21, total_bets: 22, stored_bets: 22,
  source_window: { count: 25,
    first: { label: "2025-01-01 05:00", source_index: 0, minute: 0 },
    last: { label: "2025-01-01 07:00", source_index: 24, minute: 120 } },
  limits: { bytes: 2097152, bets: 10000, sessions: 1000 },
};
const report = { id: "saved", created_at: "2025-01-01T00:00:00Z", trace } as BacktestReport;
const session = { ordinal: 0, outcome: "reached_goal" as const, final_balance: 89, bets_count: 21,
  first_bet: { label: "2025-01-01 05:10", source_index: 1, minute: 10 },
  last_bet: { label: "2025-01-01 06:50", source_index: 21, minute: 110 } };
const sessions: BacktestSessionsPage = { id: "saved", trace, total: 21, offset: 0, limit: 20, items: [session] };
const bet = { bet_index: 0, label: "2025-01-01 05:10", source_index: 1, minute: 10,
  numbers: [0, 3], per_number: 7, wagered: 14, results: [0, 0, 3, 4, 5], paid: 616, balance: 2602 };
const bets: BacktestBetsPage = { id: "saved", ordinal: 0, trace, session, total: 21,
  offset: 0, limit: 20, items: [bet] };
const formatMoney = (value: number | string) => `RD$${value},0`;
function view(value = report) { return <BacktestSessions report={value} formatMoney={formatMoney} />; }
function deferred<T>() {
  let resolve!: (page: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
beforeEach(() => {
  vi.mocked(apiClient.getBacktestSessions).mockReset().mockResolvedValue(sessions);
  vi.mocked(apiClient.getBacktestSessionBets).mockReset().mockResolvedValue(bets);
});

describe("native historical session explorer", () => {
  it("does not fetch missing IDs, legacy snapshots or genuine empty execution", () => {
    const { rerender } = render(view({ ...report, trace: undefined }));
    expect(screen.getByText("Detalle no almacenado")).toBeInTheDocument();
    rerender(view({ ...report, trace: { status: "not_stored", reason: "legacy" } }));
    expect(screen.getByText("Detalle no almacenado")).toBeInTheDocument();
    rerender(view({ ...report, id: "" }));
    expect(screen.getByText(/Sin identificador guardado/)).toBeInTheDocument();
    rerender(view({ ...report, trace: { ...trace, status: "empty", total_sessions: 0,
      stored_sessions: 0, total_bets: 0, stored_bets: 0 } }));
    expect(screen.getByText(/La ejecución no inició sesiones/)).toBeInTheDocument();
    expect(apiClient.getBacktestSessions).not.toHaveBeenCalled();
  });

  it("shows source boundary separately and loads only selected native bets", async () => {
    const user = userEvent.setup();
    render(view());
    expect(screen.getByText(/Límite inicial de la ventana.*05:00/)).toBeInTheDocument();
    expect(await screen.findByText(/Primera apuesta registrada.*05:10/)).toBeInTheDocument();
    expect(screen.getByText(/Ordinal original: 0/)).toBeInTheDocument();
    expect(screen.queryByText(/^Inicio solicitado:/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /ID oficial/i })).not.toBeInTheDocument();
    expect(apiClient.getBacktestSessionBets).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Ver apuestas de la sesión 1" }));
    const ledger = await screen.findByRole("table", { name: "Apuestas registradas de la sesión 1" });
    const scrollRegion = screen.getByRole("region", { name: "Tabla de apuestas; desplazamiento horizontal" });
    expect(scrollRegion).toHaveClass("backtest-bets-ledger");
    expect(scrollRegion).not.toHaveClass("backtest-report-table");
    expect(scrollRegion).toHaveAttribute("tabindex", "0");
    expect(scrollRegion).toContainElement(ledger);
    expect(within(ledger).getByText("0 / 3")).toBeInTheDocument();
    expect(within(ledger).getByText("0 / 0 / 3 / 4 / 5")).toBeInTheDocument();
    for (const amount of ["RD$7,0", "RD$14,0", "RD$616,0", "RD$2602,0"]) {
      expect(within(ledger).getByText(amount)).toBeInTheDocument();
    }
    expect(apiClient.getBacktestSessionBets).toHaveBeenCalledWith("saved", 0, 0, 20);
  });

  it("pages sessions with keyboard and clears selection and old bets", async () => {
    const user = userEvent.setup();
    const pending = deferred<BacktestSessionsPage>();
    vi.mocked(apiClient.getBacktestSessions).mockResolvedValueOnce(sessions)
      .mockReturnValueOnce(pending.promise);
    render(view());
    await user.click(await screen.findByRole("button", { name: "Ver apuestas de la sesión 1" }));
    await screen.findByRole("table");
    const next = screen.getByRole("button", { name: "Siguientes sesiones" });
    next.focus();
    await user.keyboard("{Enter}");
    const heading = screen.getByRole("heading", { name: "Sesiones almacenadas · página 2" });
    expect(screen.getByText("Cargando sesiones…")).toBeInTheDocument();
    expect(heading).toHaveFocus();
    await act(async () => pending.resolve({ ...sessions, offset: 20, items: [{ ...session, ordinal: 20 }] }));
    expect(heading).toHaveFocus();
    expect(await screen.findByRole("button", { name: "Ver apuestas de la sesión 21" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(apiClient.getBacktestSessions).toHaveBeenLastCalledWith("saved", 20, 20);
  });

  it("pages bets without eagerly loading the ledger or displaying the old page", async () => {
    const user = userEvent.setup();
    let resolve!: (page: BacktestBetsPage) => void;
    vi.mocked(apiClient.getBacktestSessionBets).mockResolvedValueOnce(bets)
      .mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    render(view());
    await user.click(await screen.findByRole("button", { name: "Ver apuestas de la sesión 1" }));
    await screen.findByRole("table");
    screen.getByRole("button", { name: "Siguientes apuestas" }).focus();
    await user.keyboard("{Enter}");
    const heading = screen.getByRole("heading", { name: "Apuestas de la sesión 1 · página 2" });
    expect(heading).toHaveFocus();
    expect(screen.getByText("Cargando apuestas…")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await act(async () => resolve({ ...bets, offset: 20, items: [{ ...bet, bet_index: 20 }] }));
    expect(await screen.findByRole("rowheader", { name: "21" })).toBeInTheDocument();
    expect(heading).toHaveFocus();
    expect(apiClient.getBacktestSessionBets).toHaveBeenLastCalledWith("saved", 0, 20, 20);
  });

  it.each([new NetworkError(), new ApiError(404, "missing"), new ApiError(409, "corrupt")])(
    "does not turn a failed page into empty history and retries only on activation (%s)", async (cause) => {
      const user = userEvent.setup();
      const pending = deferred<BacktestSessionsPage>();
      vi.mocked(apiClient.getBacktestSessions).mockResolvedValueOnce(sessions)
        .mockRejectedValueOnce(cause).mockReturnValueOnce(pending.promise);
      render(view());
      (await screen.findByRole("button", { name: "Siguientes sesiones" })).focus();
      await user.keyboard("{Enter}");
      const heading = screen.getByRole("heading", { name: "Sesiones almacenadas · página 2" });
      expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudo|no existe|no está disponible/);
      expect(screen.queryByText(/no inició sesiones/)).not.toBeInTheDocument();
      expect(heading).toHaveFocus();
      expect(apiClient.getBacktestSessions).toHaveBeenCalledTimes(2);
      screen.getByRole("button", { name: "Reintentar sesiones" }).focus();
      await user.keyboard("{Enter}");
      expect(screen.getByText("Cargando sesiones…")).toBeInTheDocument();
      expect(heading).toHaveFocus();
      await act(async () => pending.resolve({ ...sessions, offset: 20, items: [{ ...session, ordinal: 20 }] }));
      await screen.findByRole("button", { name: "Ver apuestas de la sesión 21" });
      expect(heading).toHaveFocus();
      expect(apiClient.getBacktestSessions).toHaveBeenCalledTimes(3);
      expect(apiClient.getBacktestSessions).toHaveBeenLastCalledWith("saved", 20, 20);
    },
  );

  it("retries failed bets once per activation without showing fake empty history", async () => {
    const user = userEvent.setup();
    const pending = deferred<BacktestBetsPage>();
    vi.mocked(apiClient.getBacktestSessionBets).mockResolvedValueOnce(bets)
      .mockRejectedValueOnce(new NetworkError()).mockReturnValueOnce(pending.promise);
    render(view());
    await user.click(await screen.findByRole("button", { name: "Ver apuestas de la sesión 1" }));
    (await screen.findByRole("button", { name: "Siguientes apuestas" })).focus();
    await user.keyboard("{Enter}");
    const heading = screen.getByRole("heading", { name: "Apuestas de la sesión 1 · página 2" });
    expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudo contactar/);
    expect(screen.queryByText(/sin apuestas registradas/)).not.toBeInTheDocument();
    expect(heading).toHaveFocus();
    expect(apiClient.getBacktestSessionBets).toHaveBeenCalledTimes(2);
    screen.getByRole("button", { name: "Reintentar apuestas" }).focus();
    await user.keyboard("{Enter}");
    expect(screen.getByText("Cargando apuestas…")).toBeInTheDocument();
    expect(heading).toHaveFocus();
    await act(async () => pending.resolve({ ...bets, offset: 20, items: [{ ...bet, bet_index: 20 }] }));
    await screen.findByRole("table");
    expect(heading).toHaveFocus();
    expect(apiClient.getBacktestSessionBets).toHaveBeenCalledTimes(3);
    expect(apiClient.getBacktestSessionBets).toHaveBeenLastCalledWith("saved", 0, 20, 20);
  });

  it.each(["sesiones", "apuestas"] as const)(
    "never steals outside focus on initial load or late %s success/error/retry", async (kind) => {
      const user = userEvent.setup();
      const sessionPage = deferred<BacktestSessionsPage>();
      const betPage = deferred<BacktestBetsPage>();
      const sessionRetry = deferred<BacktestSessionsPage>();
      const betRetry = deferred<BacktestBetsPage>();
      if (kind === "sesiones") {
        vi.mocked(apiClient.getBacktestSessions).mockResolvedValueOnce(sessions)
          .mockReturnValueOnce(sessionPage.promise).mockReturnValueOnce(sessionRetry.promise);
      } else {
        vi.mocked(apiClient.getBacktestSessionBets).mockResolvedValueOnce(bets)
          .mockReturnValueOnce(betPage.promise).mockReturnValueOnce(betRetry.promise);
      }
      render(<><button type="button">Fuera del detalle</button>{view()}</>);
      const outside = screen.getByRole("button", { name: "Fuera del detalle" });
      outside.focus();
      await screen.findByRole("button", { name: "Ver apuestas de la sesión 1" });
      expect(outside).toHaveFocus();
      if (kind === "apuestas") {
        const select = screen.getByRole("button", { name: "Ver apuestas de la sesión 1" });
        await user.click(select);
        await screen.findByRole("table");
        expect(select).toHaveFocus();
      }
      screen.getByRole("button", { name: `Siguientes ${kind}` }).focus();
      await user.keyboard("{Enter}");
      outside.focus();
      await act(async () => (kind === "sesiones" ? sessionPage : betPage).reject(new NetworkError()));
      await screen.findByRole("alert");
      expect(outside).toHaveFocus();
      screen.getByRole("button", { name: `Reintentar ${kind}` }).focus();
      await user.keyboard("{Enter}");
      outside.focus();
      await act(async () => {
        if (kind === "sesiones") sessionRetry.resolve({ ...sessions, offset: 20 });
        else betRetry.resolve({ ...bets, offset: 20 });
      });
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(outside).toHaveFocus();
    },
  );

  it("ignores stale bets when another session is selected and resets its page", async () => {
    const user = userEvent.setup();
    let resolve!: (page: BacktestBetsPage) => void;
    vi.mocked(apiClient.getBacktestSessions).mockResolvedValue({ ...sessions,
      items: [session, { ...session, ordinal: 1 }] });
    vi.mocked(apiClient.getBacktestSessionBets)
      .mockImplementationOnce(() => new Promise((done) => { resolve = done; }))
      .mockResolvedValueOnce({ ...bets, ordinal: 1,
        items: [{ ...bet, label: "2025-01-01 06:00" }] });
    render(view());
    await user.click(await screen.findByRole("button", { name: "Ver apuestas de la sesión 1" }));
    await user.click(screen.getByRole("button", { name: "Ver apuestas de la sesión 2" }));
    const ledger = await screen.findByRole("table", { name: "Apuestas registradas de la sesión 2" });
    await act(async () => resolve(bets));
    expect(within(ledger).getByText("2025-01-01 06:00")).toBeInTheDocument();
    expect(within(ledger).queryByText("2025-01-01 05:10")).not.toBeInTheDocument();
    expect(apiClient.getBacktestSessionBets).toHaveBeenLastCalledWith("saved", 1, 0, 20);
  });

  it("ignores a stale report response and clears the selected session", async () => {
    const user = userEvent.setup();
    let resolve!: (page: BacktestBetsPage) => void;
    vi.mocked(apiClient.getBacktestSessionBets).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    const { rerender } = render(view());
    await user.click(await screen.findByRole("button", { name: "Ver apuestas de la sesión 1" }));
    rerender(view({ ...report, id: "new" }));
    await act(async () => resolve(bets));
    await waitFor(() => expect(apiClient.getBacktestSessions).toHaveBeenLastCalledWith("new", 0, 20));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("keeps unavailable truncated capture distinct from genuine empty sessions", () => {
    render(view({ ...report, trace: { ...trace, status: "truncated", reason: "limit_exceeded",
      stored_sessions: 0, stored_bets: 0 } }));
    expect(screen.getByText(/Detalle limitado/)).toBeInTheDocument();
    expect(screen.getByText(/Ninguna sesión completa cupo/)).toBeInTheDocument();
    expect(apiClient.getBacktestSessions).not.toHaveBeenCalled();
  });

  it("shows a stored zero-bet session as such, not a missing or failed query", async () => {
    const user = userEvent.setup();
    const zero = { ...session, bets_count: 0, first_bet: null, last_bet: null, outcome: "quiebre" as const };
    vi.mocked(apiClient.getBacktestSessions).mockResolvedValue({ ...sessions, items: [zero] });
    vi.mocked(apiClient.getBacktestSessionBets).mockResolvedValue({ ...bets, session: zero, total: 0, items: [] });
    render(view());
    await user.click(await screen.findByRole("button", { name: "Ver apuestas de la sesión 1" }));
    expect(await screen.findByText("Esta sesión se cerró sin apuestas registradas.")).toBeInTheDocument();
    expect(screen.getByText(/Primera apuesta registrada: ninguna/)).toBeInTheDocument();
  });
});
