import { useEffect, useRef, useState } from "react";
import { Link, useBlocker, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { ApiFieldError } from "../../api/client";
import { isProfileExperiment } from "../../api/types";
import type { Catalog, ConfigurationSummary, Page, StartingDrawAvailability } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { StrategyEditor } from "../../components/StrategyEditor";
import { buildRequest, buildStrategy, diffStrategyKey, draftFromRequest, draftFromStrategy, errorDetail, errorMessage, initialConditions, newStrategy, trimName, validateConditions, validateStrategies } from "./model";
import type { ConditionsDraft, Errors, StrategyDraft } from "./model";
import { FIELD_HELP_SEED, FIELD_LABEL_SEED, FIELD_LABEL_SETTLEMENT, SELECTOR_LABELS, SETTLEMENT_LABELS, STAKING_LABELS } from "../../lib/ui-labels";

const control = "control";
const secondary = "btn btn-secondary";
const primary = "btn btn-primary";
function generatedSeed(): string {
  const values = new Uint32Array(2);
  crypto.getRandomValues(values);
  return String((values[0] & 0x1fffff) * 0x100000000 + values[1]);
}
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
    if (root < 0) { errors.form = { message: "Solicitud rechazada; revisá los datos.", detail: entry.msg }; continue; }
    if (path[0] === "conditions") {
      if (path.length === 1) {
        errors.conditions = { message: "Condiciones rechazadas; revisá esta sección.", detail: entry.msg };
      } else {
        const key = path[1];
        errors[key] = { message: "Valor rechazado; revisá este campo.", detail: entry.msg };
      }
    } else if (path[0] === "strategies" && /^\d+$/.test(path[1] ?? "")) {
      const index = path[1];
      if (path.length === 2) {
        errors[`strategies.${index}`] = { message: "Estrategia rechazada; revisá sus valores.", detail: entry.msg };
      } else {
        const field = path.slice(2).join(".");
        errors[`strategies.${index}.${field}`] = { message: "Valor rechazado; revisá este campo.", detail: entry.msg };
      }
    } else if (path[0] === "name" && path.length === 1) {
      errors.name = { message: "Nombre rechazado; revisá este campo.", detail: entry.msg };
    } else {
      errors.form = { message: "Solicitud rechazada; revisá los datos.", detail: entry.msg };
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
  const [conditions, setConditions] = useState<ConditionsDraft>(() => ({ ...initialConditions, seed: generatedSeed() }));
  const [strategies, setStrategies] = useState<StrategyDraft[]>([newStrategy(1)]);
  const nextId = useRef(2);
  const [active, setActive] = useState(0);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [seedEditing, setSeedEditing] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [notice, setNotice] = useState("");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [draws, setDraws] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [drawDate, setDrawDate] = useState("");
  const [knownDraw, setKnownDraw] = useState("");
  const [verifiedDraw, setVerifiedDraw] = useState("");
  const [availability, setAvailability] = useState<StartingDrawAvailability | null>(null);
  const [loading, setLoading] = useState(true);
  const [drawLoading, setDrawLoading] = useState(false);
  const [drawError, setDrawError] = useState("");
  const [drawRetry, setDrawRetry] = useState(0);
  const drawGeneration = useRef(0);
  const [catalogError, setCatalogError] = useState("");
  const [catalogRetry, setCatalogRetry] = useState(0);
  const [posting, setPosting] = useState(false);
  const postingRef = useRef(false);
  const [dirty, setDirty] = useState(false);
  const submitted = useRef(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const [pendingFocus, setPendingFocus] = useState<string | null>(null);
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    dirty && !submitted.current && (currentLocation.pathname !== nextLocation.pathname ||
      (new URLSearchParams(currentLocation.search).get("base") || null) !== (new URLSearchParams(nextLocation.search).get("base") || null) ||
      (new URLSearchParams(currentLocation.search).get("configuration") || null) !== (new URLSearchParams(nextLocation.search).get("configuration") || null)));

  // A query-only navigation keeps this component mounted. Clear the previous
  // clean source before loading another; dirty source changes are blocked above.
  useEffect(() => {
    if (previousSource.current !== sourceKey) {
      drawGeneration.current += 1;
      setDrawDate(""); setDrawRetry((value) => value + 1);
      setKnownDraw(""); setVerifiedDraw(""); setDraws([]); setTotal(0); setAvailability(null);
      setConditions({ ...initialConditions, seed: generatedSeed() }); setStrategies([newStrategy(1)]); nextId.current = 2;
      setDirty(false); setBaseState(baseId ? "loading" : "ready");
      setConfigurationState(configurationId ? "loading" : "ready");
      setActive(0); setErrors({}); setNotice(""); setLibraryOpen(false); setAdvancedOpen(false); setSeedEditing(false);
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
    apiClient.getCatalog().then((result) => {
      if (!alive) return;
      setCatalog(result); setCatalogError("");
    }).catch((error: unknown) => {
      if (alive) setCatalogError(error instanceof NetworkError ? "No se pudo contactar al servidor. Reintentá." : "No se pudo cargar el catálogo. Reintentá.");
    }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [catalogRetry]);

  useEffect(() => {
    const generation = ++drawGeneration.current;
    let live = true;
    setDrawLoading(true); setDrawError(""); setAvailability(null);
    setDraws([]); setTotal(0); setVerifiedDraw("");
    const requests = [drawDate ? apiClient.getStartingDraws(0, 100, drawDate) : apiClient.getStartingDraws(0, 100),
      ...(drawDate ? [apiClient.getStartingDrawAvailability(drawDate)] : [])] as const;
    Promise.all(requests).then(async ([page, result]) => {
      if (!live || generation !== drawGeneration.current) return;
      let verified = "";
      if (knownDraw && (!drawDate || knownDraw.startsWith(`${drawDate} `)) && !(drawDate && result?.ranked_total === 0)) {
        if (page.items.includes(knownDraw)) verified = knownDraw;
        else {
          // The first page cannot disprove a late-day draw. Recheck only its day,
          // and never reuse confirmation from an earlier filter response.
          const day = knownDraw.slice(0, 10);
          if (/^\d{4}-\d{2}-\d{2} /.test(knownDraw)) {
            let offset = drawDate === day ? page.items.length : 0;
            let totalForDay = drawDate === day ? page.total : Infinity;
            while (offset < totalForDay) {
              const part = await apiClient.getStartingDraws(offset, 100, day);
              if (!live || generation !== drawGeneration.current) return;
              if (part.items.includes(knownDraw)) { verified = knownDraw; break; }
              offset += part.items.length;
              totalForDay = part.total;
              if (!part.items.length) break;
            }
          }
        }
      }
      if (!live || generation !== drawGeneration.current) return;
      setDraws(page.items); setTotal(page.total);
      setAvailability(result ?? null); setVerifiedDraw(verified);
    }).catch((error: unknown) => {
      if (live && generation === drawGeneration.current) setDrawError(error instanceof NetworkError
        ? "No se pudo contactar al servidor. Reintentá."
        : "No se pudieron cargar los sorteos. Reintentá.");
    }).finally(() => {
      if (live && generation === drawGeneration.current) setDrawLoading(false);
    });
    return () => { live = false; };
  }, [drawDate, drawRetry]);

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
      setConditions({ ...initialConditions, seed: generatedSeed() }); setStrategies([draft]); nextId.current = 2;
      setDirty(false); setActive(0); setErrors({}); setNotice(""); setConfigurationState("ready");
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
    }).catch((error: unknown) => { if (live) setLibraryError(error instanceof NetworkError ? "No se pudo contactar al servidor." : "No se pudo cargar la biblioteca."); });
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
        if (isProfileExperiment(saved)) { setBaseState("invalid"); return; }
        const draft = draftFromRequest(saved.request);
        // Search only the saved draw's day, not all earlier ranked history.
        // A day can exceed one page; an exact match is required before prefill.
        const savedDraw = draft.conditions.start_draw;
        const savedDate = /^\d{4}-\d{2}-\d{2} /.test(savedDraw) ? savedDraw.slice(0, 10) : "";
        let found = false;
        if (savedDate) {
          let offset = 0;
          while (true) {
            const page = await apiClient.getStartingDraws(offset, 100, savedDate);
            if (!alive) return;
            if (page.items.includes(savedDraw)) { found = true; break; }
            offset += page.items.length;
            if (!page.items.length || offset >= page.total) break;
          }
        }
        if (!alive) return;
        if (Object.keys(validateConditions(draft.conditions, found ? [savedDraw] : [])).length || Object.keys(validateStrategies(draft.strategies, catalog!)).length) {
          setBaseState("invalid"); return;
        }
        drawGeneration.current += 1;
        setDrawDate(savedDate); setKnownDraw(savedDraw);
        setConditions(draft.conditions); setStrategies(draft.strategies); nextId.current = draft.strategies.length + 1;
        setDirty(false); setBaseState("ready"); setActive(0);
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
        setLibraryError(validation[`strategies.${strategies.length}.name`] ? "El nombre debe ser único entre las estrategias." : "Esta estrategia guardada ya no es válida."); return;
      }
      nextId.current += 1; setStrategies((previous) => [...previous, draft]); setActive(strategies.length); setDirty(true); setLibraryOpen(false); setErrors({}); setNotice("");
    } catch (error) {
      setLibraryError(error instanceof ApiError && error.status === 404 ? "La estrategia ya no existe. Actualizá la biblioteca." : error instanceof NetworkError ? "No se pudo contactar al servidor. Reintentá." : "No se pudo cargar la estrategia. Reintentá.");
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
      setNotice("Estrategia guardada. El experimento aún no se creó."); setLibraryName(""); setLibraryNameError(undefined);
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
        setNotice("El servidor rechazó la estrategia. Revisá los campos señalados.");
      } else setNotice(error instanceof NetworkError ? "No se pudo contactar al servidor. Revisá la biblioteca antes de reintentar; tu borrador sigue aquí." : "No se pudo guardar la estrategia. Tu borrador sigue aquí.");
    } finally { saveStrategyRef.current = false; setSavingStrategy(false); }
  }
  async function loadDraws() {
    const generation = drawGeneration.current;
    const date = drawDate;
    setDrawLoading(true); setDrawError("");
    try {
      const page = date ? await apiClient.getStartingDraws(draws.length, 100, date)
        : await apiClient.getStartingDraws(draws.length, 100);
      if (generation !== drawGeneration.current) return;
      setDraws((previous) => [...previous, ...page.items.filter((item) => !previous.includes(item))]);
      setTotal(page.total);
    } catch (error) {
      if (generation === drawGeneration.current) setDrawError(error instanceof NetworkError ? "No se pudo contactar al servidor. Reintentá." : "No se pudieron cargar más sorteos. Reintentá.");
    } finally { if (generation === drawGeneration.current) setDrawLoading(false); }
  }
  function changeDrawDate(value: string) {
    drawGeneration.current += 1;
    setDrawDate(value); setDraws([]); setTotal(0); setAvailability(null); setVerifiedDraw(""); setDrawError("");
    if (value && conditions.start_draw && !conditions.start_draw.startsWith(`${value} `)) {
      editCondition("start_draw", ""); setKnownDraw("");
    }
  }
  function editCondition(key: keyof ConditionsDraft, value: string) {
    setConditions((previous) => ({ ...previous, [key]: value })); setDirty(true);
    if (key === "start_draw") setKnownDraw(value);
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
  function validateAll(): boolean {
    if (!catalog) return false;
    const available = drawDate && availability?.ranked_total === 0 ? [] : [...draws, ...(verifiedDraw ? [verifiedDraw] : [])];
    const found = {
      ...validateConditions(conditions, drawLoading || drawError ? [] : available),
      ...validateStrategies(strategies, catalog),
    };
    setErrors(found); setNotice("");
    const first = Object.keys(found)[0];
    if (first) {
      const strategyMatch = first.match(/^strategies\.(\d+)/);
      if (strategyMatch) setActive(Number(strategyMatch[1]));
      if (Object.keys(found).some((key) => key === "seed" || key === "max_minutes")) setAdvancedOpen(true);
      if (Object.hasOwn(found, "seed")) setSeedEditing(true);
      if (first !== "conditions" && first !== "strategies") setPendingFocus(first);
      return false;
    }
    return true;
  }
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
    if (!validateAll()) return;
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
        const target = firstFocusTarget(mapped);
        if (target === "seed" || target === "max_minutes") {
          setAdvancedOpen(true);
          if (target === "seed") setSeedEditing(true);
        }
        setNotice("Revisá los campos señalados.");
        setPendingFocus(target);
      } else if (error instanceof ApiError && error.status === 507) setNotice("No hay espacio para crear el experimento. Liberá espacio en Ajustes; tus datos siguen aquí.");
      else if (error instanceof ApiError && error.status === 409) setNotice("La cola no está disponible. Reintentá más tarde; tus datos siguen aquí.");
      else if (error instanceof NetworkError) setNotice("Sin respuesta del servidor. Puede que el experimento se haya creado: revisá Experimentos antes de reintentar.");
      else setNotice(error instanceof ApiError ? `Solicitud rechazada: ${error.detail}` : "No se pudo crear el experimento. Reintentá.");
    } finally { postingRef.current = false; setPosting(false); }
  }

  const offeredDraws = drawDate && availability?.ranked_total === 0 ? [] : draws;
  const selectedAvailable = !!conditions.start_draw &&
    (offeredDraws.includes(conditions.start_draw) || verifiedDraw === conditions.start_draw);
  const staleDraw = !!knownDraw && conditions.start_draw === knownDraw && !drawLoading && !drawError && !selectedAvailable;

  if (baseId && configurationId) return <div><Link to="/experimentos" className="link">Volver a experimentos</Link><p role="alert" className="mt-4 text-red-300">Hay dos orígenes (base y estrategia guardada). Elegí solo uno.</p></div>;

  if (configurationId && (configurationState !== "ready" || catalogError)) return <div>
    <Link to="/configuraciones" className="link">Volver a estrategias guardadas</Link>
    {catalogError ? <p role="alert" className="mt-4">{catalogError} <button type="button" className="btn btn-tertiary" onClick={() => setCatalogRetry((value) => value + 1)}>Reintentar</button></p> : configurationState === "loading" ? <p role="status">Cargando estrategia…</p> : <p role="alert" className="mt-4 text-red-300">{configurationState === "missing" ? "La estrategia ya no existe." : configurationState === "network" ? "No se pudo contactar al servidor." : configurationState === "invalid" ? "Esta estrategia guardada ya no es válida." : "No se pudo cargar la estrategia."} <button type="button" className="btn btn-tertiary" onClick={() => setConfigurationRetry((value) => value + 1)}>Reintentar</button></p>}
  </div>;

  if (baseId && (baseState !== "ready" || catalogError)) return <div>
    <Link to="/experimentos" className="link">Volver a experimentos</Link>
    {catalogError ? <p role="alert" className="mt-4">{catalogError} <button type="button" className="btn btn-tertiary" onClick={() => { setCatalogError(""); setCatalogRetry((value) => value + 1); }}>Reintentar</button></p> : baseState === "loading" ? <p role="status">Cargando experimento base…</p> : <p role="alert" className="mt-4 text-red-300">{baseState === "missing" ? "El experimento base ya no existe." : baseState === "network" ? "No se pudo contactar al servidor." : baseState === "invalid" ? "El experimento base no es compatible con este asistente." : "No se pudo cargar el experimento base."} <button type="button" className="btn btn-tertiary" onClick={() => setBaseRetry((value) => value + 1)}>Reintentar</button></p>}
  </div>;

  return <>
    <Link to="/experimentos" className="mb-4 inline-block link">Volver a experimentos</Link>
    <div className="mb-5 border-y border-border py-4 text-sm"><p>¿Tenés un perfil y datos importados? <Link to="/experimentos/nuevo/perfil" className="link">Crear simulación con perfil</Link>.</p></div>
    <form className="max-w-4xl" noValidate onSubmit={(event) => { event.preventDefault(); void submit(); }}>
        {(Object.keys(errors).length > 0 || notice) && <div ref={errorRef} tabIndex={-1} role="alert" className="mb-5 border border-border-control p-3 text-sm focus:outline-accent">
          {notice || "Revisá los errores señalados junto a los campos antes de crear la simulación."}
          {errorDetail(errors.form) && <p className="mt-1 text-xs text-text-secondary">{errorDetail(errors.form)}</p>}
        </div>}
        {errors.conditions && <p className="mb-4 text-sm text-red-300">{errorMessage(errors.conditions)}{errorDetail(errors.conditions) && <span className="ml-2 text-xs text-text-secondary">{errorDetail(errors.conditions)}</span>}</p>}
        {loading && <p role="status">Cargando catálogo…</p>}
        {catalogError && <p role="alert" className="mb-4 text-red-300">{catalogError} <button type="button" className="btn btn-tertiary" onClick={() => { setCatalogError(""); setCatalogRetry((value) => value + 1); }}>Reintentar</button></p>}

        <div className="mb-8 sm:grid sm:grid-cols-2 sm:gap-x-4">
          {input("name", "Nombre del experimento")}
          {field("start_draw", "Sorteo inicial", <select {...attrs("start_draw", true)} className={control} value={conditions.start_draw} disabled={!catalog || drawLoading || !!drawError || (!offeredDraws.length && !selectedAvailable)} onChange={(event) => editCondition("start_draw", event.target.value)}>
            <option value="">Elegí un sorteo disponible</option>{offeredDraws.map((draw) => <option key={draw} value={draw}>{draw}</option>)}
            {knownDraw && !offeredDraws.includes(knownDraw) && (!drawDate || knownDraw.startsWith(`${drawDate} `)) && <option value={knownDraw} disabled={!selectedAvailable}>{knownDraw}{selectedAvailable ? "" : " (sin ranking disponible)"}</option>}
          </select>)}
        </div>
        <fieldset className="mb-8 min-w-0 border-0 p-0">
          <legend className="section-header mb-3 p-0">Reglas del sorteo</legend>
          {catalog && <dl className="data-list mb-3">
            <dt>Universo</dt><dd>{String(catalog.game.numbers).padStart(2, "0")} números (00–{String(catalog.game.numbers - 1).padStart(2, "0")})</dd>
            <dt>Posiciones por sorteo</dt><dd>{catalog.game.positions}</dd>
            <dt>Repeticiones</dt><dd>{catalog.game.allows_repeats ? "Permitidas" : "No permitidas"}</dd>
            <dt>Premios por posición</dt><dd>{catalog.game.prizes.map((prize, index) => `${index + 1}: ${prize}`).join(" · ")}</dd>
            <dt>Apuesta mínima</dt><dd>No indicada en el catálogo</dd>
          </dl>}
          <Link to="/datos#perfiles" className="link text-sm">Editar reglas</Link>
        </fieldset>

        <fieldset className="mb-8 min-w-0 border-0 p-0">
          <legend className="section-header mb-3 p-0">Selección</legend>
          {drawLoading && <p role="status" className="mb-4">Cargando sorteos disponibles…</p>}
          {drawError && <p role="alert" className="mb-4 text-red-300">{drawError} <button type="button" className="btn btn-tertiary" onClick={() => setDrawRetry((value) => value + 1)}>Reintentar</button></p>}
          {staleDraw && <p role="status" className="mb-4 text-text-secondary">Ese sorteo ya no está disponible. Elegí otro.</p>}
          {catalog && !drawLoading && !drawError && offeredDraws.length === 0 && !knownDraw && <p role="status" className="mb-4">{drawDate && availability?.history_total === 0 ? "No hay sorteos en esta fecha. Probá otra." : drawDate && availability?.ranked_total === 0 ? "Ningún sorteo de esta fecha tiene ranking. Probá otra." : "No hay sorteos iniciales disponibles."}</p>}
          {draws.length < total && <button type="button" className={`${secondary} mb-5`} disabled={drawLoading} onClick={() => { void loadDraws(); }}>{drawLoading ? "Cargando sorteos…" : "Cargar más sorteos"}</button>}
          {field("settlement", FIELD_LABEL_SETTLEMENT, <select {...attrs("settlement")} className={control} value={conditions.settlement} onChange={(event) => editCondition("settlement", event.target.value)}>{(Object.keys(SETTLEMENT_LABELS) as (keyof typeof SETTLEMENT_LABELS)[]).map((key) => <option value={key} key={key}>{SETTLEMENT_LABELS[key]}</option>)}</select>)}
          {catalog && <div className="mt-5">{strategies.map((strategy, i) => <section key={strategy.id} className="mb-4 border-b border-border pb-4">
            <div className="flex items-center gap-3"><button type="button" aria-expanded={active === i} className="min-h-control flex-1 text-left text-sm text-accent" onClick={() => setActive(i)}>Estrategia {i + 1}{strategy.name ? ` · ${trimName(strategy.name)}` : ""}</button>
              {strategies.length > 1 && <button type="button" className="btn btn-tertiary" onClick={() => { setStrategies((previous) => previous.filter((item) => item.id !== strategy.id)); setActive(0); setDirty(true); }}>Quitar {i + 1}</button>}</div>
            {active === i && <div className="pt-4">
              {errors[`strategies.${i}`] && <p className="mb-4 text-sm text-red-300">{errorMessage(errors[`strategies.${i}`])}{errorDetail(errors[`strategies.${i}`]) && <span className="ml-2 text-xs text-text-secondary">{errorDetail(errors[`strategies.${i}`])}</span>}</p>}
              <StrategyEditor value={strategy} index={i} catalog={catalog} errors={errors} onChange={(value) => editStrategy(i, value)} />
            </div>}
          </section>)}
          <div className="flex flex-wrap gap-3"><button type="button" disabled={strategies.length >= 5} className={secondary} onClick={() => { setStrategies((previous) => [...previous, newStrategy(nextId.current++)]); setActive(strategies.length); setDirty(true); }}>Agregar estrategia</button>
          <button type="button" disabled={strategies.length >= 5} className={secondary} onClick={() => setLibraryOpen((value) => !value)}>Agregar desde biblioteca</button></div>
          {libraryOpen && <section aria-label="Seleccionar de biblioteca" className="mt-5 border-t border-border pt-4">
            <h3 className="section-header">Biblioteca de estrategias</h3>
            {libraryError && <p role="alert" className="mb-3 text-sm text-red-300">{libraryError} <button type="button" className="btn btn-tertiary" onClick={() => setLibraryRetry((value) => value + 1)}>Reintentar</button></p>}
            {!libraryPage && !libraryError && <p role="status">Cargando biblioteca…</p>}
            {libraryPage && <>{libraryPage.total === 0 ? <p>No hay estrategias guardadas todavía.</p> : <ul className="divide-y divide-border">{libraryPage.items.map((item) => <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-2"><span>{item.name} · {item.strategy.name}</span><button type="button" className={secondary} disabled={libraryBusy || strategies.length >= 5} onClick={() => { void appendConfiguration(item.id); }}>Añadir {item.name}</button></li>)}</ul>}
              <nav aria-label="Páginas de biblioteca" className="mt-3 flex items-center gap-3"><button type="button" className={secondary} disabled={libraryOffset === 0} onClick={() => setLibraryOffset(Math.max(0, libraryOffset - 20))}>Anterior</button><span>{Math.floor(libraryOffset / 20) + 1} · {libraryPage.total}</span><button type="button" className={secondary} disabled={libraryOffset + 20 >= libraryPage.total} onClick={() => setLibraryOffset(libraryOffset + 20)}>Siguiente</button></nav></>}
          </section>}
          <div className="mt-6 border-t border-border pt-4"><label htmlFor="libraryName" className="field-label">Nombre para guardar en biblioteca</label><input id="libraryName" className={`${control} max-w-md`} value={libraryName} aria-invalid={!!libraryNameError} aria-describedby={libraryNameError ? "libraryName-error" : undefined} onChange={(event) => { setLibraryName(event.target.value); setLibraryNameError(undefined); setDirty(true); }} />{libraryNameError && <p id="libraryName-error" className="mt-1 text-sm text-red-300">{errorMessage(libraryNameError)} <span className="text-xs text-text-secondary">{errorDetail(libraryNameError)}</span></p>}<p className="field-help my-2">Guarda solo esta estrategia.</p><button type="button" className={secondary} disabled={savingStrategy} onClick={() => { void saveToLibrary(); }}>{savingStrategy ? "Guardando…" : "Guardar estrategia en biblioteca"}</button></div>
          </div>}
        </fieldset>

        <fieldset className="mb-8 min-w-0 border-0 p-0"><legend className="section-header mb-3 p-0">Límites</legend>
          <div className="sm:grid sm:grid-cols-2 sm:gap-x-4">{input("capital", "Capital inicial (RD$)", "Pesos enteros; mínimo RD$1.")}{input("goal", "Meta de saldo final (RD$)", "Saldo final buscado, no ganancia: capital RD$2.000 y meta RD$2.800 buscan +RD$800.")}</div>
          {input("max_bets", "Máximo de apuestas", "Opcional (1 a 10.000.000). Se detiene al primer límite alcanzado.")}
        </fieldset>

        <details open={advancedOpen} onToggle={(event) => setAdvancedOpen(event.currentTarget.open)} className="mb-8 border-y border-border py-3">
          <summary className="disclosure-summary">Ajustes avanzados</summary>
          <div className="pt-4">
            <p className="mb-2 text-sm">{FIELD_LABEL_SEED}: <output id="seed-summary">{conditions.seed}</output></p>
            {seedEditing ? input("seed", FIELD_LABEL_SEED, FIELD_HELP_SEED) : <><p id="seed-help" className="field-help mb-3">{FIELD_HELP_SEED}</p><button type="button" className={secondary} onClick={() => setSeedEditing(true)}>Cambiar</button></>}
            <div className="mt-5 max-w-md">{input("max_minutes", "Máximo de minutos históricos", "Opcional (1 a 100.000.000). No incluye el sorteo en la hora límite.")}</div>
            <div className="field max-w-md"><label htmlFor="draw_date" className="field-label">Filtrar sorteos por fecha</label><input id="draw_date" type="date" className={control} value={drawDate} aria-describedby="draw_date-help" onChange={(event) => changeDrawDate(event.target.value)} /><p id="draw_date-help" className="field-help">Vacío: todas las fechas.</p></div>
          </div>
        </details>
        <section aria-label="Resumen de selección" className="mb-6 border-t border-border pt-4">
          <h2 className="section-header mb-3">Resumen</h2>
          <p>{strategies.map((strategy) => `${trimName(strategy.name) || "Sin nombre"}: ${SELECTOR_LABELS[strategy.selector]}${strategy.selector === "system" ? ` (${catalog?.systems[strategy.system] ?? strategy.system})` : strategy.selector === "blend" ? ` (${strategy.components.map((c) => `${catalog?.systems[c.system] ?? c.system} ${c.weight}%`).join(" + ")})` : ""}, cobertura ${strategy.selector === "parity" ? 50 : strategy.coverage}, ${STAKING_LABELS[strategy.staking]}`).join(" · ")}</p>
        </section>
        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
          <button type="button" className={secondary} onClick={() => navigate("/experimentos")}>Salir</button>
          <button type="submit" className={primary} disabled={!catalog || loading || drawLoading || !!drawError || (!offeredDraws.length && !selectedAvailable) || posting}>{posting ? "Creando…" : "Crear simulación"}</button>
        </div>
    </form>
    <ConfirmDialog open={blocker.state === "blocked"} title="¿Salir sin guardar?" description="Perderás los cambios. Lo que ya está en la cola sigue su curso." confirmLabel="Salir sin guardar" cancelLabel="Seguir editando" onConfirm={() => blocker.proceed?.()} onCancel={() => blocker.reset?.()} />
  </>;
}
