import type { ReactNode } from "react";
import type { SimulationResultViewModel } from "../lib/simulation-result-model";

export function SimulationResultFrame({ model, children, className, statusDisplay }: {
  model: SimulationResultViewModel | null;
  children: ReactNode;
  className?: string;
  statusDisplay?: ReactNode;
}) {
  if (!model) return <>{children}</>;
  return <section className={className} aria-label={model.title} data-result-family={model.family}>
    <header className="border-b border-border pb-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-heading text-xl">{model.title}</h2>
        <span className="text-sm text-text-secondary">{statusDisplay ?? model.status}</span>
      </div>
      <p className="mt-2 break-all text-sm text-text-secondary">{model.source}</p>
    </header>
    <div aria-label={`Secciones: ${model.sections.join(", ")}`} className="pt-1">{children}</div>
  </section>;
}
