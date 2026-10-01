import { useEffect, useRef, useState } from "react";
import { Link, useBlocker, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { ApiFieldError } from "../../api/client";
import type { Catalog, ConfigurationSummary, Page } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { StrategyEditor } from "../../components/StrategyEditor";
import { buildRequest, buildStrategy, diffStrategyKey, draftFromRequest, draftFromStrategy, errorDetail, errorMessage, initialConditions, newStrategy, trimName, validateConditions, validateStrategies } from "./model";
import type { ConditionsDraft, Errors, StrategyDraft } from "./model";
import { FIELD_HELP_SEED, FIELD_LABEL_SEED, FIELD_LABEL_SETTLEMENT, SELECTOR_LABELS, SETTLEMENT_LABELS, STAKING_LABELS } from "../../lib/ui-labels";

const control = "control";
const secondary = "btn btn-secondary hover:bg-field disabled:opacity-50";
const primary = "btn btn-primary disabled:opacity-50";
const labels = ["Condiciones", "Estrategias", "Revisar"];
const money = (value: string) => {
  if (!value) return "—";
  // Never round an invalid draft in the summary; only bounded safe integers are formatted.
  return /^[0-9]+$/.test(value) && BigInt(value) <= BigInt(Number.MAX_SAFE_INTEGER)
    ? `RD$ ${Number(value).toLocaleString("es-DO")}` : `RD$ ${value}`;
};

/** Field-level errors map to their own field; a bare strategy loc (e.g. weights not
 * summing to 100) maps to that strategy's block; a bare conditions loc maps to the
 * conditions section; anything else falls back to the general notice. The server `msg`
 * is kept as secondary technical text instead of discarded. */
function serverErrors(entries: ApiFieldError[]): Errors {
  const errors: Errors = {};
  for (const entry of entries) {
    const loc = entry.loc.map(String);
    const root = loc.indexOf("request");
    const path = root < 0 ? loc : loc.slice(root + 1);
    if (root < 0) { errors.form = { message: "La solicitud fue rechazada; revisá los datos.", detail: entry.msg }; continue; }
    if (path[0] === "conditions") {
      if (path.length === 1) {
        errors.conditions = { message: "El servidor rechazó las condiciones comunes; revisá esta sección.", detail: entry.msg };
      } else {
        const key = path[1];
        errors[key] = { message: `El servidor rechazó ${key}; revisá este campo.`, detail: entry.msg };
      }
    } else if (path[0] === "strategies" && /^\d+$/.test(path[1] ?? "")) {
      const index = path[1];
      if (path.length === 2) {
        errors[`strategies.${index}`] = { message: "El servidor rechazó esta estrategia; revisá sus valores.", detail: entry.msg };
      } else {
        const field = path.slice(2).join(".");
        errors[`strategies.${index}.${field}`] = { message: "El servidor rechazó este campo; revisá el valor.", detail: entry.msg };
      }
    } else if (path[0] === "name" && path.length === 1) {
      errors.name = { message: "El servidor rechazó el nombre; revisá este campo.", detail: entry.msg };
    } else {
      errors.form = { message: "El servidor rechazó la solicitud; revisá los datos.", detail: entry.msg };
    }
  }
  return errors;
}

/** The first offending field's DOM id for a mapped server-error set, so focus can move
 * there directly; a block-level strategy error focuses that strategy's name field
 * (always rendered), and section-level/unknown errors fall back to no specific target. */
function firstFocusTarget(mapped: Errors): string | null {
  for (const key of Object.keys(mapped)) {
    if (key === "form" || key === "conditions") continue;
    if (/^strategies\.\d+$/.test(key)) return `${key}.name`;
    if (/^strategies\.\d+\.components$/.test(key)) return `${key}.0.weight`;
    if (/^strategies\.\d+\.components\.\d+$/.test(key)) return `${key}.system`;
    return key;
  }
  return null;
}

export function NewExperimentPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const baseId = searchParams.get("base") || null;
  const configurationId = searchParams.get("configuration") || null;
  const sourceKey = baseId ? `base:${baseId}` : configurationId ? `configuration:${configurationId}` : "";
  const previousSource = useRef(sourceKey);
  const [configurationState, setConfigurationState] = useState<"loading" | "ready" | "missing" | "network" | "invalid" | "error">(configurationId ? "loading" : "ready");
  const [configurationRetry, setConfigurationRetry] = useState(0);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryPage, setLibraryPage] = useState<Page<ConfigurationSummary> | null>(null);
  const [libraryOffset, setLibraryOffset] = useState(0);
  const [libraryRetry, setLibraryRetry] = useState(0);
  const [libraryError, setLibraryError] = useState("");
  const [libraryBusy, setLibraryBusy] = useState(false);
  const libraryRef = useRef(false);
  const [savingStrategy, setSavingStrategy] = useState(false);
  const saveStrategyRef = useRef(false);
  const [libraryName, setLibraryName] = useState("");
  const [libraryNameError, setLibraryNameError] = useState<Errors["libraryName"]>();
  const [baseState, setBaseState] = useState<"loading" | "ready" | "missing" | "network" | "invalid" | "error">(baseId ? "loading" : "ready");
  const [baseRetry, setBaseRetry] = useState(0);
  const [conditions, setConditions] = useState<ConditionsDraft>(initialConditions);
  const [strategies, setStrategies] = useState<StrategyDraft[]>([newStrategy(1)]);
  const nextId = useRef(2);
  const [active, setActive] = useState(0);
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Errors>({});
  const [notice, setNotice] = useState("");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [draws, setDraws] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [drawLoading, setDrawLoading] = useState(false);
  const [catalogError, setCatalogError] = useState("");
  const [catalogRetry, setCatalogRetry] = useState(0);
  const [posting, setPosting] = useState(false);
  const postingRef = useRef(false);
  const [dirty, setDirty] = useState(false);
  const submitted = useRef(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [pendingFocus, setPendingFocus] = useState<string | null>(null);
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    dirty && !submitted.current && (currentLocation.pathname !== nextLocation.pathname ||
      (new URLSearchParams(currentLocation.search).get("base") || null) !== (new URLSearchParams(nextLocation.search).get("base") || null) ||
      (new URLSearchParams(currentLocation.search).get("configuration") || null) !== (new URLSearchParams(nextLocation.search).get("configuration") || null)));

  // A query-only navigation keeps this component mounted. Clear the previous
  // clean source before loading another; dirty source changes are blocked above.
  useEffect(() => {
    if (previousSource.current !== sourceKey) {
      setConditions(initialConditions); setStrategies([newStrategy(1)]); nextId.current = 2;
      setDirty(false); setBaseState(baseId ? "loading" : "ready");
      setConfigurationState(configurationId ? "loading" : "ready");
      setStep(0); setActive(0); setErrors({}); setNotice(""); setLibraryOpen(false);
    }
    previousSource.current = sourceKey;
  }, [sourceKey, baseId, configurationId]);

  useEffect(() => {
    if (!dirty || submitted.current) return;
    function warnBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault(); event.returnValue = "";
    }
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [dirty]);

  useEffect(() => { headingRef.current?.focus(); }, [step]);
  useEffect(() => { if (Object.keys(errors).length || notice) errorRef.current?.focus(); }, [errors, notice]);
  // Runs after the errorRef effect above, in the same commit: a server-error field
  // target wins over the alert box, while role="alert" keeps announcing regardless of
  // where focus lands.
  useEffect(() => {
    if (!pendingFocus) return;
    document.getElementById(pendingFocus)?.focus();
    setPendingFocus(null);
  }, [pendingFocus]);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    Promise.all([apiClient.getCatalog(), apiClient.getStartingDraws(0, 100)]).then(([result, page]) => {
      if (!alive) return;
      setCatalog(result); setDraws(page.items); setTotal(page.total); setCatalogError("");
    }).catch((error: unknown) => {
      if (alive) setCatalogError(error instanceof NetworkError ? "No se pudo contactar al servidor local. Probá de nuevo; no sabemos si la cola sigue trabajando." : "No se pudo cargar el catálogo. Probá de nuevo.");
    }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [catalogRetry]);

  useEffect(() => {
    if (!configurationId || baseId || !catalog || loading) return;
    let live = true;
    setConfigurationState("loading");
    apiClient.getConfiguration(configurationId).then((saved) => {
      if (!live) return;
      const draft = draftFromStrategy(saved.strategy, 1);
      if (Object.keys(validateStrategies([draft], catalog)).length) { setConfigurationState("invalid"); return; }
      // A template has no conditions. Replace only the initial empty strategy slot;
      // never assign saved library name to experiment name or synthesize conditions.
      setConditions(initialConditions); setStrategies([draft]); nextId.current = 2;
      setDirty(false); setStep(0); setActive(0); setErrors({}); setNotice(""); setConfigurationState("ready");
    }).catch((error: unknown) => {
      if (live) setConfigurationState(error instanceof ApiError && error.status === 404 ? "missing" : error instanceof NetworkError ? "network" : "error");
    });
    return () => { live = false; };
  }, [configurationId, baseId, catalog, loading, configurationRetry]);

  useEffect(() => {
    if (!libraryOpen) return;
    let live = true;
    setLibraryPage(null); setLibraryError("");
    apiClient.listConfigurations(libraryOffset, 20).then((page) => {
      if (!live) return;
      if (libraryOffset > 0 && page.items.length === 0 && page.total <= libraryOffset) { setLibraryOffset(Math.max(0, Math.ceil(page.total / 20) - 1) * 20); return; }
      setLibraryPage(page);
    }).catch((error: unknown) => { if (live) setLibraryError(error instanceof NetworkError ? "No se pudo contactar al servidor local para cargar la biblioteca." : "No se pudo cargar la biblioteca."); });
    return () => { live = false; };
  }, [libraryOpen, libraryOffset, libraryRetry]);

  useEffect(() => {
    if (!baseId || configurationId || !catalog || loading) return;
    let alive = true;
    setBaseState("loading");
    async function loadBase() {
      try {
        const saved = await apiClient.getExperiment(baseId!);
        if (!alive) return;
        const draft = draftFromRequest(saved.request);
        // The first catalog page is not the whole ranked history. Walk its
        // bounded endpoint until the exact saved label is confirmed or exhausted.
        const available = [...draws];
        for (let offset = 100; !available.includes(draft.conditions.start_draw) && offset < total; offset += 100) {
          const page = await apiClient.getStartingDraws(offset, 100);
          if (!alive) return;
          available.push(...page.items);
          if (!page.items.length) break;
        }
        if (!alive) return;
        if (Object.keys(validateConditions(draft.conditions, available)).length || Object.keys(validateStrategies(draft.strategies, catalog!)).length) {
          setBaseState("invalid"); return;
        }
        setDraws(available);
        setConditions(draft.conditions); setStrategies(draft.strategies); nextId.current = draft.strategies.length + 1;
        setDirty(false); setBaseState("ready"); setStep(0); setActive(0);
        setErrors({}); setNotice("");
      } catch (error) {
        if (alive) setBaseState(error instanceof ApiError && error.status === 404 ? "missing" : error instanceof NetworkError ? "network" : "error");
      }
    }
    void loadBase();
    return () => { alive = false; };
  // Only run after initial catalog load or an explicit retry, not when a user
  // expands the local draw list or edits a prefilled field.
  }, [baseId, catalog, loading, baseRetry]);

  async function appendConfiguration(id: string) {
    if (libraryRef.current || !catalog) return;
    if (strategies.length >= 5) { setLibraryError("Se permiten hasta cinco estrategias."); return; }
    libraryRef.current = true; setLibraryBusy(true); setLibraryError("");
    try {
      const saved = await apiClient.getConfiguration(id);
      const draft = draftFromStrategy(saved.strategy, nextId.current);
      const validation = validateStrategies([...strategies, draft], catalog);
      // Do not append invalid or duplicate catalog data, nor discard the current draft.
      if (Object.keys(validation).length && (validation[`strategies.${strategies.length}.name`] || Object.keys(validateStrategies([draft], catalog)).length)) {
        setLibraryError(validation[`strategies.${strategies.length}.name`] ? "El nombre debe ser único entre las estrategias." : "La configuración guardada ya no coincide con el catálogo o contiene parámetros inválidos."); return;
      }
      nextId.current += 1; setStrategies((previous) => [...previous, draft]); setActive(strategies.length); setDirty(true); setLibraryOpen(false); setErrors({}); setNotice("");
    } catch (error) {
      setLibraryError(error instanceof ApiError && error.status === 404 ? "La configuración ya no existe. Actualizá la biblioteca." : error instanceof NetworkError ? "No se pudo contactar al servidor local. Reintentá." : "No se pudo cargar la configuración. Reintentá.");
      if (error instanceof ApiError && error.status === 404) setLibraryRetry((value) => value + 1);
    } finally { libraryRef.current = false; setLibraryBusy(false); }
  }
  async function saveToLibrary() {
    if (saveStrategyRef.current || !catalog) return;
    const strategy = strategies[active];
    const found = validateStrategies([strategy], catalog);
    if (!trimName(libraryName) || trimName(libraryName).length > 80) { setLibraryNameError("Ingresá un nombre de biblioteca de 1 a 80 caracteres."); return; }
    if (Object.keys(found).length) { setErrors(validateStrategies(strategies, catalog)); setNotice("Corregí la estrategia antes de guardarla en la biblioteca."); return; }
    saveStrategyRef.current = true; setSavingStrategy(true); setNotice("");
    try {
      await apiClient.createConfiguration(trimName(libraryName), buildStrategy(strategy, catalog));
      setNotice("Estrategia guardada en la biblioteca. El experimento todavía no se creó."); setLibraryName(""); setLibraryNameError(undefined);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        const mapped: Errors = {};
        for (const entry of error.fieldErrors ?? []) {
          const path = entry.loc.map(String);
          const body = path.indexOf("body");
          const field = body < 0 ? [] : path.slice(body + 1);
          if (field[0] === "name" && field.length === 1) setLibraryNameError({ message: "El servidor rechazó el nombre de la biblioteca.", detail: entry.msg });
          else if (field[0] === "strategy") mapped[field.length === 1 ? `strategies.${active}` : `strategies.${active}.${field.slice(1).join(".")}`] = { message: "El servidor rechazó este valor de la estrategia.", detail: entry.msg };
          else mapped.form = { message: "El servidor rechazó la solicitud.", detail: entry.msg };
        }
        setErrors((previous) => ({ ...previous, ...mapped }));
        setNotice("El servidor rechazó la estrategia de biblioteca. Revisá los campos señalados.");
      } else setNotice(error instanceof NetworkError ? "No se pudo contactar al servidor local. Comprobá la biblioteca antes de reintentar; tu borrador sigue aquí." : "No se pudo guardar la estrategia. Tu borrador sigue aquí.");
    } finally { saveStrategyRef.current = false; setSavingStrategy(false); }
  }
  async function loadDraws() {
    setDrawLoading(true);
    try {
      const page = await apiClient.getStartingDraws(draws.length, 100);
      setDraws((previous) => [...previous, ...page.items.filter((item) => !previous.includes(item))]);
      setTotal(page.total); setCatalogError("");
    } catch (error) {
      setCatalogError(error instanceof NetworkError ? "No se pudo contactar al servidor local. Reintentá cargar sorteos." : "No se pudieron cargar más sorteos. Reintentá.");
    } finally { setDrawLoading(false); }
  }
  function editCondition(key: keyof ConditionsDraft, value: string) {
    setConditions((previous) => ({ ...previous, [key]: value })); setDirty(true);
    if (key in errors || "conditions" in errors) {
      const updated = { ...errors }; delete updated[key]; delete updated.conditions;
      setErrors(updated); setNotice("");
    }
  }
  function editStrategy(index: number, value: StrategyDraft) {
    const changedKey = diffStrategyKey(strategies[index], value);
    setStrategies((previous) => previous.map((item, i) => i === index ? value : item)); setDirty(true);
    const blockKey = `strategies.${index}`;
    const fieldKey = changedKey ? `${blockKey}.${changedKey}` : null;
    if (blockKey in errors || (fieldKey && fieldKey in errors) || (changedKey?.startsWith("components") && Object.keys(errors).some((key) => key.startsWith(`${blockKey}.components`)))) {
      const updated = { ...errors };
      delete updated[blockKey];
      if (fieldKey) delete updated[fieldKey];
      if (changedKey?.startsWith("components")) {
        delete updated[`${blockKey}.components`];
        const parent = changedKey.match(/^components\.(\d+)\./);
        if (parent) delete updated[`${blockKey}.components.${parent[1]}`];
        if (changedKey === "components") for (const key of Object.keys(updated)) if (key.startsWith(`${blockKey}.components.`)) delete updated[key];
      }
      setErrors(updated); setNotice("");
    }
  }
  function check(target: number): boolean {
    if (!catalog) return false;
    const found = target === 0 ? validateConditions(conditions, draws) : validateStrategies(strategies, catalog);
    setErrors(found); setNotice("");
    if (Object.keys(found).length) { setStep(target); if (target === 1) {
      const match = Object.keys(found).find((key) => key.startsWith("strategies."));
      if (match) setActive(Number(match.split(".")[1]));
    } return false; }
    return true;
  }
  function next() { if (check(step)) setStep(step + 1); }
  function field(key: keyof ConditionsDraft, label: string, element: React.ReactNode, help?: string) {
    const entry = errors[key];
    return <div className="field" key={key}>
      <label htmlFor={key} className="field-label">{label}</label>
      {element}
      {help && <p id={`${key}-help`} className="field-help">{help}</p>}
      {entry && <p id={`${key}-error`} className="mt-1 text-sm text-red-300">{errorMessage(entry)}</p>}
      {errorDetail(entry) && <p className="mt-1 text-xs text-text-secondary">{errorDetail(entry)}</p>}
    </div>;
  }
  function attrs(key: keyof ConditionsDraft, hasHelp = false) {
    const description = [hasHelp && `${key}-help`, errors[key] && `${key}-error`].filter(Boolean).join(" ");
    return { id: key, "aria-invalid": !!errors[key], "aria-describedby": description || undefined } as const;
  }
  function input(key: keyof ConditionsDraft, label: string, help?: string) {
    return field(key, label, <input {...attrs(key, !!help)} className={control} value={conditions[key]} inputMode={key === "name" ? "text" : "numeric"} onChange={(event) => editCondition(key, event.target.value)} />, help);
  }
  async function submit() {
    if (postingRef.current || !catalog || baseId && configurationId || baseId && baseState !== "ready" || configurationId && configurationState !== "ready" || catalogError) return;
    if (!check(0) || !check(1)) return;
    postingRef.current = true; setPosting(true);
    try {
      const created = await apiClient.createExperiment({ request: buildRequest(conditions, strategies, catalog) });
      submitted.current = true; setDirty(false);
      navigate(`/experimentos/${encodeURIComponent(created.id)}`, { replace: true });
    } catch (error) {
      if (error instanceof ApiError && error.status === 422 && error.fieldErrors?.length) {
        const mapped = serverErrors(error.fieldErrors); setErrors(mapped);
        const strategyKey = Object.keys(mapped).find((key) => key.startsWith("strategies."));
        if (strategyKey) setActive(Number(strategyKey.split(".")[1]));
        setStep(strategyKey ? 1 : 0);
        setNotice("El servidor encontró errores. Revisá los campos señalados.");
        setPendingFocus(firstFocusTarget(mapped));
      } else if (error instanceof ApiError && error.status === 507) setNotice("No hay capacidad disponible para crear el experimento. Liberá espacio o consultá los ajustes; tus datos siguen aquí.");
      else if (error instanceof ApiError && error.status === 409) setNotice("La cola no está disponible ahora. Reintentá más tarde; tus datos siguen aquí.");
      else if (error instanceof NetworkError) setNotice("No se pudo contactar al servidor local. La solicitud podría haber llegado: comprobá Experimentos antes de reintentar para evitar duplicados.");
      else setNotice(error instanceof ApiError ? `El servidor rechazó la solicitud (${error.status}): ${error.detail}` : "No se pudo crear el experimento. Comprobá el servidor antes de reintentar.");
    } finally { postingRef.current = false; setPosting(false); }
  }

  if (baseId && configurationId) return <div><Link to="/experimentos" className="text-accent underline">Volver a experimentos</Link><p role="alert" className="mt-4 text-red-300">Se indicaron dos orígenes (base y configuración). Elegí solo uno; no se reemplazó ningún borrador.</p></div>;

  if (configurationId && (configurationState !== "ready" || catalogError)) return <div>
    <Link to="/configuraciones" className="text-accent underline">Volver a configuraciones</Link>
    {catalogError ? <p role="alert" className="mt-4">{catalogError} <button type="button" className="text-accent underline" onClick={() => setCatalogRetry((value) => value + 1)}>Reintentar</button></p> : configurationState === "loading" ? <p role="status">Cargando configuración guardada…</p> : <p role="alert" className="mt-4 text-red-300">{configurationState === "missing" ? "La configuración ya no existe." : configurationState === "network" ? "No se pudo contactar al servidor local para cargar la configuración." : configurationState === "invalid" ? "La configuración ya no coincide con el catálogo o contiene parámetros inválidos; no se reemplazaron valores." : "No se pudo cargar la configuración."} <button type="button" className="text-accent underline" onClick={() => setConfigurationRetry((value) => value + 1)}>Reintentar</button></p>}
  </div>;

  if (baseId && (baseState !== "ready" || catalogError)) return <div>
    <Link to="/experimentos" className="text-accent underline">Volver a experimentos</Link>
    {catalogError ? <p role="alert" className="mt-4">{catalogError} <button type="button" className="text-accent underline" onClick={() => { setCatalogError(""); setCatalogRetry((value) => value + 1); }}>Reintentar</button></p> : baseState === "loading" ? <p role="status">Cargando experimento base y confirmando el sorteo disponible…</p> : <p role="alert" className="mt-4 text-red-300">{baseState === "missing" ? "El experimento base ya no existe." : baseState === "network" ? "No se pudo contactar al servidor local para cargar el experimento base." : baseState === "invalid" ? "El experimento base ya no coincide con el catálogo o contiene parámetros inválidos; no se reemplazaron valores." : "No se pudo cargar el experimento base."} <button type="button" className="text-accent underline" onClick={() => setBaseRetry((value) => value + 1)}>Reintentar</button></p>}
  </div>;

  return <>
    <Link to="/experimentos" className="mb-4 inline-block text-accent underline">Volver a experimentos</Link>
    <nav aria-label="Pasos del asistente" className="mb-6 flex flex-wrap gap-3 border-b border-border pb-4 text-sm">
      {labels.map((label, i) => <span key={label} aria-current={step === i ? "step" : undefined} className={step === i ? "font-semibold text-accent" : "text-text-secondary"}>{i + 1} {label}</span>)}
    </nav>
    <div className="wide:grid wide:grid-cols-[minmax(0,1fr)_300px] wide:gap-8">
      <aside aria-label="Resumen del experimento" className="mb-6 min-w-0 wide:order-2 wide:mb-0">
        <div className="hidden border-t border-border pt-3 wide:block wide:sticky wide:top-6">
          <h2 className="section-header">Resumen</h2><Summary conditions={conditions} count={strategies.length} />
        </div>
        <details className="border-y border-border py-3 wide:hidden"><summary className="cursor-pointer text-sm">Resumen · {strategies.length} estrategias</summary><div className="pt-3"><Summary conditions={conditions} count={strategies.length} /></div></details>
      </aside>
      <div className="min-w-0 wide:order-1">
        <h2 ref={headingRef} tabIndex={-1} className="mb-5 text-2xl focus:outline-none">{labels[step]}</h2>
        {(Object.keys(errors).length > 0 || notice) && <div ref={errorRef} tabIndex={-1} role="alert" className="mb-5 border border-border-control p-3 text-sm focus:outline-accent">
          {notice || "Revisá los errores señalados junto a los campos antes de continuar."}
          {errorDetail(errors.form) && <p className="mt-1 text-xs text-text-secondary">{errorDetail(errors.form)}</p>}
        </div>}
        {step === 0 && <section aria-label="Condiciones comunes">
          {errors.conditions && <p className="mb-4 text-sm text-red-300">{errorMessage(errors.conditions)}{errorDetail(errors.conditions) && <span className="ml-2 text-xs text-text-secondary">{errorDetail(errors.conditions)}</span>}</p>}
          {loading && <p role="status">Cargando catálogo y sorteos disponibles…</p>}
          {catalogError && <p role="alert" className="mb-4 text-red-300">{catalogError} <button type="button" className="text-accent underline" onClick={() => { setCatalogError(""); setCatalogRetry((value) => value + 1); }}>Reintentar</button></p>}
          {catalog && !loading && draws.length === 0 && <p role="status" className="mb-4">No hay sorteos iniciales con ranking disponible.</p>}
          {input("name", "Nombre del experimento")}
          {field("start_draw", "Sorteo inicial", <select {...attrs("start_draw", true)} className={control} value={conditions.start_draw} disabled={!catalog || !draws.length} onChange={(event) => editCondition("start_draw", event.target.value)}>
            <option value="">Elegí un sorteo disponible</option>{draws.map((draw) => <option key={draw} value={draw}>{draw}</option>)}
          </select>, "Solo se ofrecen sorteos históricos con ranking disponible.")}
          {draws.length < total && <button type="button" className={`${secondary} mb-5`} disabled={drawLoading} onClick={loadDraws}>{drawLoading ? "Cargando sorteos…" : "Cargar más sorteos"}</button>}
          {/* Capital and goal are the two amounts that define success; grouped together at sm+. */}
          <div className="sm:grid sm:grid-cols-2 sm:gap-x-4">
            {input("capital", "Capital inicial (RD$)", "Pesos enteros; mínimo RD$1.")}
            {input("goal", "Meta de saldo final (RD$)", "La meta es el saldo final, no ganancia adicional: capital RD$2.000 y meta RD$2.800 buscan +RD$800.")}
          </div>
          {field("settlement", FIELD_LABEL_SETTLEMENT, <select {...attrs("settlement")} className={control} value={conditions.settlement} onChange={(event) => editCondition("settlement", event.target.value)}>{(Object.keys(SETTLEMENT_LABELS) as (keyof typeof SETTLEMENT_LABELS)[]).map((key) => <option value={key} key={key}>{SETTLEMENT_LABELS[key]}</option>)}</select>)}
          {/* Stop limits retain their original keyboard order before the seed. */}
          <div className="sm:grid sm:grid-cols-2 sm:gap-x-4">
            {input("max_bets", "Máximo de apuestas", "Opcional: de 1 a 10.000.000; con otro límite se detiene al alcanzar el primero.")}
            {input("max_minutes", "Máximo de minutos históricos", "Opcional: de 1 a 100.000.000; se excluye el sorteo en la hora límite.")}
          </div>
          {input("seed", FIELD_LABEL_SEED, FIELD_HELP_SEED)}
          {catalog && <p className="border-t border-border pt-4 text-sm text-text-secondary">Juego fijo: {catalog.game.name}, números 00–99, cinco posiciones con repetición; premios {catalog.game.prizes.join("/")}. No se editan en este MVP.</p>}
        </section>}
        {step === 1 && catalog && <section aria-label="Estrategias">
          <p className="mb-5 text-text-secondary">Hasta cinco estrategias comparten las condiciones. Cada nombre debe ser único.</p>
          {strategies.map((strategy, i) => <section key={strategy.id} className="mb-4 border-b border-border pb-4">
            <div className="flex items-center gap-3"><button type="button" aria-expanded={active === i} className="min-h-control flex-1 text-left text-sm text-accent" onClick={() => setActive(i)}>Estrategia {i + 1}{strategy.name ? ` · ${trimName(strategy.name)}` : ""}</button>
              {strategies.length > 1 && <button type="button" className="text-sm text-accent" onClick={() => { setStrategies((previous) => previous.filter((item) => item.id !== strategy.id)); setActive(0); setDirty(true); }}>Quitar {i + 1}</button>}</div>
            {active === i && <div className="pt-4">
              {errors[`strategies.${i}`] && <p className="mb-4 text-sm text-red-300">{errorMessage(errors[`strategies.${i}`])}{errorDetail(errors[`strategies.${i}`]) && <span className="ml-2 text-xs text-text-secondary">{errorDetail(errors[`strategies.${i}`])}</span>}</p>}
              <StrategyEditor value={strategy} index={i} catalog={catalog} errors={errors} onChange={(value) => editStrategy(i, value)} />
            </div>}
          </section>)}
          <div className="flex flex-wrap gap-3"><button type="button" disabled={strategies.length >= 5} className={secondary} onClick={() => { setStrategies((previous) => [...previous, newStrategy(nextId.current++)]); setActive(strategies.length); setDirty(true); }}>Agregar estrategia</button>
          <button type="button" disabled={strategies.length >= 5} className={secondary} onClick={() => setLibraryOpen((value) => !value)}>Agregar desde biblioteca</button></div>
          {libraryOpen && <section aria-label="Seleccionar de biblioteca" className="mt-5 border-t border-border pt-4">
            <h3 className="section-header">Biblioteca de estrategias</h3>
            {libraryError && <p role="alert" className="mb-3 text-sm text-red-300">{libraryError} <button type="button" className="text-accent underline" onClick={() => setLibraryRetry((value) => value + 1)}>Reintentar</button></p>}
            {!libraryPage && !libraryError && <p role="status">Cargando biblioteca…</p>}
            {libraryPage && <>{libraryPage.total === 0 ? <p>No hay estrategias guardadas todavía.</p> : <ul className="divide-y divide-border">{libraryPage.items.map((item) => <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-2"><span>{item.name} · {item.strategy.name}</span><button type="button" className={secondary} disabled={libraryBusy || strategies.length >= 5} onClick={() => { void appendConfiguration(item.id); }}>Añadir {item.name}</button></li>)}</ul>}
              <nav aria-label="Páginas de biblioteca" className="mt-3 flex items-center gap-3"><button type="button" className={secondary} disabled={libraryOffset === 0} onClick={() => setLibraryOffset(Math.max(0, libraryOffset - 20))}>Anterior</button><span>{Math.floor(libraryOffset / 20) + 1} · {libraryPage.total}</span><button type="button" className={secondary} disabled={libraryOffset + 20 >= libraryPage.total} onClick={() => setLibraryOffset(libraryOffset + 20)}>Siguiente</button></nav></>}
          </section>}
          <div className="mt-6 border-t border-border pt-4"><label htmlFor="libraryName" className="field-label">Nombre para guardar en biblioteca</label><input id="libraryName" className={`${control} max-w-md`} value={libraryName} aria-invalid={!!libraryNameError} aria-describedby={libraryNameError ? "libraryName-error" : undefined} onChange={(event) => { setLibraryName(event.target.value); setLibraryNameError(undefined); setDirty(true); }} />{libraryNameError && <p id="libraryName-error" className="mt-1 text-sm text-red-300">{errorMessage(libraryNameError)} <span className="text-xs text-text-secondary">{errorDetail(libraryNameError)}</span></p>}<p className="field-help my-2">Guarda solo esta estrategia, no las condiciones comunes ni crea un experimento.</p><button type="button" className={secondary} disabled={savingStrategy} onClick={() => { void saveToLibrary(); }}>{savingStrategy ? "Guardando…" : "Guardar estrategia en biblioteca"}</button></div>
        </section>}
        {step === 2 && <section aria-label="Revisión">
          <p className="mb-5 text-text-secondary">Revisá los parámetros antes de agregar el experimento a la cola. Los importes y resultados se calculan solo en el servidor.</p>
          <div className="flex items-center justify-between border-b border-border pb-2"><h3 className="section-header">Condiciones comunes</h3><button type="button" className="text-accent underline" onClick={() => setStep(0)}>Editar condiciones</button></div>
          <dl className="data-list py-4"><dt>Nombre</dt><dd>{trimName(conditions.name)}</dd><dt>Sorteo inicial</dt><dd>{conditions.start_draw}</dd><dt>Capital</dt><dd className="data-list-numeric">{money(conditions.capital)}</dd><dt>Meta de saldo final</dt><dd className="data-list-numeric">{money(conditions.goal)}</dd><dt>Liquidación</dt><dd>{SETTLEMENT_LABELS[conditions.settlement]}</dd><dt>Límite de apuestas</dt><dd>{conditions.max_bets || "Sin límite"}</dd><dt>Minutos históricos</dt><dd>{conditions.max_minutes || "Sin límite"}</dd><dt>Semilla</dt><dd>{conditions.seed}</dd></dl>
          <div className="flex items-center justify-between border-b border-border pb-2"><h3 className="section-header">Estrategias</h3><button type="button" className="text-accent underline" onClick={() => setStep(1)}>Editar estrategias</button></div>
          <ul className="divide-y divide-border">{strategies.map((strategy) => <li key={strategy.id} className="py-3"><strong>{trimName(strategy.name)}</strong> · {SELECTOR_LABELS[strategy.selector]}{strategy.selector === "system" ? `: ${catalog?.systems[strategy.system] ?? strategy.system}` : strategy.selector === "blend" ? `: ${strategy.components.map((c) => `${catalog?.systems[c.system] ?? c.system} ${c.weight}%`).join(" + ")}` : ""} · cobertura {strategy.selector === "parity" ? 50 : strategy.coverage} · {STAKING_LABELS[strategy.staking]}</li>)}</ul>
        </section>}
        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
          <button type="button" className={secondary} onClick={() => navigate("/experimentos")}>Salir</button>
          <div className="flex gap-3">{step > 0 && <button type="button" className={secondary} onClick={() => { setErrors({}); setNotice(""); setStep(step - 1); }}>Atrás</button>}
            {step < 2 ? <button type="button" className={primary} disabled={!catalog || !draws.length} onClick={next}>Continuar</button> : <button type="button" className={primary} disabled={posting} onClick={submit}>{posting ? "Agregando…" : "Agregar a la cola"}</button>}
          </div>
        </div>
      </div>
    </div>
    <ConfirmDialog open={blocker.state === "blocked"} title="¿Salir sin guardar?" description="Perderás los cambios del asistente. Salir no cancela ningún cálculo que ya esté en la cola del servidor." confirmLabel="Salir sin guardar" cancelLabel="Seguir editando" onConfirm={() => blocker.proceed?.()} onCancel={() => blocker.reset?.()} />
  </>;
}

function Summary({ conditions, count }: { conditions: ConditionsDraft; count: number }) {
  return <dl className="data-list">
    <dt>Inicio</dt><dd className="break-words">{conditions.start_draw || "Sin elegir"}</dd>
    <dt>Capital</dt><dd className="data-list-numeric break-words">{money(conditions.capital)}</dd>
    <dt>Meta de saldo final</dt><dd className="data-list-numeric break-words">{money(conditions.goal)}</dd>
    <dt>Límites</dt><dd className="break-words">{[conditions.max_bets && `${conditions.max_bets} apuestas`, conditions.max_minutes && `${conditions.max_minutes} min`].filter(Boolean).join(" · ") || "Sin límite"}</dd>
    <dt>Estrategias</dt><dd className="data-list-numeric">{count}</dd>
  </dl>;
}
