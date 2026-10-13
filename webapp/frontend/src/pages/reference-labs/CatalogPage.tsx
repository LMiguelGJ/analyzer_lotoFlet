import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, NetworkError } from "../../api/client";
import { getReferenceLabs } from "../../api/referenceLabs";
import type { ReferenceCatalog } from "../../api/referenceLabs";
import { ErrorBanner, Loading } from "../../components/ui/Feedback";
import { labTitle } from "./lab-model";
import "./reference-labs.css";

function failureText(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof NetworkError) return "No se pudo contactar al servidor local. Revisá la conexión e intentá de nuevo.";
  return "No se pudo leer el catálogo de laboratorios.";
}

export function CatalogPage() {
  const [catalog, setCatalog] = useState<ReferenceCatalog | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setFailure(null);
    getReferenceLabs({ signal: controller.signal }).then((value) => {
      if (current) setCatalog(value);
    }).catch((error: unknown) => {
      if (current && !(error instanceof Error && error.name === "AbortError")) setFailure(failureText(error));
    });
    return () => { current = false; controller.abort(); };
  }, [reload]);

  return <section className="reference-page" aria-labelledby="reference-catalog-title">
    <header className="reference-heading"><div><h2 id="reference-catalog-title">Laboratorios de referencia</h2><p>Reproducciones históricas con reglas fijadas; describen el pasado, no predicen sorteos.</p></div></header>
    {failure ? <ErrorBanner cause="No pudimos cargar los laboratorios." recovery={failure} actionLabel="Reintentar" onAction={() => setReload((value) => value + 1)} /> : !catalog ? <Loading label="Cargando laboratorios…" rows={5} /> : <>
      <section className="reference-source" aria-label="Fuente de referencia">
        <h3>Una sola fuente congelada</h3>
        <p>{catalog.reference_history.draws.toLocaleString("es-DO")} sorteos · {catalog.reference_history.first_label ?? "—"} – {catalog.reference_history.last_label ?? "—"}</p>
        <p className="reference-sha"><span>SHA-256</span> {catalog.reference_history.sha256}</p>
      </section>
      <div className="reference-catalog" aria-label="Catálogo de laboratorios">
        {catalog.items.map((lab) => <Link className="reference-lab-link" key={lab.lab_id} to={`/laboratorios/${encodeURIComponent(lab.lab_id)}`}>
          <span className="reference-lab-name">{labTitle(lab)}</span>
          <span className="reference-lab-meta">{lab.lab_id} · cobertura {lab.coverage}/50 · {lab.selection_kind === "parity" ? "paridad" : "ranking"}</span>
          <span className="reference-lab-open" aria-hidden="true">Abrir →</span>
        </Link>)}
      </div>
      <p className="reference-count">{catalog.items.length} laboratorios disponibles · cada nombre abre su página independiente.</p>
    </>}
  </section>;
}
