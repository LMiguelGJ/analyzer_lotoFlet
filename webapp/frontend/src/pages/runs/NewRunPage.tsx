import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, NetworkError } from "../../api/client";
import { createRun } from "../../api/runs";
import { getHistory } from "../../api/history";
import { getRunOptions, getRun } from "../../api/runs";
import type { HistorySnapshot, RunOptions, RunReport } from "../../api/types";
import { formatNumber, formatSignedDOP } from "../../lib/format";
import { Button } from "../../components/ui/Controls";
import { Loading } from "../../components/ui/Feedback";
import { createInitialRunForm, formatStrategyLabel, parseIntegerInput, resizePrizes, toCreateRunRequest, validateRunForm, type RunForm, type RunFormErrors } from "./run-model";
import "./runs.css";

function message(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.fieldErrors?.length) return `${error.detail} ${error.fieldErrors.map((item) => `${item.loc.slice(1).join(".")}: ${item.msg}`).join("; ")}`;
    return error.detail;
  }
  if (error instanceof NetworkError) return "No se obtuvo respuesta del servidor. La corrida pudo haberse guardado; revisá la lista antes de volver a enviarla.";
  if (error instanceof Error && error.message) return error.message;
  return "No se pudo contactar al servidor local. Revisá la conexión.";
}
function snapshotDate(snapshot: HistorySnapshot) { return `${snapshot.first_label} – ${snapshot.last_label}`; }

export function NewRunPage() {
  const [search] = useSearchParams();
  const baseId = search.get("base");
  const navigate = useNavigate();
  const [options, setOptions] = useState<RunOptions | null>(null);
  const [snapshots, setSnapshots] = useState<HistorySnapshot[]>([]);
  const [form, setForm] = useState<RunForm | null>(null);
  const [base, setBase] = useState<RunReport | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [errors, setErrors] = useState<RunFormErrors>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController(); let current = true;
    setLoading(true); setLoadError(null);
    Promise.all([getRunOptions({ signal: controller.signal }), getHistory({ signal: controller.signal })]).then(async ([loadedOptions, history]) => {
      let loadedBase: RunReport | undefined;
      if (baseId) loadedBase = await getRun(baseId, { signal: controller.signal });
      if (!current) return;
      const sources = [...history.sources, history.active].filter((item, index, all) => all.findIndex((candidate) => candidate.sha256 === item.sha256) === index);
      const pinnedSha = loadedBase?.config.history.sha256;
      if (pinnedSha && !sources.some((item) => item.sha256 === pinnedSha)) throw new Error("No encontramos metadatos para el historial fijado en esta corrida; no se cargarán valores sustitutos.");
      setOptions(loadedOptions); setSnapshots(sources); setBase(loadedBase ?? null);
      setForm(createInitialRunForm(loadedOptions, loadedBase));
    }).catch((error: unknown) => { if (current && !(error instanceof Error && error.name === "AbortError")) setLoadError(message(error)); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [baseId, revision]);

  const selectedSnapshot = useMemo(() => snapshots.find((item) => item.sha256 === form?.historySha), [snapshots, form?.historySha]);
  const update = (patch: Partial<RunForm>) => setForm((current) => current ? { ...current, ...patch } : current);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form || !options || pending) return;
    const checked = validateRunForm(form, options); setErrors(checked.errors); setApiError(null); setUncertain(false);
    if (!checked.valid) {
      const first = Object.keys(checked.errors)[0];
      const focusId: Record<string, string> = { prizes: "run-prize-1", components: "run-strategy-mix", maxDraws: "run-maxDraws" };
      document.getElementById(focusId[first] ?? `run-${first}`)?.focus();
      return;
    }
    setPending(true);
    try {
      const created = await createRun(toCreateRunRequest(form, options));
      navigate(`/corridas/${encodeURIComponent(created.id)}`);
    } catch (error) {
      setApiError(message(error)); setUncertain(error instanceof NetworkError);
    } finally { setPending(false); }
  }

  if (loading) return <section className="runs-page"><h2>Nueva corrida</h2><Loading label={baseId ? "Cargando opciones y corrida de origen…" : "Cargando opciones del historial…"} rows={5} /></section>;
  if (loadError || !form || !options) return <section className="runs-page"><h2>Nueva corrida</h2><div className="runs-inline-error" role="alert"><p>{baseId ? "No se pudo cargar la corrida de origen; el formulario no se completó con valores predeterminados." : "No se pudieron cargar las opciones reales del servidor."}</p><p>{loadError ?? "Respuesta incompleta."}</p><Button onClick={() => setRevision((value) => value + 1)}>Reintentar</Button><Link className="link" to="/corridas">Volver a Corridas</Link></div></section>;

  const cost = (parseIntegerInput(form.coverage) ?? 0) * (parseIntegerInput(form.minimumStake) ?? 0);
  const windowLabel = `${form.startDate || selectedSnapshot?.first_label || "Inicio del historial"} – ${form.endDate || selectedSnapshot?.last_label || "Fin del historial"}`;
  const visibleErrors = Object.values(errors).filter(Boolean);
  const fieldError = (key: keyof RunForm) => errors[key];
  return <section className="runs-page" aria-labelledby="new-run-title">
    <header className="runs-heading"><div><h2 id="new-run-title">{base ? "Repetir con cambios" : "Nueva corrida"}</h2><p>{base ? `Copia editable de ${base.name}; la original no se modifica.` : "Definí las reglas de una prueba sobre el historial."}</p></div><Link className="link" to="/corridas">Volver a Corridas</Link></header>
    {apiError && <div className="runs-inline-error" role="alert"><p>{apiError}</p>{uncertain && <p>No la reenviaremos automáticamente. Consultá Corridas para comprobar si quedó guardada antes de iniciar otra.</p>}</div>}
    {visibleErrors.length > 0 && <div className="runs-inline-error" role="alert" aria-live="polite"><strong>Revisá estos datos:</strong><ul>{visibleErrors.map((error) => <li key={error}>{error}</li>)}</ul></div>}
    <form className="runs-form" noValidate onSubmit={(event) => void submit(event)}>
      <fieldset className="runs-block" disabled={pending}><legend>Reglas</legend><div className="runs-fields-grid">
        <label className="runs-field"><span>Nombre <small>(opcional)</small></span><input id="run-name" type="text" maxLength={options.limits.name} value={form.name} onChange={(e) => update({ name: e.target.value })} aria-invalid={!!fieldError("name")} aria-describedby={fieldError("name") ? "run-name-error" : undefined} />{fieldError("name") && <small id="run-name-error" className="runs-field-error">{fieldError("name")}</small>}</label>
        <label className="runs-field"><span>Posiciones (1–5)</span><select id="run-positions" value={form.positions} onChange={(e) => { const count = Number(e.target.value); update({ positions: e.target.value, prizes: resizePrizes(form.prizes, count) }); }} aria-invalid={!!fieldError("positions")} aria-describedby={fieldError("positions") ? "run-positions-error" : undefined}>{[1,2,3,4,5].map((n) => <option key={n} value={n}>{n}</option>)}</select>{fieldError("positions") && <small id="run-positions-error" className="runs-field-error">{fieldError("positions")}</small>}</label>
        <label className="runs-field"><span>Apuesta mínima (RD$)</span><input id="run-minimumStake" inputMode="numeric" value={form.minimumStake} onChange={(e) => update({ minimumStake: e.target.value })} aria-invalid={!!fieldError("minimumStake")} aria-describedby={fieldError("minimumStake") ? "run-minimumStake-error" : undefined} />{fieldError("minimumStake") && <small id="run-minimumStake-error" className="runs-field-error">{fieldError("minimumStake")}</small>}</label>
        <div className="runs-fixed-note"><strong>Números:</strong> 00–99. Se permiten repeticiones.</div>
      </div><div className="runs-prizes"><p className="runs-label">Premio por posición (RD$)</p>{form.prizes.slice(0, Number(form.positions)).map((prize, index) => <label className="runs-field" key={index}><span>Posición {index + 1}</span><input id={`run-prize-${index + 1}`} aria-label={`Premio posición ${index + 1}`} inputMode="numeric" value={prize} onChange={(e) => update({ prizes: form.prizes.map((item, i) => i === index ? e.target.value : item) })} aria-invalid={!!fieldError("prizes")} aria-describedby={fieldError("prizes") ? "run-prizes-error" : undefined} />{index === 0 && fieldError("prizes") && <small id="run-prizes-error" className="runs-field-error">{fieldError("prizes")}</small>}</label>)}</div>
      </fieldset>
      <fieldset className="runs-block" disabled={pending}><legend>Estrategia</legend><div className="runs-choice-row"><label><input type="radio" name="kind" checked={form.kind === "mix"} onChange={() => update({ kind: "mix" })} /> Mezcla de rankings</label><label><input type="radio" name="kind" checked={form.kind === "parity"} onChange={() => update({ kind: "parity" })} /> Paridad</label></div>
        {form.kind === "mix" && <div id="run-strategy-mix" className="runs-components" tabIndex={-1}><div className="runs-component-list">{form.components.map((part, index) => <div className="runs-component" key={`${index}-${part.system}`}><label className="runs-field"><span>Sistema</span><select aria-label={`Sistema ${index + 1}`} value={part.system} onChange={(e) => update({ components: form.components.map((item, i) => i === index ? { ...item, system: e.target.value } : item) })}>{!options.systems.some((system) => system.id === part.system) && <option value={part.system}>Sistema no disponible</option>}{options.systems.filter((system) => system.id === part.system || !form.components.some((other, i) => i !== index && other.system === system.id)).map((system) => <option key={system.id} value={system.id}>{system.label}</option>)}</select></label><label className="runs-field"><span>Porcentaje</span><input aria-label={`Porcentaje ${index + 1}`} inputMode="numeric" value={part.percent} onChange={(e) => update({ components: form.components.map((item, i) => i === index ? { ...item, percent: e.target.value } : item) })} /></label><Button variant="secondary" disabled={form.components.length <= 1} onClick={() => update({ components: form.components.filter((_, i) => i !== index) })}>Quitar sistema</Button></div>)}</div>
          <p className="runs-percent-total" aria-live="polite">Total: {form.components.reduce((sum, item) => sum + (parseIntegerInput(item.percent) ?? 0), 0)} %</p>{fieldError("components") && <small className="runs-field-error">{fieldError("components")}</small>}
          <Button variant="secondary" disabled={form.components.length >= 13 || form.components.length >= options.systems.length} onClick={() => { const next = options.systems.find((system) => !form.components.some((item) => item.system === system.id)); if (next) update({ components: [...form.components, { system: next.id, percent: "1" }] }); }}>Agregar sistema</Button></div>}
        <label className="runs-field runs-coverage"><span>Cobertura (1–50 números)</span><input id="run-coverage" inputMode="numeric" value={form.coverage} onChange={(e) => update({ coverage: e.target.value })} aria-invalid={!!fieldError("coverage")} aria-describedby={fieldError("coverage") ? "run-coverage-error" : undefined} />{fieldError("coverage") && <small id="run-coverage-error" className="runs-field-error">{fieldError("coverage")}</small>}</label>
      </fieldset>
      <fieldset className="runs-block" disabled={pending}><legend>Condiciones</legend><div className="runs-fields-grid"><label className="runs-field"><span>Capital (RD$)</span><input id="run-capital" inputMode="numeric" value={form.capital} onChange={(e) => update({ capital: e.target.value })} aria-invalid={!!fieldError("capital")} aria-describedby={fieldError("capital") ? "run-capital-error" : undefined} />{fieldError("capital") && <small id="run-capital-error" className="runs-field-error">{fieldError("capital")}</small>}</label><label className="runs-field"><span>Meta (RD$)</span><input id="run-goal" inputMode="numeric" value={form.goal} onChange={(e) => update({ goal: e.target.value })} aria-invalid={!!fieldError("goal")} aria-describedby={fieldError("goal") ? "run-goal-error" : undefined} />{fieldError("goal") && <small id="run-goal-error" className="runs-field-error">{fieldError("goal")}</small>}</label><label className="runs-field"><span>Duración máxima (sorteos, opcional)</span><input id="run-maxDraws" inputMode="numeric" value={form.maxDraws} onChange={(e) => update({ maxDraws: e.target.value })} aria-invalid={!!fieldError("maxDraws")} aria-describedby={fieldError("maxDraws") ? "run-maxDraws-error" : undefined} />{fieldError("maxDraws") && <small id="run-maxDraws-error" className="runs-field-error">{fieldError("maxDraws")}</small>}</label></div></fieldset>
      <fieldset className="runs-block" disabled={pending}><legend>Alcance</legend><div className="runs-fields-grid"><label className="runs-field"><span>Historial usado</span><select value={form.historySha ?? ""} onChange={(e) => update({ historySha: e.target.value || null })}>{snapshots.map((snapshot) => <option key={snapshot.sha256} value={snapshot.sha256}>{snapshot.origin === "frozen" ? "Congelado" : "Importado"} · {snapshot.sha256.slice(0, 12)}…</option>)}</select></label><label className="runs-field"><span>Desde (inclusive)</span><input id="run-startDate" type="date" value={form.startDate} onChange={(e) => update({ startDate: e.target.value })} aria-invalid={!!fieldError("startDate")} aria-describedby={fieldError("startDate") ? "run-startDate-error" : undefined} />{fieldError("startDate") && <small id="run-startDate-error" className="runs-field-error">{fieldError("startDate")}</small>}</label><label className="runs-field"><span>Hasta (inclusive)</span><input id="run-endDate" type="date" value={form.endDate} onChange={(e) => update({ endDate: e.target.value })} aria-invalid={!!fieldError("endDate")} aria-describedby={fieldError("endDate") ? "run-endDate-error" : undefined} />{fieldError("endDate") && <small id="run-endDate-error" className="runs-field-error">{fieldError("endDate")}</small>}</label></div>
        {selectedSnapshot && <div className="runs-history-meta"><p><strong>Origen:</strong> {selectedSnapshot.origin === "frozen" ? "Historial congelado" : "Historial importado"} · {selectedSnapshot.active ? "activo" : "fijado"} · {snapshotDate(selectedSnapshot)}</p><p><strong>SHA-256:</strong> <span className="runs-sha">{selectedSnapshot.sha256}</span></p><p><strong>Sorteos totales:</strong> {formatNumber(selectedSnapshot.draws)} · <strong>con ranking:</strong> {formatNumber(selectedSnapshot.ranked_draws)}</p>{selectedSnapshot.origin === "frozen" && <p>Los rankings del historial congelado están disponibles desde 2025-09-02; el conteo mostrado corresponde al historial completo, no necesariamente a esta ventana.</p>}</div>}
      </fieldset>
      <section className="runs-block runs-summary" aria-labelledby="run-summary-title"><h3 id="run-summary-title">Resumen</h3><dl><div><dt>Costo por apuesta</dt><dd>{formatSignedDOP(cost)}</dd></div><div><dt>Capital / meta</dt><dd>{formatSignedDOP(parseIntegerInput(form.capital) ?? 0)} / {formatSignedDOP(parseIntegerInput(form.goal) ?? 0)}</dd></div><div><dt>Estrategia</dt><dd>{formatStrategyLabel({ kind: form.kind, components: form.kind === "mix" ? form.components.map(({ system, percent }) => ({ system, percent: parseIntegerInput(percent) ?? 0 })) : [], coverage: parseIntegerInput(form.coverage) ?? 0 }, options.systems)}</dd></div><div><dt>Ventana</dt><dd>{windowLabel}</dd></div><div><dt>Duración máxima</dt><dd>{form.maxDraws || "Sin límite"}</dd></div><div><dt>Premios</dt><dd>{form.prizes.slice(0, Number(form.positions)).join(" / ")} RD$</dd></div></dl><p className="runs-warning">Esto describe resultados del pasado. No es una predicción ni garantiza resultados futuros.</p></section>
      <div className="runs-submit"><Button type="submit" variant="primary" loading={pending}>{pending ? "Calculando…" : "Correr"}</Button><Link className="link" to="/corridas">Volver sin correr</Link></div>
    </form>
  </section>;
}
