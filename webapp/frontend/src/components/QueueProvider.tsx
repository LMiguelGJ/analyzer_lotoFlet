import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { apiClient, ApiError, NetworkError } from "../api/client";
import type { ExperimentStatus, QueueStatus } from "../api/types";

const PAGE_SIZE = 20;
export type QueueAction = { id: string; kind: "cancel" | "start" };
export type RequestLock = {
  kind: QueueAction["kind"];
  outcome: string;
  originOffset: number;
  started?: boolean;
  terminal?: boolean;
  checkedStatus?: ExperimentStatus;
  checking?: boolean;
};

function actionError(cause: unknown, kind: QueueAction["kind"]): string {
  if (cause instanceof NetworkError) return "La solicitud puede haber llegado; comprobá el estado desde la cola antes de reintentar.";
  if (cause instanceof ApiError) {
    if (cause.status === 404) return "El experimento ya no existe. Actualizá la cola.";
    if (cause.status === 409) return kind === "start" ? "Este experimento ya no puede iniciarse. Comprobá su estado." : "Este experimento ya no puede cancelarse. Comprobá su estado.";
    if (cause.status === 507) return "No hay espacio o cuota suficiente para iniciar. Revisá Ajustes y volvé a intentar.";
  }
  return "No se pudo completar la acción. Comprobá el estado antes de repetirla.";
}

interface QueueContextValue {
  status: QueueStatus | null;
  error: "network" | "server" | null;
  loading: boolean;
  offset: number;
  setOffset: (offset: number) => void;
  refresh: () => void;
  requests: Record<string, RequestLock>;
  errors: Record<string, string>;
  busy: string | null;
  perform: (action: QueueAction, repeat?: boolean) => Promise<"accepted" | "uncertain" | "rejected" | "ignored">;
  check: (id: string) => Promise<void>;
}
const QueueContext = createContext<QueueContextValue | null>(null);

/** One bounded queue poll per app instance, across route and drawer remounts.
 * Actions are session-only; a browser reload has no persisted action registry.
 */
export function QueueProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<QueueStatus | null>(null);
  const [error, setError] = useState<QueueContextValue["error"]>(null);
  const [loading, setLoading] = useState(true);
  const [offset, setOffsetState] = useState(0);
  const [revision, setRevision] = useState(0);
  const [requests, setRequests] = useState<Record<string, RequestLock>>({});
  const requestsRef = useRef(requests);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const busyRef = useRef<string | null>(null);
  const inspections = useRef(new Map<string, { lock: RequestLock; promise: ReturnType<typeof apiClient.getExperiment> }>());
  const sequence = useRef(0);
  const setOffset = useCallback((next: number) => setOffsetState(Math.max(0, Math.floor(next / PAGE_SIZE) * PAGE_SIZE)), []);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  const changeRequests = useCallback((next: Record<string, RequestLock>) => {
    requestsRef.current = next;
    setRequests(next);
  }, []);
  const updateLock = useCallback((id: string, lock: RequestLock, next: RequestLock | null) => {
    if (requestsRef.current[id] !== lock) return;
    const updated = { ...requestsRef.current };
    if (next) updated[id] = next;
    else delete updated[id];
    changeRequests(updated);
  }, [changeRequests]);

  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    const ticket = ++sequence.current;
    setError(null);
    setLoading(true);
    async function poll() {
      try {
        const result = await apiClient.getQueue(offset, PAGE_SIZE);
        if (!live || ticket !== sequence.current) return;
        setStatus(result);
        setError(null);
        setLoading(false);
        if (offset > 0 && result.pending.total <= offset && result.held.total <= offset) {
          setOffsetState(Math.max(0, Math.ceil(Math.max(result.pending.total, result.held.total) / PAGE_SIZE) - 1) * PAGE_SIZE);
          return;
        }
      } catch (cause) {
        if (!live || ticket !== sequence.current) return;
        setError(cause instanceof NetworkError ? "network" : "server");
        setLoading(false); // Keep the last authoritative response visible, but mark it stale.
      }
      if (live) timer = setTimeout(poll, 5000);
    }
    void poll();
    return () => { live = false; ++sequence.current; clearTimeout(timer); };
  }, [offset, revision]);

  const inspect = useCallback(async (id: string, lock: RequestLock, explicit: boolean, snapshot: QueueStatus | null) => {
    if (requestsRef.current[id] !== lock || lock.outcome === "sending") return;
    let inspection = inspections.current.get(id);
    if (!inspection || inspection.lock !== lock) {
      const promise = apiClient.getExperiment(id);
      inspection = { lock, promise };
      inspections.current.set(id, inspection);
      void promise.finally(() => {
        if (inspections.current.get(id)?.promise === promise) inspections.current.delete(id);
      }).catch(() => { /* A failed detail must remain locked. */ });
    }
    const checkingLock = explicit ? { ...lock, checking: true, checkedStatus: undefined } : lock;
    if (explicit) updateLock(id, lock, checkingLock);
    try {
      const experiment = await inspection.promise;
      const current = requestsRef.current[id];
      if (current !== checkingLock) return;
      const onPage = snapshot && (snapshot.active_id === id || snapshot.pending.items.includes(id) || snapshot.held.items.includes(id));
      const originReady = snapshot?.pending.offset === current.originOffset && snapshot?.held.offset === current.originOffset;
      if (["completed", "cancelled", "interrupted", "failed"].includes(experiment.status)) {
        updateLock(id, current, originReady && !onPage ? null : { ...current, terminal: true, checking: false, checkedStatus: undefined });
        if (explicit) refresh();
      } else if (current.kind === "start" && (experiment.status === "pending" || experiment.status === "running")) {
        updateLock(id, current, originReady && !snapshot?.held.items.includes(id) ? null : { ...current, started: true, checking: false, checkedStatus: undefined });
      } else if (current.kind === "start" && current.started && experiment.status === "held" && originReady && snapshot?.held.items.includes(id)) {
        updateLock(id, current, null); // A later restart produced a new held action.
      } else if (explicit) {
        updateLock(id, current, { ...current, checking: false, checkedStatus: experiment.status });
        setErrors((previous) => ({ ...previous, [id]: "" }));
      }
    } catch (cause) {
      const current = requestsRef.current[id];
      if (current !== checkingLock) return;
      if (cause instanceof ApiError && cause.status === 404) {
        const onPage = snapshot && (snapshot.active_id === id || snapshot.pending.items.includes(id) || snapshot.held.items.includes(id));
        const originReady = snapshot?.pending.offset === current.originOffset && snapshot?.held.offset === current.originOffset;
        updateLock(id, current, originReady && !onPage ? null : { ...current, terminal: true, checking: false, checkedStatus: undefined });
        if (explicit) refresh();
      } else if (explicit) {
        updateLock(id, current, { ...current, checking: false, checkedStatus: undefined });
        setErrors((previous) => ({ ...previous, [id]: "No se pudo comprobar el estado. La acción sigue bloqueada; volvé a comprobarla." }));
      }
    }
  }, [refresh, updateLock]);

  useEffect(() => {
    if (!status || error) return;
    for (const [id, lock] of Object.entries(requestsRef.current)) {
      const onPage = status.active_id === id || status.pending.items.includes(id) || status.held.items.includes(id);
      const originReady = status.pending.offset === lock.originOffset && status.held.offset === lock.originOffset;
      if (lock.terminal) {
        if (originReady && !onPage) updateLock(id, lock, null);
      } else if (lock.kind === "start" && (status.active_id === id || status.pending.items.includes(id))) {
        updateLock(id, lock, null); // Positive queue evidence, no detail request.
      } else if (lock.outcome !== "sending" && !lock.checking) {
        void inspect(id, lock, false, status);
      }
    }
  }, [status, error, inspect, updateLock]);

  const check = useCallback(async (id: string) => {
    const lock = requestsRef.current[id];
    if (!lock || lock.terminal || lock.checking || busyRef.current) return;
    await inspect(id, lock, true, status);
  }, [inspect, status]);

  const perform = useCallback(async (action: QueueAction, repeat = false) => {
    const previous = requestsRef.current[action.id];
    if (busyRef.current || (previous && !repeat)) return "ignored";
    if (repeat && (!previous || previous.kind !== action.kind || previous.terminal || previous.checking ||
      !(action.kind === "start" ? previous.checkedStatus === "held" :
        previous.checkedStatus === "pending" || previous.checkedStatus === "running" || previous.checkedStatus === "held"))) return "ignored";
    busyRef.current = action.id;
    setBusy(action.id);
    const lock: RequestLock = { kind: action.kind, outcome: "sending", originOffset: previous?.originOffset ?? offset };
    changeRequests({ ...requestsRef.current, [action.id]: lock });
    setErrors((prior) => ({ ...prior, [action.id]: "" }));
    try {
      const result = action.kind === "start" ? await apiClient.startHeld(action.id) : await apiClient.cancelJob(action.id);
      updateLock(action.id, lock, { ...lock, outcome: repeat ? "resent" : result.status });
      refresh();
      return "accepted";
    } catch (cause) {
      if (cause instanceof NetworkError) {
        updateLock(action.id, lock, { ...lock, outcome: "uncertain" });
        refresh();
      } else if (repeat) {
        updateLock(action.id, lock, { ...lock, outcome: previous!.outcome });
      } else if (cause instanceof ApiError && (cause.status === 404 || cause.status === 409)) {
        // The response is known, but an old queue page cannot prove the row is actionable.
        updateLock(action.id, lock, { ...lock, outcome: "rejected" });
      } else {
        updateLock(action.id, lock, null);
      }
      setErrors((prior) => ({ ...prior, [action.id]: actionError(cause, action.kind) }));
      if (cause instanceof ApiError && (cause.status === 404 || cause.status === 409)) refresh();
      return cause instanceof NetworkError ? "uncertain" : "rejected";
    } finally {
      busyRef.current = null;
      setBusy(null);
    }
  }, [changeRequests, offset, refresh, updateLock]);

  return <QueueContext.Provider value={{ status, error, loading, offset, setOffset, refresh, requests, errors, busy, perform, check }}>{children}</QueueContext.Provider>;
}

export function useQueue() {
  const value = useContext(QueueContext);
  if (!value) throw new Error("QueueProvider is required for queue consumers");
  return value;
}
