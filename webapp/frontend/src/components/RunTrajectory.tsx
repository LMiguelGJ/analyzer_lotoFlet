import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/client";
import type { Trajectory } from "../api/types";
import { BalanceChart } from "./BalanceChart";

/** Load a bounded projection of the entire saved run, independently of replay pages. */
export function RunTrajectory({ id, ordinal, name, goal, money, onSelect, onLoad, chart = true }: {
  id: string; ordinal: number; name: string; goal: number;
  money: (amount: number) => string;
  onSelect?: (index: number) => void;
  onLoad?: (ordinal: number, trajectory: Trajectory) => void;
  chart?: boolean;
}) {
  const [data, setData] = useState<Trajectory | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [jump, setJump] = useState("");
  const notify = useRef(onLoad);
  notify.current = onLoad;
  useEffect(() => {
    let live = true;
    setData(null); setError(false);
    void apiClient.getTrajectory(id, ordinal, 500).then((next) => {
      if (!live) return;
      if (!next || !Array.isArray(next.points) || next.points.length > 500 ||
          !Number.isSafeInteger(next.total) || next.total < 0 ||
          !Number.isSafeInteger(next.initial_capital) ||
          !next.minimum || !next.maximum ||
          !Number.isSafeInteger(next.minimum.balance) || !Number.isSafeInteger(next.maximum.balance) ||
          !["none", "minmax-even-v1"].includes(next.reduction_method) ||
          next.reduction_method === "none" && next.points.length !== next.total ||
          next.points.some((p, i) => !Number.isSafeInteger(p.source_index) || p.source_index < 0 || p.source_index >= next.total ||
            !Number.isSafeInteger(p.balance) || typeof p.label !== "string" || i > 0 && p.source_index <= next.points[i - 1].source_index)) throw new Error("Invalid trajectory");
      setData(next); notify.current?.(ordinal, next);
    }).catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [id, ordinal, retry]);
  if (error) return <p role="alert">No se pudo cargar la trayectoria de {name}. <button type="button" className="text-accent underline" onClick={() => setRetry((n) => n + 1)}>Reintentar trayectoria de {name}</button></p>;
  if (!data) return <p role="status">Cargando trayectoria de {name}…</p>;
  const jumpIndex = /^[1-9]\d*$/.test(jump) ? Number(jump) - 1 : -1;
  const canJump = Number.isSafeInteger(jumpIndex) && jumpIndex >= 0 && jumpIndex < data.total;
  return <section aria-label={`Trayectoria de ${name}`} className="my-4 space-y-2">
    <p>{name}: {data.points.length} de {data.total} apuestas · {data.reduction_method === "none" ? "trayectoria completa sin reducción" : `trayectoria completa con reducción ${data.reduction_method} (máximo ${data.max_points} puntos)`}</p>
    <p className="text-sm">Capital inicial: {money(data.initial_capital)} · Mínimo: {money(data.minimum.balance)} · Máximo: {money(data.maximum.balance)}. Inicio, fin y extremos preservados; las líneas no agregan apuestas ni valores intermedios.</p>
    {chart && <BalanceChart points={data.points.map((p) => ({ ordinal: p.source_index + 1, balance: p.balance }))} goal={goal} total={data.total} formatMoney={money} initialCapital={data.initial_capital} reductionMethod={data.reduction_method} />}
    {data.total > 0 && <div className="flex flex-wrap items-center gap-2">
      <label htmlFor={`trajectory-jump-${ordinal}`}>Ir a apuesta exacta (1–{data.total})</label>
      <input id={`trajectory-jump-${ordinal}`} type="number" min={1} max={data.total} value={jump} onChange={(event) => setJump(event.target.value)} className="w-28 rounded-control border border-border-control bg-field p-2" />
      {onSelect ? <button type="button" disabled={!canJump} className="btn btn-secondary" onClick={() => onSelect(jumpIndex)}>Ver apuesta exacta</button>
        : canJump ? <Link className="text-accent underline" to={`/experimentos/${encodeURIComponent(id)}?run=${ordinal}&bet=${jumpIndex}&from=comparison`}>Ver apuesta exacta</Link> : <span>Elegí un número válido</span>}
    </div>}
    <details><summary className="cursor-pointer text-accent">Consultar apuesta exacta de un punto</summary>
      <ul className="max-h-40 overflow-auto text-sm">
        {data.points.map((point) => <li key={point.source_index}>{onSelect
          ? <button type="button" className="text-accent underline" onClick={() => onSelect(point.source_index)}>Apuesta {point.source_index + 1} · {point.label} · {money(point.balance)}</button>
          : <Link className="text-accent underline" to={`/experimentos/${encodeURIComponent(id)}?run=${ordinal}&bet=${point.source_index}&from=comparison`}>Apuesta {point.source_index + 1} · {point.label} · {money(point.balance)}</Link>}</li>)}
      </ul>
    </details>
  </section>;
}
