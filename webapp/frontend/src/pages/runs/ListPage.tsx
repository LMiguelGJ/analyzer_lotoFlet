import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { deleteRun, getRunOptions, listRuns } from "../../api/runs";
import type { Page, RunOptions, RunReport } from "../../api/types";
import { formatNumber, formatSignedDOP } from "../../lib/format";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Button } from "../../components/ui/Controls";
import { EmptyState, ErrorBanner, Loading } from "../../components/ui/Feedback";
import { formatStrategyLabel } from "./run-model";
import "./runs.css";

const PAGE_SIZE = 20;
const detailLabel = { complete: "Detalle completo", partial: "Detalle parcial", sessions_truncated: "Sesiones truncadas" } as const;
function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  return "No se pudo contactar al servidor local. Revisá la conexión e intentá de nuevo.";
}

export function ListPage() {
  const navigate = useNavigate();
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page<RunReport> | null>(null);
  const [systems, setSystems] = useState<RunOptions["systems"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<string | null>(null);
  const [target, setTarget] = useState<RunReport | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setLoading(true); setFailure(null);
    Promise.allSettled([
      listRuns({ offset, limit: PAGE_SIZE }, { signal: controller.signal }),
      getRunOptions({ signal: controller.signal }),
    ]).then(([pageResult, optionsResult]) => {
      if (!current) return;
      if (pageResult.status === "rejected") {
        if (!(pageResult.reason instanceof Error && pageResult.reason.name === "AbortError")) setFailure(errorText(pageResult.reason));
      } else {
        const response = pageResult.value;
        if (offset > 0 && response.items.length === 0 && response.total > 0) {
          setOffset(Math.max(0, Math.ceil(response.total / PAGE_SIZE - 1) * PAGE_SIZE));
          return;
        }
        setPage(response);
      }
      setSystems(optionsResult.status === "fulfilled" ? optionsResult.value.systems : null);
    }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [offset, reload]);

  const retry = useCallback(() => setReload((value) => value + 1), []);
  async function confirmDelete() {
    if (!target || deleting) return;
    setDeleting(true); setDeleteError(null);
    try {
      await deleteRun(target.id);
      const nextTotal = Math.max(0, (page?.total ?? 1) - 1);
      setTarget(null);
      setOffset(nextTotal === 0 ? 0 : offset >= nextTotal ? Math.floor((nextTotal - 1) / PAGE_SIZE) * PAGE_SIZE : offset);
      retry();
    } catch (error) {
      setDeleteError(errorText(error));
      setTarget(null);
    } finally { setDeleting(false); }
  }

  return <section className="runs-page" aria-labelledby="runs-title">
    <header className="runs-heading"><div><h2 id="runs-title">Corridas</h2><p>Pruebas sobre el historial guardado, no predicciones.</p></div><Link className="ledger-button ledger-button-primary" to="/corridas/nueva">Nueva corrida</Link></header>
    {deleteError && <div role="alert" className="runs-inline-error"><p>{deleteError}</p><Button onClick={() => setDeleteError(null)}>Cerrar</Button></div>}
    {deleting && <p className="runs-inline-error" role="status">Borrando corrida…</p>}
    {loading ? <Loading label="Cargando corridas…" rows={4} /> : failure ? <ErrorBanner cause="No pudimos cargar las corridas." recovery={failure} actionLabel="Reintentar" onAction={retry} /> : !page?.items.length ? <EmptyState title="Todavía no hay corridas" description="Definí reglas y una estrategia para medir qué habría ocurrido en el historial." actionLabel="Nueva corrida" onAction={() => navigate("/corridas/nueva")} /> : <>
      <div className="runs-table-wrap" role="region" aria-label="Lista de corridas" tabIndex={0}><table className="runs-table"><thead><tr><th scope="col">Nombre y estrategia</th><th scope="col">Ventana</th><th scope="col">Neto total</th><th scope="col">Detalle guardado</th><th scope="col"><span className="sr-only">Acciones</span></th></tr></thead><tbody>{page.items.map((run) => <tr key={run.id}>
        <th scope="row"><Link className="link runs-name" to={`/corridas/${encodeURIComponent(run.id)}`}>{run.name}</Link><span className="runs-subline">{formatStrategyLabel(run.config.strategy, systems ?? [])}</span></th>
        <td>{run.summary.window.first_label} – {run.summary.window.last_label}</td>
        <td className={`runs-money ${run.summary.totals.net < 0 ? "is-negative" : ""}`}>{formatSignedDOP(run.summary.totals.net)}</td>
        <td>{detailLabel[run.summary.detail.status]}</td>
        <td><div className="runs-actions"><Link className="link" to={`/corridas/${encodeURIComponent(run.id)}`}>Abrir</Link><Link className="link" to={`/corridas/nueva?base=${encodeURIComponent(run.id)}`}>Repetir con cambios</Link><button className="runs-delete" type="button" disabled={deleting} onClick={() => { setDeleteError(null); setTarget(run); }}>Borrar</button></div></td>
      </tr>)}</tbody></table></div>
      <nav className="runs-pagination" aria-label="Paginación de corridas"><span>{formatNumber(page.total)} corridas · {formatNumber(offset + 1)}–{formatNumber(Math.min(offset + PAGE_SIZE, page.total))}</span><div><Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</Button><Button variant="secondary" disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</Button></div></nav>
    </>}
    <ConfirmDialog open={!!target && !deleting} title="Borrar esta corrida" description={target ? `Se eliminará “${target.name}” del historial guardado. Esta acción no se puede deshacer.` : ""} confirmLabel={deleting ? "Borrando…" : "Borrar"} cancelLabel="Cancelar" onCancel={() => { if (!deleting) setTarget(null); }} onConfirm={() => void confirmDelete()} />
  </section>;
}
