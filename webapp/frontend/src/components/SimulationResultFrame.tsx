import type { ReactNode } from "react";
import type { SimulationResultViewModel } from "../lib/simulation-result-model";

export function SimulationResultFrame({ model, children, className, statusDisplay }: {
  model: SimulationResultViewModel | null;
  children: ReactNode;
  className?: string;
  statusDisplay?: ReactNode;
}) {
  if (!model) return <>{children}</>;
  return <section className={`simulation-result-frame ${className ?? ""}`} aria-label={model.title} data-result-family={model.family}>
    <header className="simulation-result-heading">
      <div className="simulation-result-title-row">
        <h2>{model.title}</h2>
        <span className="simulation-result-status">{statusDisplay ?? model.status}</span>
      </div>
      <p className="simulation-result-source">{model.source}</p>
    </header>
    <div aria-label={`Secciones: ${model.sections.join(", ")}`} className="simulation-result-content">{children}</div>
  </section>;
}
