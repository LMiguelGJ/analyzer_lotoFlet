import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, NetworkError } from "../../api/client";
import { listLaboratories } from "../../api/laboratories";
import type { LaboratoryDefinition } from "../../api/laboratories";
import type { ReferencePage } from "../../api/referenceLabs";
import { ErrorBanner, Loading } from "../../components/ui/Feedback";
import { count } from "./count";
import { stakeLabel, systemLabel } from "../reference-labs/lab-model";
import { LaboratoryForm } from "./LaboratoryForm";
import { LaboratoryPanel } from "./LaboratoryPanel";
import "../reference-labs/reference-labs.css";
import "./laboratories.css";

const PAGE = 20;
const CREATE_SEGMENT = "nuevo";

function failureText(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof NetworkError) return "No se pudo contactar al servidor local. Revisá la conexión e intentá de nuevo.";
  return "No se pudo leer la lista de laboratorios.";
}
function summary(definition: LaboratoryDefinition): string {
  const { config } = definition;
  return `${systemLabel(config.system)} · ${config.coverage} ${config.coverage === 1 ? "número" : "números"} · ${stakeLabel(config.stake_style)}`;
}

export function Workspace() {
  const { labId } = useParams();
  const navigate = useNavigate();
  const [page, setPage] = useState<ReferencePage<LaboratoryDefinition> | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const creating = labId === CREATE_SEGMENT;
  const refresh = useCallback(() => setReload((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController(); let current = true;
    setFailure(null);
    listLaboratories({ offset, limit: PAGE }, { signal: controller.signal }).then((value) => {
      if (!current) return;
      if (offset > 0 && value.items.length === 0 && value.total > 0) { setOffset(Math.max(0, Math.ceil(value.total / PAGE - 1) * PAGE)); return; }
      setPage(value);
    }).catch((error: unknown) => { if (current && !(error instanceof Error && error.name === "AbortError")) setFailure(failureText(error)); });
    return () => { current = false; controller.abort(); };
  }, [offset, reload]);

  return <div className="lab-workspace" data-selected={labId ? "true" : "false"}>
    <aside className="lab-sidebar" aria-label="Laboratorios guardados">
      <div className="lab-sidebar-head">
        <h2>Laboratorios</h2>
        <Link className="ledger-button ledger-button-secondary" to={`/laboratorios/${CREATE_SEGMENT}`} aria-current={creating ? "page" : undefined}>Nuevo laboratorio</Link>
      </div>
      {failure ? <ErrorBanner cause="No pudimos cargar los laboratorios." recovery={failure} actionLabel="Reintentar" onAction={refresh} />
        : !page ? <Loading label="Cargando laboratorios…" rows={4} />
        : page.items.length === 0 ? <p className="reference-empty">No hay laboratorios guardados. Creá el primero con «Nuevo laboratorio».</p>
        : <>
          <ul className="lab-list">
            {page.items.map((definition) => <li key={definition.id}>
              <Link to={`/laboratorios/${encodeURIComponent(definition.id)}`} aria-current={labId === definition.id ? "page" : undefined}>
                <span className="lab-list-name">{definition.name}</span>
                <span className="lab-list-meta">{summary(definition)}</span>
              </Link>
            </li>)}
          </ul>
          <nav className="reference-pagination" aria-label="Paginación de laboratorios"><span>{count(page.total, "laboratorio", "laboratorios")}</span>
            <div><button type="button" className="ledger-button ledger-button-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Anterior</button>
              <button type="button" className="ledger-button ledger-button-secondary" disabled={offset + PAGE >= page.total} onClick={() => setOffset(offset + PAGE)}>Siguiente</button></div></nav>
        </>}
    </aside>
    <div className="lab-stage">
      {creating ? <LaboratoryForm onCreated={(definition) => { setOffset(0); refresh(); navigate(`/laboratorios/${encodeURIComponent(definition.id)}`); }} />
        : labId ? <LaboratoryPanel key={labId} labId={labId} onDeleted={() => { refresh(); navigate("/laboratorios"); }} />
        : <section className="reference-page" aria-labelledby="lab-empty-title"><header className="reference-heading"><div><h2 id="lab-empty-title">Elegí un laboratorio</h2><p>Abrí uno de la lista para ejecutarlo y ver sus corridas, o definí uno nuevo con tus propias reglas. Describen el pasado; no predicen sorteos.</p></div></header></section>}
    </div>
  </div>;
}
