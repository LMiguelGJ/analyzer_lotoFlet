import { useLayoutEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, NetworkError } from "../../api/client";
import { createLaboratory } from "../../api/laboratories";
import type { LaboratoryDefinition } from "../../api/laboratories";
import { Button, Field } from "../../components/ui/Controls";
import { DEFAULT_FORM, PRIZE_FIELDS, STAKE_STYLES, SYSTEMS, parseLaboratoryForm } from "./form-model";
import type { FormErrors, FormField, FormValues } from "./form-model";
import { LaboratoryOptionHelp } from "./LaboratoryOptionHelp";
import type { HelpKind } from "./option-help";

function failureText(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof NetworkError) return "No se pudo contactar al servidor local. Verificá la lista antes de intentar de nuevo.";
  return "No se pudo crear el laboratorio.";
}

interface Props { onCreated: (definition: LaboratoryDefinition) => void }

const FIELD_LABELS: Record<FormField, string> = {
  name: "Nombre", system: "Sistema de selección", stake_style: "Estilo de apuesta",
  coverage: "Cobertura (números)", capital: "Capital inicial", goal: "Meta de saldo",
  prize_1: "Premio 1.º", prize_2: "Premio 2.º", prize_3: "Premio 3.º", prize_4: "Premio 4.º", prize_5: "Premio 5.º",
  window_start: "Ventana: inicio", window_end: "Ventana: fin",
};
const FIELD_ORDER: FormField[] = ["name", "system", "stake_style", "coverage", "capital", "goal", ...PRIZE_FIELDS, "window_start", "window_end"];

function fieldId(field: FormField): string {
  if (field === "window_start") return "lab-window-start";
  if (field === "window_end") return "lab-window-end";
  return `lab-${field}`;
}

export function LaboratoryForm({ onCreated }: Props) {
  const [values, setValues] = useState<FormValues>(DEFAULT_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [help, setHelp] = useState<HelpKind | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const focusInvalid = useRef(false);

  useLayoutEffect(() => {
    if (!focusInvalid.current) return;
    focusInvalid.current = false;
    formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  }, [errors]);

  const set = (field: FormField) => (value: string) => setValues((current) => ({ ...current, [field]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    const parsed = parseLaboratoryForm(values);
    if (!parsed.ok) { focusInvalid.current = true; setErrors(parsed.errors); setFailure(null); return; }
    setErrors({}); setFailure(null); setSaving(true);
    try {
      onCreated(await createLaboratory(parsed.value.name, parsed.value.config));
    } catch (error) {
      setFailure(failureText(error));
    } finally { setSaving(false); }
  }

  return <form ref={formRef} className="lab-form" onSubmit={(event) => void submit(event)} noValidate aria-labelledby="lab-form-title">
    <header className="reference-heading"><div><h2 id="lab-form-title">Nuevo laboratorio</h2><p>Definí las reglas una vez; quedan fijas y cada ejecución las reproduce sobre la fuente histórica congelada.</p></div></header>
    {Object.keys(errors).length > 0 && <div className="reference-action-error lab-form-errors" role="alert">
      <p>Revisá los campos señalados.</p>
      <ul>{FIELD_ORDER.filter((field) => errors[field]).map((field) => <li key={field}>
        <a href={`#${fieldId(field)}`} onClick={(event) => { event.preventDefault(); formRef.current?.querySelector<HTMLElement>(`#${fieldId(field)}`)?.focus(); }}>{FIELD_LABELS[field]}</a>
      </li>)}</ul>
    </div>}
    <Field id="lab-name" label="Nombre" value={values.name} onChange={(event) => set("name")(event.target.value)} error={errors.name} hint="Único; hasta 120 bytes." autoComplete="off" />
    <div className="lab-form-row">
      <div className="ledger-field"><div className="lab-field-label"><label className="ledger-label" htmlFor="lab-system">Sistema de selección</label>
        <LaboratoryOptionHelp kind="system" value={values.system} open={help === "system"} onOpen={() => setHelp("system")} onClose={() => setHelp(null)} /></div>
        <select id="lab-system" className="ledger-control" value={values.system} onChange={(event) => set("system")(event.target.value)}>{SYSTEMS.map((system) => <option key={system.value} value={system.value}>{system.label}</option>)}</select></div>
      <div className="ledger-field"><div className="lab-field-label"><label className="ledger-label" htmlFor="lab-stake">Estilo de apuesta</label>
        <LaboratoryOptionHelp kind="stake_style" value={values.stake_style} open={help === "stake_style"} onOpen={() => setHelp("stake_style")} onClose={() => setHelp(null)} /></div>
        <select id="lab-stake" className="ledger-control" value={values.stake_style} onChange={(event) => set("stake_style")(event.target.value)}>{STAKE_STYLES.map((style) => <option key={style.value} value={style.value}>{style.label}</option>)}</select></div>
      <Field id="lab-coverage" label="Cobertura (números)" inputMode="numeric" value={values.coverage} onChange={(event) => set("coverage")(event.target.value)} error={errors.coverage} hint="De 1 a 50." />
    </div>
    <div className="lab-form-row">
      <Field id="lab-capital" label="Capital inicial" inputMode="numeric" value={values.capital} onChange={(event) => set("capital")(event.target.value)} error={errors.capital} />
      <Field id="lab-goal" label="Meta de saldo" inputMode="numeric" value={values.goal} onChange={(event) => set("goal")(event.target.value)} error={errors.goal} />
    </div>
    <fieldset className="lab-prizes"><legend className="ledger-label">Premios por posición</legend>
      <div className="lab-form-row lab-form-row-5">{PRIZE_FIELDS.map((field, index) => <Field key={field} id={`lab-${field}`} label={`${index + 1}.º`} inputMode="numeric" value={values[field]} onChange={(event) => set(field)(event.target.value)} error={errors[field]} />)}</div>
    </fieldset>
    <div className="lab-form-row">
      <Field id="lab-window-start" label="Ventana: inicio" value={values.window_start} onChange={(event) => set("window_start")(event.target.value)} error={errors.window_start} hint="AAAA-MM-DD HH:MM" />
      <Field id="lab-window-end" label="Ventana: fin" value={values.window_end} onChange={(event) => set("window_end")(event.target.value)} error={errors.window_end} hint="AAAA-MM-DD HH:MM" />
    </div>
    {failure && <div className="reference-action-error" role="alert"><p>{failure}</p></div>}
    <div className="reference-run-action"><Button type="submit" variant="primary" loading={saving}>Crear laboratorio</Button><span>No ejecuta nada: solo guarda las reglas.</span></div>
  </form>;
}
