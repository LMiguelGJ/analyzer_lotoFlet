import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { listSessionBets } from "../../api/runs";
import type { SessionBetsPage } from "../../api/types";
import { formatNumber, formatSignedDOP, formatTwoDigit } from "../../lib/format";
import { Button } from "../../components/ui/Controls";
import { Loading } from "../../components/ui/Feedback";

const BET_PAGE_SIZE = 20;
function message(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  return "No se pudo contactar al servidor local. Revisá la conexión e intentá de nuevo.";
}
function numbers(values: number[]): string { return values.map(formatTwoDigit).join(", "); }

export function RunBets({ runId, ordinal }: { runId: string; ordinal: number }) {
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<SessionBetsPage | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController(); let current = true;
    setPage(null); setUnavailable(false); setFailure(null); setLoading(true);
    listSessionBets(runId, ordinal, { offset, limit: BET_PAGE_SIZE }, { signal: controller.signal }).then((loaded) => {
      if (!current) return;
      if (!loaded.detail_available || !loaded.session.detail_available) { setUnavailable(true); return; }
      setPage(loaded);
    }).catch((error: unknown) => {
      if (current && !(error instanceof Error && error.name === "AbortError")) setFailure(message(error));
    }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [runId, ordinal, offset, revision]);

  if (loading) return <Loading label={`Cargando apuestas de la sesión ${formatNumber(ordinal)}…`} rows={3} />;
  if (unavailable) return <p className="result-empty">Detalle de apuestas no almacenado para esta sesión</p>;
  if (failure) return <div className="runs-inline-error" role="alert"><p>No se pudieron cargar las apuestas de esta sesión.</p><p>{failure}</p><Button onClick={() => setRevision((value) => value + 1)}>Reintentar apuestas</Button></div>;
  if (!page) return <p className="result-empty">No hay detalle de apuestas disponible.</p>;
  if (page.total === 0) return <p className="result-empty">Esta sesión no contiene apuestas guardadas.</p>;

  return <div className="result-bets">
    <div className="runs-table-wrap result-table-wrap" role="region" aria-label={`Apuestas de sesión ${formatNumber(ordinal)}`} tabIndex={0}><table className="runs-table result-bet-table"><thead><tr><th scope="col">Apuesta</th><th scope="col">Sorteo</th><th scope="col">Números apostados</th><th scope="col">Resultados</th><th scope="col">Apostado</th><th scope="col">Pagado</th><th scope="col">Saldo</th></tr></thead><tbody>{page.items.map((bet) => <tr key={bet.index}><th scope="row">{formatNumber(bet.index)}</th><td>{bet.label}</td><td>{numbers(bet.numbers)}</td><td>{numbers(bet.results)}</td><td className="runs-money">{formatSignedDOP(bet.wagered)}</td><td className="runs-money">{formatSignedDOP(bet.paid)}</td><td className="runs-money">{formatSignedDOP(bet.balance)}</td></tr>)}</tbody></table></div>
    <nav className="runs-pagination result-pagination" aria-label="Paginación de apuestas"><span>Apuestas: {formatNumber(page.offset + 1)}–{formatNumber(Math.min(page.offset + page.items.length, page.total))} de {formatNumber(page.total)}</span><div><Button variant="secondary" disabled={page.offset === 0} onClick={() => setOffset(Math.max(0, page.offset - page.limit))}>Anterior apuestas</Button><Button variant="secondary" disabled={page.offset + page.items.length >= page.total} onClick={() => setOffset(page.offset + page.limit)}>Siguiente apuestas</Button></div></nav>
  </div>;
}
