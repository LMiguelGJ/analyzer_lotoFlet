import type { Catalog, SelectorKind, StakingStyle } from "../api/types";
import type { Errors, StrategyDraft } from "../pages/new-experiment/model";
import { errorDetail, errorMessage } from "../pages/new-experiment/model";

const control = "h-control w-full rounded-control border border-border-control bg-field px-3 font-mono text-sm text-text";
const help = "mt-1 text-sm text-text-secondary";

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
    return <div className="mb-5" key={key}>
      <label htmlFor={`${prefix}.${key}`} className="mb-1 block font-mono text-sm">{label}</label>
      {node}
      {description && <p className={help}>{description}</p>}
      {entry && <p id={`${prefix}.${key}.error`} className="mt-1 text-sm text-red-300">{errorMessage(entry)}</p>}
      {errorDetail(entry) && <p className="mt-1 text-xs text-text-secondary">{errorDetail(entry)}</p>}
    </div>;
  }
  function attributes(key: string) {
    const id = `${prefix}.${key}`;
    return { id, "aria-invalid": !!errors[id], "aria-describedby": errors[id] ? `${id}.error` : undefined } as const;
  }
  const systems = Object.entries(catalog.systems);
  const systemOptions = <><option value="">Elegí un sistema</option>{systems.map(([key, label]) => <option value={key} key={key}>{label}</option>)}</>;
  return <div>
    {field("name", `Nombre de la configuración ${index + 1}`, <input {...attributes("name")} className={control} value={value.name} maxLength={81} onChange={(event) => onChange({ ...value, name: event.target.value })} />)}
    {field("selector", `Método de la configuración ${index + 1}`, <select {...attributes("selector")} className={control} value={value.selector} onChange={(event) => onChange({ ...value, selector: event.target.value as SelectorKind, coverage: event.target.value === "parity" ? String(catalog.parity_coverage) : value.selector === "parity" ? String(catalog.coverages[0]) : value.coverage })}>
      {catalog.selectors.map((selector) => <option value={selector} key={selector}>{({ system: "Sistema individual", blend: "Mezcla personalizada", random: "Azar reproducible", parity: "Par/impar" })[selector]}</option>)}
    </select>)}
    {value.selector === "system" && field("system", "Sistema de ranking", <select {...attributes("system")} className={control} value={value.system} onChange={(event) => onChange({ ...value, system: event.target.value })}>{systemOptions}</select>)}
    {value.selector === "blend" && <section aria-label="Sistemas de la mezcla" className="mb-5 border-t border-border pt-4">
      <p className={help}>Cada ranking otorga 100 puntos al primer puesto hasta 1 al último. Los porcentajes ponderan puntos, no son probabilidades; los empates priorizan el número menor.</p>
      {value.components.map((component, componentIndex) => <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_120px_auto]" key={componentIndex}>
        {errors[`${prefix}.components.${componentIndex}`] && <p id={`${prefix}.components.${componentIndex}.error`} className="text-sm text-red-300 sm:col-span-3">{errorMessage(errors[`${prefix}.components.${componentIndex}`])}{errorDetail(errors[`${prefix}.components.${componentIndex}`]) && <span className="ml-2 text-xs text-text-secondary">{errorDetail(errors[`${prefix}.components.${componentIndex}`])}</span>}</p>}
        <div><label htmlFor={`${prefix}.components.${componentIndex}.system`} className="mb-1 block font-mono text-sm">Sistema {componentIndex + 1}</label>
          <select id={`${prefix}.components.${componentIndex}.system`} className={control} aria-invalid={!!(errors[`${prefix}.components.${componentIndex}.system`] || errors[`${prefix}.components.${componentIndex}`])} aria-describedby={errors[`${prefix}.components.${componentIndex}`] ? `${prefix}.components.${componentIndex}.error` : errors[`${prefix}.components.${componentIndex}.system`] ? `${prefix}.components.${componentIndex}.system.error` : undefined} value={component.system} onChange={(event) => onChange({ ...value, components: value.components.map((item, i) => i === componentIndex ? { ...item, system: event.target.value } : item) })}>{systemOptions}</select>
          {errors[`${prefix}.components.${componentIndex}.system`] && <p className="text-sm text-red-300">{errorMessage(errors[`${prefix}.components.${componentIndex}.system`])}</p>}
          {errorDetail(errors[`${prefix}.components.${componentIndex}.system`]) && <p className="text-xs text-text-secondary">{errorDetail(errors[`${prefix}.components.${componentIndex}.system`])}</p>}</div>
        <div><label htmlFor={`${prefix}.components.${componentIndex}.weight`} className="mb-1 block font-mono text-sm">Peso {componentIndex + 1} (%)</label>
          <input id={`${prefix}.components.${componentIndex}.weight`} className={control} inputMode="numeric" aria-invalid={!!errors[`${prefix}.components.${componentIndex}.weight`]} value={component.weight} onChange={(event) => onChange({ ...value, components: value.components.map((item, i) => i === componentIndex ? { ...item, weight: event.target.value } : item) })} />
          {errors[`${prefix}.components.${componentIndex}.weight`] && <p className="text-sm text-red-300">{errorMessage(errors[`${prefix}.components.${componentIndex}.weight`])}</p>}
          {errorDetail(errors[`${prefix}.components.${componentIndex}.weight`]) && <p className="text-xs text-text-secondary">{errorDetail(errors[`${prefix}.components.${componentIndex}.weight`])}</p>}</div>
        {value.components.length > 2 && <button type="button" className="self-end font-mono text-sm text-accent" onClick={() => onChange({ ...value, components: value.components.filter((_, i) => i !== componentIndex) })}>Quitar sistema {componentIndex + 1}</button>}
      </div>)}
      {errors[`${prefix}.components`] && <p className="mt-2 text-sm text-red-300">{errorMessage(errors[`${prefix}.components`])}</p>}
      {errorDetail(errors[`${prefix}.components`]) && <p className="mt-1 text-xs text-text-secondary">{errorDetail(errors[`${prefix}.components`])}</p>}
      <button type="button" disabled={value.components.length >= Math.min(13, systems.length)} className="mt-4 font-mono text-sm text-accent disabled:text-text-secondary" onClick={() => onChange({ ...value, components: [...value.components, { system: "", weight: "" }] })}>Agregar sistema</button>
    </section>}
    {value.selector === "parity" ? <p className="mb-5 text-sm text-text-secondary">Par/impar utiliza siempre 50 números; no selecciona subconjuntos.</p> : field("coverage", `Cobertura de la configuración ${index + 1}`, <select {...attributes("coverage")} className={control} value={value.coverage} onChange={(event) => onChange({ ...value, coverage: event.target.value })}>{catalog.coverages.map((coverage) => <option value={coverage} key={coverage}>{coverage} números</option>)}</select>, "Cantidad de números seleccionados en cada sorteo con ranking.")}
    {field("staking", `Tipo de apuesta de la configuración ${index + 1}`, <select {...attributes("staking")} className={control} value={value.staking} onChange={(event) => onChange({ ...value, staking: event.target.value as StakingStyle })}>
      <option value="flat">Plana</option><option value="ladder">Escalera</option><option value="bold">Audaz</option>
    </select>, ({ flat: "Plana: importe base constante por número.", ladder: "Escalera: ajusta la apuesta según la secuencia histórica.", bold: "Audaz: apuesta más agresiva según la regla del motor." })[value.staking])}
  </div>;
}
