import { useEffect, useRef } from "react";
import type { Catalog, SelectorKind, StakingStyle } from "../api/types";
import type { Errors, StrategyDraft } from "../pages/new-experiment/model";
import { errorDetail, errorMessage } from "../pages/new-experiment/model";
import { FIELD_LABEL_STAKING, SELECTOR_LABELS, STAKING_DESCRIPTIONS, STAKING_LABELS } from "../lib/ui-labels";
import { Block, Disclosure } from "./ui";

interface Props {
  value: StrategyDraft;
  index: number;
  catalog: Catalog;
  errors: Errors;
  onChange: (value: StrategyDraft) => void;
  progressiveDisclosure?: boolean;
}

/** Shared editor for the wizard and the LW13 configuration library. No financial rules live here. */
export function StrategyEditor({ value, index, catalog, errors, onChange, progressiveDisclosure = false }: Props) {
  const prefix = `strategies.${index}`;
  function field(key: string, label: string, node: React.ReactNode, description?: string) {
    const entry = errors[`${prefix}.${key}`];
    return <div className="field" key={key}>
      <label htmlFor={`${prefix}.${key}`} className="field-label">{label}</label>
      {node}
      {description && <p id={`${prefix}.${key}.help`} className="field-help">{description}</p>}
      {entry && <p id={`${prefix}.${key}.error`} className="mt-1 text-sm text-red-300">{errorMessage(entry)}</p>}
      {errorDetail(entry) && <Disclosure summary="Detalles técnicos"><p className="mt-1 text-xs text-text-secondary">{errorDetail(entry)}</p></Disclosure>}
    </div>;
  }
  function attributes(key: string, hasHelp = false) {
    const id = `${prefix}.${key}`;
    const description = [hasHelp && `${id}.help`, errors[id] && `${id}.error`].filter(Boolean).join(" ");
    return { id, "aria-invalid": !!errors[id], "aria-describedby": description || undefined } as const;
  }
  const systems = Object.entries(catalog.systems);
  const systemOptions = <><option value="">Elegí un sistema</option>{systems.map(([key, label]) => <option value={key} key={key}>{label}</option>)}</>;
  const advancedRef = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (!progressiveDisclosure) return;
    if (Object.keys(errors).some((key) => key.startsWith(`${prefix}.`) && key !== `${prefix}.name` && key !== `${prefix}.selector`)) {
      if (advancedRef.current) advancedRef.current.open = true;
    }
  }, [errors, prefix, progressiveDisclosure]);
  const advancedFields = <>
    {value.selector === "system" && field("system", "Método de selección", <select {...attributes("system")} aria-label="Sistema de ranking" className="control" value={value.system} onChange={(event) => onChange({ ...value, system: event.target.value })}>{systemOptions}</select>)}
    {value.selector === "blend" && <section aria-label="Sistemas de la mezcla" className="mb-5 border-t border-border pt-4">
      <Disclosure summary="Detalles técnicos"><p className="field-help">Cada clasificación otorga 100 puntos al primer puesto hasta 1 al último. Los porcentajes ponderan puntos, no son probabilidades; los empates priorizan el número menor.</p></Disclosure>
      {value.components.map((component, componentIndex) => {
        const componentKey = `${prefix}.components.${componentIndex}`;
        const systemError = errors[`${componentKey}.system`];
        const weightError = errors[`${componentKey}.weight`];
        const componentError = errors[componentKey];
        return <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_120px_auto]" key={componentIndex}>
          {componentError && <p id={`${componentKey}.error`} className="text-sm text-red-300 sm:col-span-3">{errorMessage(componentError)}{errorDetail(componentError) && <span className="ml-2 text-xs text-text-secondary">{errorDetail(componentError)}</span>}</p>}
          <div><label htmlFor={`${componentKey}.system`} className="field-label">Sistema {componentIndex + 1}</label>
            <select id={`${componentKey}.system`} className="control" aria-invalid={!!(systemError || componentError)} aria-describedby={[componentError && `${componentKey}.error`, systemError && `${componentKey}.system.error`].filter(Boolean).join(" ") || undefined} value={component.system} onChange={(event) => onChange({ ...value, components: value.components.map((item, i) => i === componentIndex ? { ...item, system: event.target.value } : item) })}>{systemOptions}</select>
            {systemError && <p id={`${componentKey}.system.error`} className="text-sm text-red-300">{errorMessage(systemError)}</p>}
            {errorDetail(systemError) && <p className="text-xs text-text-secondary">{errorDetail(systemError)}</p>}</div>
          <div><label htmlFor={`${componentKey}.weight`} className="field-label">Peso {componentIndex + 1} (%)</label>
            <input id={`${componentKey}.weight`} className="control" inputMode="numeric" aria-invalid={!!weightError} aria-describedby={[`${componentKey}.weight.help`, weightError && `${componentKey}.weight.error`].filter(Boolean).join(" ")} value={component.weight} onChange={(event) => onChange({ ...value, components: value.components.map((item, i) => i === componentIndex ? { ...item, weight: event.target.value } : item) })} />
            <p id={`${componentKey}.weight.help`} className="field-help">Porcentaje que aporta este sistema a la mezcla.</p>
            {weightError && <p id={`${componentKey}.weight.error`} className="text-sm text-red-300">{errorMessage(weightError)}</p>}
            {errorDetail(weightError) && <p className="text-xs text-text-secondary">{errorDetail(weightError)}</p>}</div>
          {value.components.length > 2 && <button type="button" className="min-h-12 self-end px-2 text-sm text-accent" onClick={() => onChange({ ...value, components: value.components.filter((_, i) => i !== componentIndex) })}>Quitar sistema {componentIndex + 1}</button>}
        </div>;
      })}
      {errors[`${prefix}.components`] && <p id={`${prefix}.components.error`} className="mt-2 text-sm text-red-300">{errorMessage(errors[`${prefix}.components`])}</p>}
      {errorDetail(errors[`${prefix}.components`]) && <p className="mt-1 text-xs text-text-secondary">{errorDetail(errors[`${prefix}.components`])}</p>}
      <button type="button" disabled={value.components.length >= Math.min(13, systems.length)} className="mt-4 min-h-12 px-2 text-sm text-accent disabled:text-text-secondary" onClick={() => onChange({ ...value, components: [...value.components, { system: "", weight: "" }] })}>Agregar sistema</button>
    </section>}
    {/* Coverage and staking are the two closing decisions for this configuration; pairing
        them side by side at sm+ keeps the block scannable without reordering the fields
        above, which stay in their original document order. */}
    <div className="sm:grid sm:grid-cols-2 sm:gap-x-4">
      {value.selector === "parity" ? <div className="field"><p className="field-help">Par/impar utiliza siempre 50 números; no selecciona subconjuntos.</p></div> : field("coverage", `Cobertura de la estrategia ${index + 1}`, <select {...attributes("coverage", true)} className="control" value={value.coverage} onChange={(event) => onChange({ ...value, coverage: event.target.value })}>{catalog.coverages.map((coverage) => <option value={coverage} key={coverage}>{coverage} números</option>)}</select>, "Cantidad de números seleccionados en cada sorteo con ranking.")}
      {field("staking", FIELD_LABEL_STAKING, <select {...attributes("staking", true)} className="control" value={value.staking} onChange={(event) => onChange({ ...value, staking: event.target.value as StakingStyle })}>
        {(Object.keys(STAKING_LABELS) as StakingStyle[]).map((key) => <option value={key} key={key}>{STAKING_LABELS[key]}</option>)}
      </select>, STAKING_DESCRIPTIONS[value.staking])}
    </div>
  </>;
  return <Block className="space-y-4">
    {field("name", `Nombre de la estrategia ${index + 1}`, <input {...attributes("name")} className="control" value={value.name} maxLength={81} onChange={(event) => onChange({ ...value, name: event.target.value })} />)}
    {field("selector", `Método de la estrategia ${index + 1}`, <select {...attributes("selector")} className="control" value={value.selector} onChange={(event) => onChange({ ...value, selector: event.target.value as SelectorKind, coverage: event.target.value === "parity" ? String(catalog.parity_coverage) : value.selector === "parity" ? String(catalog.coverages[0]) : value.coverage })}>
      {catalog.selectors.map((selector) => <option value={selector} key={selector}>{SELECTOR_LABELS[selector]}</option>)}
    </select>)}
    {progressiveDisclosure ? <details ref={advancedRef} className="strategy-advanced"><summary className="disclosure-summary">Avanzado</summary><div className="space-y-4 pt-2">{advancedFields}</div></details> : advancedFields}
  </Block>;
}
