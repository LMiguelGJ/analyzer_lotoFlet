import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/client";
import type { Trajectory } from "../api/types";
import { BalanceChart } from "./BalanceChart";
import { Loading } from "./ui";

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
  const identity = useRef(`${id}:${ordinal}`);
  notify.current = onLoad;
  useEffect(() => {
    let live = true;
    if (identity.current !== `${id}:${ordinal}`) { identity.current = `${id}:${ordinal}`; setData(null); }
    setError(false);
    void apiClient.getTrajectory(id, ordinal, 500).then((next) => {
      if (!live) return;
      const isCanonicalV5 = next?.result_kind === "profile" && next.schema_version === 5;
      if (!next || !Array.isArray(next.points) || next.points.length > 500 ||
          !Number.isSafeInteger(next.total) || next.total < 0 ||
          !Number.isSafeInteger(next.initial_capital) ||
          !next.minimum || !next.maximum ||
          !Number.isSafeInteger(next.minimum.balance) || !Number.isSafeInteger(next.maximum.balance) ||
          !["none", "minmax-even-v1"].includes(next.reduction_method) ||
          next.reduction_method === "none" && next.points.length !== next.total ||
          next.points.some((p, i) => !Number.isSafeInteger(p.source_index) || p.source_index < 0 ||
            (isCanonicalV5 ? !Number.isSafeInteger(p.bet_index) || p.bet_index! < 0 || p.bet_index! >= next.total ||
              i > 0 && p.bet_index! <= next.points[i - 1].bet_index! : p.source_index >= next.total ||
              i > 0 && p.source_index <= next.points[i - 1].source_index) ||
            !Number.isSafeInteger(p.balance) || typeof p.label !== "string")) throw new Error("Invalid trajectory");
      setData(next); notify.current?.(ordinal, next);
    }).catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [id, ordinal, retry]);
  if (error && !data) return <p role="alert">No se pudo cargar la trayectoria de {name}. Podés volver a intentar. <button type="button" className="btn btn-tertiary" onClick={() => setRetry((n) => n + 1)}>Reintentar trayectoria de {name}</button></p>;
  if (!data) return <Loading rows={3} label={`Cargando trayectoria de ${name}…`} className="my-4" />;
  const jumpIndex = /^[1-9]\d*$/.test(jump) ? Number(jump) - 1 : -1;
  const canJump = Number.isSafeInteger(jumpIndex) && jumpIndex >= 0 && jumpIndex < data.total;
  const localIndex = (point: Trajectory["points"][number]) => point.bet_index ?? point.source_index;
  const plottedPoints = data.points.map((point) => ({ ordinal: localIndex(point) + 1, balance: point.balance }));
  return <section aria-label={`Trayectoria de ${name}`} className="my-4 space-y-2">
    {error && <p role="alert">No se pudo actualizar la trayectoria; se conservan los datos cargados. Podés reintentar. <button type="button" className="btn btn-tertiary" onClick={() => setRetry((n) => n + 1)}>Reintentar trayectoria de {name}</button></p>}
    <details><summary className="disclosure-summary">Detalles técnicos · {name}</summary>
    <p>{data.points.length} de {data.total} puntos mostrados; modo {data.reduction_method}; máximo {data.max_points} puntos.</p>
    <p>{name}: {data.points.length} de {data.total} apuestas{data.reduction_method === "none" ? "" : ` · reducción ${data.reduction_method}`}</p>
    <p className="text-sm">Índices de origen: mínimo {data.minimum.source_index ?? "no disponible"}, máximo {data.maximum.source_index ?? "no disponible"}. La línea no agrega sorteos ni valores intermedios.</p></details>
    {chart && data.total > 0 && <BalanceChart points={plottedPoints} goal={goal} total={data.total} formatMoney={money} initialCapital={data.initial_capital} reductionMethod={data.reduction_method} />}
    {data.total === 0 && <p role="status">Todavía no hay sorteos jugados; consultá la cola más tarde para ver la evolución.</p>}
    {data.total > 0 && <div className="flex flex-wrap items-center gap-2">
      <label htmlFor={`trajectory-jump-${ordinal}`} className="legend">Ir a sorteo (1–{data.total})</label>
      <input id={`trajectory-jump-${ordinal}`} type="number" min={1} max={data.total} value={jump} onChange={(event) => setJump(event.target.value)} className="w-28 border border-border-control bg-field p-2" />
      {onSelect ? <button type="button" disabled={!canJump} className="btn btn-secondary" onClick={() => onSelect(jumpIndex)}>Ver apuesta exacta</button>
        : canJump ? <Link className="btn btn-tertiary" to={`/simulaciones/${encodeURIComponent(id)}?run=${ordinal}&bet=${jumpIndex}&from=comparison`}>Ver apuesta exacta</Link> : <span>Elegí un número válido</span>}
    </div>}
    <details><summary className="disclosure-summary">Consultar detalle técnico de un punto</summary>
      <ul className="max-h-40 overflow-auto text-sm">
        {data.points.map((point) => <li key={point.source_index}>{onSelect
          ? <button type="button" className="link" onClick={() => onSelect(localIndex(point))}>Apuesta {localIndex(point) + 1}{point.bet_index == null ? "" : ` · sorteo n.º ${point.source_index}`} · {point.label} · {money(point.balance)}</button>
          : <Link className="link" to={`/simulaciones/${encodeURIComponent(id)}?run=${ordinal}&bet=${localIndex(point)}&from=comparison`}>Apuesta {localIndex(point) + 1}{point.bet_index == null ? "" : ` · sorteo n.º ${point.source_index}`} · {point.label} · {money(point.balance)}</Link>}</li>)}
      </ul>
    </details>
  </section>;
}
