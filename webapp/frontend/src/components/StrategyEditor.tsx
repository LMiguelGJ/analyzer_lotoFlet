import type { Catalog, SelectorKind, StakingStyle } from "../api/types";
import type { Errors, StrategyDraft } from "../pages/new-experiment/model";
import { errorDetail, errorMessage } from "../pages/new-experiment/model";
import { FIELD_LABEL_STAKING, SELECTOR_LABELS, STAKING_DESCRIPTIONS, STAKING_LABELS } from "../lib/ui-labels";

interface Props {
  value: StrategyDraft;
  index: number;
  catalog: Catalog;
  errors: Errors;
  onChange: (value: StrategyDraft) => void;
}

/** Shared editor for the wizard and the LW13 configuration library. No financial rules live here. */
export function StrategyEditor({ value, index, catalog, errors, onChange }: Props) {
  const prefix = `strategies.${index}`;
  function field(key: string, label: string, node: React.ReactNode, description?: string) {
    const entry = errors[`${prefix}.${key}`];
    return <div className="field" key={key}>
      <label htmlFor={`${prefix}.${key}`} className="field-label">{label}</label>
      {node}
      {description && <p id={`${prefix}.${key}.help`} className="field-help">{description}</p>}
      {entry && <p id={`${prefix}.${key}.error`} className="mt-1 text-sm text-red-300">{errorMessage(entry)}</p>}
      {errorDetail(entry) && <p className="mt-1 text-xs text-text-secondary">{errorDetail(entry)}</p>}
    </div>;
  }
  function attributes(key: string, hasHelp = false) {
    const id = `${prefix}.${key}`;
    const description = [hasHelp && `${id}.help`, errors[id] && `${id}.error`].filter(Boolean).join(" ");
    return { id, "aria-invalid": !!errors[id], "aria-describedby": description || undefined } as const;
  }
  const systems = Object.entries(catalog.systems);
  const systemOptions = <><option value="">Elegí un sistema</option>{systems.map(([key, label]) => <option value={key} key={key}>{label}</option>)}</>;
  return <div>
    {field("name", `Nombre de la estrategia ${index + 1}`, <input {...attributes("name")} className="control" value={value.name} maxLength={81} onChange={(event) => onChange({ ...value, name: event.target.value })} />)}
    {field("selector", `Método de la estrategia ${index + 1}`, <select {...attributes("selector")} className="control" value={value.selector} onChange={(event) => onChange({ ...value, selector: event.target.value as SelectorKind, coverage: event.target.value === "parity" ? String(catalog.parity_coverage) : value.selector === "parity" ? String(catalog.coverages[0]) : value.coverage })}>
      {catalog.selectors.map((selector) => <option value={selector} key={selector}>{SELECTOR_LABELS[selector]}</option>)}
    </select>)}
    {value.selector === "system" && field("system", "Sistema de ranking", <select {...attributes("system")} className="control" value={value.system} onChange={(event) => onChange({ ...value, system: event.target.value })}>{systemOptions}</select>)}
    {value.selector === "blend" && <section aria-label="Sistemas de la mezcla" className="mb-5 border-t border-border pt-4">
      <p className="field-help">Cada ranking otorga 100 puntos al primer puesto hasta 1 al último. Los porcentajes ponderan puntos, no son probabilidades; los empates priorizan el número menor.</p>
      {value.components.map((component, componentIndex) => <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_120px_auto]" key={componentIndex}>
        {errors[`${prefix}.components.${componentIndex}`] && <p id={`${prefix}.components.${componentIndex}.error`} className="text-sm text-red-300 sm:col-span-3">{errorMessage(errors[`${prefix}.components.${componentIndex}`])}{errorDetail(errors[`${prefix}.components.${componentIndex}`]) && <span className="ml-2 text-xs text-text-secondary">{errorDetail(errors[`${prefix}.components.${componentIndex}`])}</span>}</p>}
        <div><label htmlFor={`${prefix}.components.${componentIndex}.system`} className="field-label">Sistema {componentIndex + 1}</label>
          <select id={`${prefix}.components.${componentIndex}.system`} className="control" aria-invalid={!!(errors[`${prefix}.components.${componentIndex}.system`] || errors[`${prefix}.components.${componentIndex}`])} aria-describedby={errors[`${prefix}.components.${componentIndex}`] ? `${prefix}.components.${componentIndex}.error` : errors[`${prefix}.components.${componentIndex}.system`] ? `${prefix}.components.${componentIndex}.system.error` : undefined} value={component.system} onChange={(event) => onChange({ ...value, components: value.components.map((item, i) => i === componentIndex ? { ...item, system: event.target.value } : item) })}>{systemOptions}</select>
          {errors[`${prefix}.components.${componentIndex}.system`] && <p className="text-sm text-red-300">{errorMessage(errors[`${prefix}.components.${componentIndex}.system`])}</p>}
          {errorDetail(errors[`${prefix}.components.${componentIndex}.system`]) && <p className="text-xs text-text-secondary">{errorDetail(errors[`${prefix}.components.${componentIndex}.system`])}</p>}</div>
        <div><label htmlFor={`${prefix}.components.${componentIndex}.weight`} className="field-label">Peso {componentIndex + 1} (%)</label>
          <input id={`${prefix}.components.${componentIndex}.weight`} className="control" inputMode="numeric" aria-invalid={!!errors[`${prefix}.components.${componentIndex}.weight`]} value={component.weight} onChange={(event) => onChange({ ...value, components: value.components.map((item, i) => i === componentIndex ? { ...item, weight: event.target.value } : item) })} />
          {errors[`${prefix}.components.${componentIndex}.weight`] && <p className="text-sm text-red-300">{errorMessage(errors[`${prefix}.components.${componentIndex}.weight`])}</p>}
          {errorDetail(errors[`${prefix}.components.${componentIndex}.weight`]) && <p className="text-xs text-text-secondary">{errorDetail(errors[`${prefix}.components.${componentIndex}.weight`])}</p>}</div>
        {value.components.length > 2 && <button type="button" className="self-end text-sm text-accent" onClick={() => onChange({ ...value, components: value.components.filter((_, i) => i !== componentIndex) })}>Quitar sistema {componentIndex + 1}</button>}
      </div>)}
      {errors[`${prefix}.components`] && <p className="mt-2 text-sm text-red-300">{errorMessage(errors[`${prefix}.components`])}</p>}
      {errorDetail(errors[`${prefix}.components`]) && <p className="mt-1 text-xs text-text-secondary">{errorDetail(errors[`${prefix}.components`])}</p>}
      <button type="button" disabled={value.components.length >= Math.min(13, systems.length)} className="mt-4 text-sm text-accent disabled:text-text-secondary" onClick={() => onChange({ ...value, components: [...value.components, { system: "", weight: "" }] })}>Agregar sistema</button>
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
  </div>;
}
