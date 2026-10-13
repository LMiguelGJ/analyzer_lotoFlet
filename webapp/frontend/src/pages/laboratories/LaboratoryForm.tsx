import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, NetworkError } from "../../api/client";
import { createLaboratory } from "../../api/laboratories";
import type { LaboratoryDefinition } from "../../api/laboratories";
import { Button, Field } from "../../components/ui/Controls";
import { DEFAULT_FORM, PRIZE_FIELDS, STAKE_STYLES, SYSTEMS, parseLaboratoryForm } from "./form-model";
import type { FormErrors, FormField, FormValues } from "./form-model";

function failureText(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof NetworkError) return "No se pudo contactar al servidor local. Verificá la lista antes de intentar de nuevo.";
  return "No se pudo crear el laboratorio.";
}

interface Props { onCreated: (definition: LaboratoryDefinition) => void }

export function LaboratoryForm({ onCreated }: Props) {
  const [values, setValues] = useState<FormValues>(DEFAULT_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (field: FormField) => (value: string) => setValues((current) => ({ ...current, [field]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    const parsed = parseLaboratoryForm(values);
    if (!parsed.ok) { setErrors(parsed.errors); setFailure(null); return; }
    setErrors({}); setFailure(null); setSaving(true);
    try {
      onCreated(await createLaboratory(parsed.value.name, parsed.value.config));
    } catch (error) {
      setFailure(failureText(error));
    } finally { setSaving(false); }
  }

  return <form className="lab-form" onSubmit={(event) => void submit(event)} noValidate aria-labelledby="lab-form-title">
    <header className="reference-heading"><div><h2 id="lab-form-title">Nuevo laboratorio</h2><p>Definí las reglas una vez; quedan fijas y cada ejecución las reproduce sobre la fuente histórica congelada.</p></div></header>
    <Field id="lab-name" label="Nombre" value={values.name} onChange={(event) => set("name")(event.target.value)} error={errors.name} hint="Único; hasta 120 bytes." autoComplete="off" />
    <div className="lab-form-row">
      <div className="ledger-field"><label className="ledger-label" htmlFor="lab-system">Sistema de selección</label>
        <select id="lab-system" className="ledger-control" value={values.system} onChange={(event) => set("system")(event.target.value)}>{SYSTEMS.map((system) => <option key={system.value} value={system.value}>{system.label}</option>)}</select></div>
      <div className="ledger-field"><label className="ledger-label" htmlFor="lab-stake">Estilo de apuesta</label>
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
