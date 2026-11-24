import { useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { ApiError, NetworkError } from "../../api/client";
import { getHistory, importHistory } from "../../api/history";
import { getLists, setActiveList, setListPrizes } from "../../api/lists";
import { getSettings, updateSettings } from "../../api/settings";
import type { HistoryImportResponse, HistoryResponse, HistorySnapshot, NumberListInfo, SettingsResponse } from "../../api/types";
import { Block, SectionHeader } from "../../components/ui/Block";
import { Button, Field } from "../../components/ui/Controls";
import { ErrorBanner, Loading } from "../../components/ui/Feedback";
import { formatLongDate, formatNumber } from "../../lib/format";
import {
  PRIZE_ERROR, bytesToMbInput, formatDiskBytes, formatExactBytes, formatSize, mbInputToBytes, parsePrizes,
  isUnlimited, positionLabel, quotaMbError, remainingBytes, UNLIMITED_BYTES, usagePercent,
} from "./settings-model";
import "./settings.css";

const MAX_IMPORT_BYTES = 32 * 1024 * 1024;
const CHANCE_ID = "chance_express";
const QUOTA_SOURCE_LABELS: Record<string, string> = {
  persisted: "lo elegiste vos",
  default: "sin límite de fábrica",
  environment: "lo fija el arranque de la aplicación",
  env: "lo fija el arranque de la aplicación",
};
const BYTE_FORMAT = (value: string) => formatExactBytes(value);

interface Snapshot { lists: NumberListInfo[]; settings: SettingsResponse; history: HistoryResponse | null }

function apiMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.detail : fallback;
}
function snapshotDescription(source: HistorySnapshot): string {
  return `${source.draws} sorteos · ${source.first_label} a ${source.last_label}`;
}
function importConfirmation(result: HistoryImportResponse): string {
  if (!result.created && result.added === 0) return "Ya estaba en las fuentes; no se agregaron sorteos.";
  return `Importación confirmada: se agregaron ${result.added} sorteos; el historial activo tiene ${result.active.draws} sorteos.`;
}
function listPeriod(list: NumberListInfo): string {
  const draws = `${formatNumber(list.draws)} ${list.draws === 1 ? "sorteo" : "sorteos"}`;
  if (!list.first_label || !list.last_label) return draws;
  return `${draws} · del ${formatLongDate(list.first_label)} al ${formatLongDate(list.last_label)}`;
}
function positionsText(count: number): string {
  return `${count} ${count === 1 ? "número" : "números"} por sorteo`;
}
async function readAll(signal: AbortSignal): Promise<Snapshot> {
  const [lists, settings, history] = await Promise.all([
    getLists({ signal }), getSettings({ signal }),
    // While Leidsa is active the history endpoint answers 409: that is expected, not a failure.
    getHistory({ signal }).catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 409) return null;
      throw error;
    }),
  ]);
  return { lists, settings, history };
}

export function SettingsPage() {
  const [lists, setLists] = useState<NumberListInfo[] | null>(null);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [quotaDraft, setQuotaDraft] = useState("");
  const [quotaError, setQuotaError] = useState<string | null>(null);
  const [quotaSaved, setQuotaSaved] = useState(false);
  const [mutationBusy, setMutationBusy] = useState(false);
  const [switchedTo, setSwitchedTo] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [prizeDrafts, setPrizeDrafts] = useState<string[]>([]);
  const [prizeError, setPrizeError] = useState<string | null>(null);
  const [prizeSaved, setPrizeSaved] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [confirmedImport, setConfirmedImport] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState(false);
  const [ambiguousImport, setAmbiguousImport] = useState(false);
  const readController = useRef<AbortController | null>(null);
  const mutationController = useRef<AbortController | null>(null);
  const readSequence = useRef(0);
  const mutationEpoch = useRef(0);
  const reconcileSequence = useRef(0);
  const busyGuard = useRef(false);
  const mounted = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const advancedRef = useRef<HTMLDetailsElement>(null);

  const applyLists = useCallback((next: NumberListInfo[]) => {
    setLists(next);
    const active = next.find((item) => item.active);
    setPrizeDrafts(active ? active.prizes.map(String) : []);
    setPrizeError(null);
    setPrizeSaved(null);
  }, []);
  const applyQuota = useCallback((next: SettingsResponse) => {
    setSettings(next);
    setQuotaDraft(bytesToMbInput(next.quota.effective_bytes));
    setQuotaError(null);
    setQuotaSaved(false);
  }, []);

  const refresh = useCallback(async (initial = false) => {
    readController.current?.abort();
    const controller = new AbortController();
    readController.current = controller;
    const sequence = ++readSequence.current;
    const epoch = mutationEpoch.current;
    if (initial) { setLoading(true); setLoadError(null); }
    try {
      const next = await readAll(controller.signal);
      if (controller.signal.aborted || sequence !== readSequence.current || epoch !== mutationEpoch.current) return false;
      setHistory(next.history);
      applyLists(next.lists);
      applyQuota(next.settings);
      setLoadError(null);
      setRefreshError(false);
      return true;
    } catch {
      if (controller.signal.aborted || sequence !== readSequence.current || epoch !== mutationEpoch.current) return false;
      if (initial) setLoadError("No se pudieron cargar los ajustes.");
      else setRefreshError(true);
      return false;
    } finally {
      if (!controller.signal.aborted && sequence === readSequence.current && epoch === mutationEpoch.current && initial) setLoading(false);
    }
  }, [applyLists, applyQuota]);

  useEffect(() => {
    mounted.current = true;
    void refresh(true);
    return () => {
      mounted.current = false;
      readSequence.current++;
      readController.current?.abort();
      mutationController.current?.abort();
      mutationController.current = null;
    };
  }, [refresh]);

  // Import feedback lives in "Avanzado": open it so the message is never hidden.
  useEffect(() => {
    if ((importError || confirmedImport || refreshError) && advancedRef.current) advancedRef.current.open = true;
  }, [importError, confirmedImport, refreshError]);

  const beginMutation = (): AbortController => {
    readController.current?.abort();
    mutationController.current?.abort();
    mutationEpoch.current++;
    const controller = new AbortController();
    mutationController.current = controller;
    busyGuard.current = true;
    setMutationBusy(true);
    return controller;
  };
  const endMutation = (controller: AbortController) => {
    if (mutationController.current !== controller) return;
    busyGuard.current = false;
    setMutationBusy(false);
  };

  async function chooseList(list: NumberListInfo) {
    if (busyGuard.current || !list.available || list.active) return;
    setListError(null);
    setSwitchedTo(null);
    const controller = beginMutation();
    try {
      const updated = await setActiveList(list.id, { signal: controller.signal });
      if (controller.signal.aborted) return;
      applyLists(updated);
      setSwitchedTo(list.name);
      setConfirmedImport(null);
      setImportError(null);
      endMutation(controller);
      // The history and storage figures depend on the list in use: read them again.
      await refresh(false);
    } catch (error) {
      if (controller.signal.aborted) return;
      setListError(apiMessage(error, error instanceof NetworkError ? "No se pudo contactar al servidor local. No se cambió la lista." : "No se pudo cambiar la lista."));
    } finally { endMutation(controller); }
  }

  async function savePrizes(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const active = lists?.find((item) => item.active);
    if (busyGuard.current || !active) return;
    setPrizeSaved(null);
    const parsed = parsePrizes(prizeDrafts);
    if (!parsed) { setPrizeError(PRIZE_ERROR); return; }
    await sendPrizes(active, parsed, "Premios guardados.");
  }

  async function restorePrizes() {
    const active = lists?.find((item) => item.active);
    if (busyGuard.current || !active) return;
    setPrizeSaved(null);
    await sendPrizes(active, null, "Se restauraron los valores originales.");
  }

  async function sendPrizes(active: NumberListInfo, prizes: number[] | null, confirmation: string) {
    const controller = beginMutation();
    try {
      const updated = await setListPrizes(active.id, prizes, { signal: controller.signal });
      if (controller.signal.aborted) return;
      applyLists(updated);
      setPrizeSaved(confirmation);
    } catch (error) {
      if (controller.signal.aborted) return;
      setPrizeError(apiMessage(error, error instanceof NetworkError ? "No se pudo contactar al servidor local. No se confirmó el cambio de premios." : "No se pudieron guardar los premios."));
    } finally { endMutation(controller); }
  }

  async function saveQuota(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busyGuard.current || !settings?.quota.writable) return;
    const validation = quotaMbError(quotaDraft);
    setQuotaError(validation);
    setQuotaSaved(false);
    const bytes = mbInputToBytes(quotaDraft);
    if (validation || bytes === null) return;
    const controller = beginMutation();
    try {
      const saved = await updateSettings(bytes, { signal: controller.signal });
      if (controller.signal.aborted) return;
      applyQuota(saved);
      setQuotaSaved(true);
    } catch (error) {
      if (controller.signal.aborted) return;
      setQuotaError(apiMessage(error, error instanceof NetworkError ? "No se pudo contactar al servidor local. No se confirmó el cambio de límite." : "No se pudo guardar el límite."));
    } finally { endMutation(controller); }
  }

  async function saveUnlimited() {
    if (busyGuard.current || !settings?.quota.writable) return;
    setQuotaError(null);
    setQuotaSaved(false);
    const controller = beginMutation();
    try {
      const saved = await updateSettings(UNLIMITED_BYTES, { signal: controller.signal });
      if (controller.signal.aborted) return;
      applyQuota(saved);
      setQuotaSaved(true);
    } catch (error) {
      if (controller.signal.aborted) return;
      setQuotaError(apiMessage(error, error instanceof NetworkError ? "No se pudo contactar al servidor local. No se confirmó el cambio de límite." : "No se pudo quitar el límite."));
    } finally { endMutation(controller); }
  }

  async function reconcileHistory() {
    const epoch = mutationEpoch.current;
    const request = ++reconcileSequence.current;
    setRefreshError(false);
    const refreshed = await refresh(false);
    if (!mounted.current || epoch !== mutationEpoch.current || request !== reconcileSequence.current) return;
    if (!refreshed) {
      setAmbiguousImport(true);
      setImportError("No se pudo confirmar la importación; actualizá el historial para comprobar el resultado.");
    } else {
      setAmbiguousImport(false);
      setImportError(null);
    }
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    setImportError(null);
    setConfirmedImport(null);
    setRefreshError(false);
    setAmbiguousImport(false);
    if (!file || busyGuard.current) return;
    if (file.size > MAX_IMPORT_BYTES) {
      setImportError("El archivo supera el límite de 32 MiB.");
      return;
    }
    const controller = beginMutation();
    let raw: string;
    try {
      raw = await file.text();
    } catch {
      if (!controller.signal.aborted && mounted.current) setImportError("No se pudo leer el archivo. Elegí otro archivo e intentá de nuevo.");
      endMutation(controller);
      return;
    }
    if (controller.signal.aborted) { endMutation(controller); return; }
    try {
      const result = await importHistory(raw, { signal: controller.signal });
      if (controller.signal.aborted || !mounted.current) return;
      setHistory((current) => current ? {
        active: result.active,
        sources: [result.active, ...current.sources.filter((source) => source.sha256 !== result.active.sha256).map((source) => ({ ...source, active: false }))],
      } : { active: result.active, sources: [result.active] });
      setConfirmedImport(importConfirmation(result));
      setAmbiguousImport(false);
      endMutation(controller);
      const refreshed = await refreshAfterImport(controller);
      if (!refreshed && mounted.current && mutationController.current === controller && !controller.signal.aborted) setRefreshError(true);
    } catch (error) {
      if (controller.signal.aborted || !mounted.current) return;
      if (error instanceof NetworkError) {
        setImportError("No se pudo confirmar la importación; actualizá el historial para comprobar el resultado.");
        setAmbiguousImport(true);
      } else {
        setImportError(apiMessage(error, error instanceof Error ? error.message : "No se pudo importar el historial."));
      }
    } finally { endMutation(controller); }
  }

  async function refreshAfterImport(controller: AbortController): Promise<boolean> {
    const sequence = ++readSequence.current;
    const epoch = mutationEpoch.current;
    const refreshController = new AbortController();
    readController.current?.abort();
    readController.current = refreshController;
    try {
      const next = await readAll(refreshController.signal);
      if (!mounted.current || controller.signal.aborted || refreshController.signal.aborted || sequence !== readSequence.current || epoch !== mutationEpoch.current) return false;
      setHistory(next.history);
      applyQuota(next.settings);
      return true;
    } catch {
      return false;
    }
  }

  const disabled = mutationBusy;

  if (loading) return <Loading label="Cargando ajustes" rows={4} className="settings-loading" />;
  if (loadError || !settings || !lists) return <ErrorBanner cause={loadError ?? "No se pudieron cargar los datos."} recovery="Podés volver a intentar la lectura del servidor." actionLabel="Reintentar" onAction={() => void refresh(true)} />;

  const active = lists.find((item) => item.active) ?? null;
  const storage = settings.storage;
  const quotaWritable = settings.quota.writable;
  const used = storage.admission_logical_bytes_exact;
  const limit = settings.quota.effective_bytes;
  const left = remainingBytes(limit, used);
  const percent = usagePercent(used, limit);
  const unlimited = isUnlimited(limit);
  const quotaDirty = quotaDraft !== bytesToMbInput(limit);
  const quotaInvalid = quotaMbError(quotaDraft);
  const shownQuotaError = quotaError ?? (quotaDirty ? quotaInvalid : null);
  const sourceLabel = QUOTA_SOURCE_LABELS[settings.quota.source] ?? "valor de fábrica";
  const prizesDirty = active ? prizeDrafts.join(",") !== active.prizes.join(",") : false;
  const prizesAtDefault = active ? active.prizes.join(",") === active.default_prizes.join(",") && !prizesDirty : true;
  const onChance = active?.id === CHANCE_ID;

  return <div className="settings-page">
    <div className="settings-intro">
      <p>Elegí con qué lista de números trabajás, ajustá cuánto paga cada posición y revisá el espacio que usa la aplicación.</p>
    </div>

    <Block aria-labelledby="settings-lists-title" className="settings-section">
      <SectionHeader id="settings-lists-title" title="Lista de números" />
      <p className="settings-note">Los laboratorios y las corridas usan siempre la lista que está en uso.</p>
      <ul className="settings-lists">
        {lists.map((list) => <li key={list.id} className="settings-list-card" data-active={list.active ? "true" : "false"} aria-labelledby={`list-name-${list.id}`}>
          <div className="settings-list-text">
            <h3 id={`list-name-${list.id}`}>{list.name}</h3>
            <p>{listPeriod(list)}</p>
            <p className="settings-list-meta">{positionsText(list.positions)}</p>
            {!list.available && <p className="settings-list-missing" id={`list-missing-${list.id}`}>Falta el archivo de esta lista</p>}
          </div>
          <div className="settings-list-action">
            {list.active
              ? <span className="settings-badge">✓ En uso</span>
              : <Button variant="secondary" disabled={disabled || !list.available} aria-describedby={`list-name-${list.id}${list.available ? "" : ` list-missing-${list.id}`}`} onClick={() => void chooseList(list)}>Usar esta lista</Button>}
          </div>
        </li>)}
      </ul>
      {switchedTo && <p className="settings-success" role="status">Ahora trabajás con «{switchedTo}».</p>}
      {listError && <p className="settings-error" role="alert">{listError}</p>}
    </Block>

    {active && <Block aria-labelledby="settings-prizes-title" className="settings-section">
      <SectionHeader id="settings-prizes-title" title="Premios" />
      <p className="settings-note">Premios de «{active.name}». Se usan al crear laboratorios y corridas nuevos.</p>
      <form className="settings-prizes-form" onSubmit={(event) => void savePrizes(event)} noValidate>
        <fieldset className="settings-prizes" disabled={disabled}>
          <legend className="ledger-label">Paga por cada peso</legend>
          <div className="settings-prizes-grid">
            {prizeDrafts.map((draft, index) => <Field key={`${active.id}-${index}`} id={`prize-${index + 1}`} label={positionLabel(index)} inputMode="numeric" autoComplete="off" value={draft}
              aria-invalid={prizeError ? true : undefined} aria-describedby={prizeError ? "prizes-error" : undefined}
              onChange={(event) => { setPrizeDrafts(prizeDrafts.map((item, i) => (i === index ? event.target.value : item))); setPrizeError(null); setPrizeSaved(null); }} />)}
          </div>
        </fieldset>
        {prizeError && <p id="prizes-error" className="ledger-error" role="alert">{prizeError}</p>}
        <div className="settings-actions">
          <Button type="submit" variant="primary" disabled={disabled || !prizesDirty} aria-busy={disabled}>Guardar</Button>
          <Button variant="secondary" disabled={disabled || prizesAtDefault} onClick={() => void restorePrizes()}>Volver a los valores originales</Button>
        </div>
        {prizeSaved && <p className="settings-success" role="status">{prizeSaved}</p>}
      </form>
    </Block>}

    <Block aria-labelledby="settings-storage-title" className="settings-section">
      <SectionHeader id="settings-storage-title" title="Espacio" />
      {storage.warning && <p className="settings-warning" role="status">Queda poco espacio disponible.</p>}
      <div className="settings-usage">
        <p className="settings-usage-line"><span>Espacio usado</span><strong>{unlimited ? `${formatSize(used)} · Sin límite` : `${formatSize(used)} de ${formatSize(limit)}`}</strong></p>
        {!unlimited && <div className="settings-meter" role="progressbar" aria-label="Espacio usado" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-valuetext={`${percent} % del límite`} data-high={percent >= 85 ? "true" : "false"}>
          <span style={{ width: `${percent}%` }} />
        </div>}
        {unlimited ? <p className="settings-note">Sin límite: la aplicación solo se detiene si el disco se llena de verdad.</p>
          : <p className="settings-note">Quedan {formatSize(left)} libres ({percent} % usado).</p>}
      </div>
      <form className="settings-quota-form" onSubmit={(event) => void saveQuota(event)} noValidate>
        <div className="field">
          <label className="ledger-label" htmlFor="settings-quota">Límite de espacio (MB)</label>
          <input id="settings-quota" className="ledger-control" type="text" inputMode="decimal" autoComplete="off" value={quotaDraft} placeholder={unlimited ? "Sin límite" : undefined} disabled={!quotaWritable || disabled}
            aria-invalid={Boolean(shownQuotaError)} aria-describedby={`quota-help${shownQuotaError ? " quota-error" : ""}`}
            onChange={(event) => { setQuotaDraft(event.target.value); setQuotaError(null); setQuotaSaved(false); }} />
          <p id="quota-help" className="ledger-hint">{quotaWritable ? (unlimited ? "Hoy no hay límite. Escribí unos MB y guardá solo si querés fijar uno (1 GB son 1.024 MB)." : `Cuánto espacio puede ocupar la aplicación (1 GB son 1.024 MB); ${sourceLabel}.`) : "Este límite está fijado fuera de esta pantalla y no se puede cambiar aquí."}</p>
          {shownQuotaError && <p id="quota-error" className="ledger-error" role="alert">{shownQuotaError}</p>}
        </div>
        <Button type="submit" variant="primary" disabled={disabled || !quotaWritable || !quotaDirty || Boolean(quotaInvalid)} aria-busy={disabled}>{disabled ? "Guardando…" : "Guardar límite"}</Button>
        {quotaWritable && !unlimited && <Button variant="secondary" disabled={disabled} onClick={() => void saveUnlimited()}>Sin límite</Button>}
        {quotaSaved && <p className="settings-success" role="status">Límite guardado</p>}
      </form>
    </Block>

    <details ref={advancedRef} className="ledger-disclosure settings-advanced">
      <summary>Avanzado</summary>
      <div className="settings-advanced-body">
        <section aria-labelledby="settings-tech-title" className="settings-subsection">
          <h3 id="settings-tech-title">Detalle técnico del almacenamiento</h3>
          <dl className="settings-summary">
            <div><dt>Uso lógico total</dt><dd>{BYTE_FORMAT(used)}</dd></div>
            <div><dt>Cuota efectiva</dt><dd>{BYTE_FORMAT(limit)}</dd></div>
            <div><dt>Disponible según cuota</dt><dd>{BYTE_FORMAT(left)}</dd></div>
            <div><dt>Disco disponible</dt><dd>{formatDiskBytes(storage.free_disk_bytes)}</dd></div>
            <div><dt>Margen de disco</dt><dd>{formatDiskBytes(storage.disk_margin_bytes)}</dd></div>
            <div><dt>Base de datos</dt><dd>{formatDiskBytes(storage.database_bytes)}</dd></div>
            <div><dt>WAL</dt><dd>{formatDiskBytes(storage.wal_bytes)}</dd></div>
            <div><dt>SHM</dt><dd>{formatDiskBytes(storage.shm_bytes)}</dd></div>
            <div><dt>Temporales</dt><dd>{formatDiskBytes(storage.temp_bytes)}</dd></div>
            <div><dt>SQLite</dt><dd>{formatDiskBytes(storage.sqlite_bytes)}</dd></div>
            <div><dt>Artefactos de historial</dt><dd>{BYTE_FORMAT(storage.history_artifact_bytes_exact)}</dd></div>
            <div><dt>Artefactos de corridas</dt><dd>{BYTE_FORMAT(storage.run_artifact_bytes_exact)}</dd></div>
          </dl>
          <p className="settings-note">El uso lógico incluye el historial, los artefactos de corridas y los datos heredados; no equivale al tamaño físico del archivo de base de datos.</p>
        </section>

        {history && <section aria-labelledby="settings-history-title" className="settings-subsection">
          <h3 id="settings-history-title">Fuentes de historial</h3>
          <div className="settings-history-list" role="group" aria-label="Fuentes de historial">
            {history.sources.map((source) => <section className="settings-history-source" key={source.sha256} aria-label={`${source.active ? "Activo" : "Inactivo"} · ${source.origin === "frozen" ? "Historial congelado" : "Historial importado"}`}>
              <div className="settings-source-heading"><h4>{source.active ? "Activo" : "Inactivo"} · {source.origin === "frozen" ? "Historial congelado" : "Historial importado"}</h4><p>{snapshotDescription(source)}</p></div>
              <dl className="settings-source-metrics"><div><dt>Sorteos</dt><dd>{source.draws}</dd></div><div><dt>Sorteos con ranking</dt><dd>{source.ranked_draws} de {source.draws}</dd></div></dl>
              <div className="settings-fingerprint"><span>SHA-256</span><code>{source.sha256}</code></div>
            </section>)}
          </div>
          <p className="settings-note">No se pueden elegir, borrar ni modificar fuentes desde esta pantalla. Los sorteos nuevos no generan rankings automáticamente.</p>
        </section>}

        <section aria-labelledby="settings-import-title" className="settings-subsection">
          <h3 id="settings-import-title">Importar historial</h3>
          {history && onChance ? <>
            <p className="settings-note">Al importar, se fusionan los sorteos y la fuente importada queda activa. Los orígenes de corridas anteriores conservan su huella; el historial guardado no se modifica.</p>
            <form className="settings-import-form" onSubmit={(event) => event.preventDefault()}>
              <div className="field">
                <label className="ledger-label" htmlFor="history-file">Importar historial JSON</label>
                <p id="history-file-hint" className="ledger-hint">La selección comienza la importación inmediatamente. Límite: 32 MiB. El archivo debe contener JSON válido.</p>
                <input ref={fileInputRef} id="history-file" aria-label="Elegir archivo de historial" aria-describedby="history-file-hint" type="file" accept=".json,application/json" disabled={disabled} onChange={(event) => void handleFileChange(event)} />
              </div>
            </form>
          </> : <p className="settings-note">La importación de historial solo funciona con Loteka Chance Express. Cambiá a esa lista para usarla.</p>}
          {importError && <div className="settings-message settings-error" role="alert"><p>{importError}</p>{ambiguousImport && <Button variant="secondary" onClick={() => void reconcileHistory()} disabled={disabled}>Actualizar historial</Button>}</div>}
          {confirmedImport && history && <div className="settings-success" role="status"><p>{confirmedImport}</p><p>Historial activo: {history.active.first_label} a {history.active.last_label}; sorteos con ranking: {history.active.ranked_draws} de {history.active.draws}.</p><p className="settings-fingerprint">SHA-256 <code>{history.active.sha256}</code></p></div>}
          {refreshError && <p className="settings-error" role="alert">{confirmedImport ? "No se pudo actualizar el historial después de la importación confirmada." : "No se pudo actualizar el historial."}</p>}
        </section>

        <section aria-labelledby="settings-origin-title" className="settings-subsection">
          <h3 id="settings-origin-title">Origen de los datos</h3>
          <dl className="settings-summary">
            <div><dt>Versión del código</dt><dd>{settings.sources.code_version}</dd></div>
            <div><dt>SHA-256 del historial</dt><dd className="settings-fingerprint"><code>{settings.sources.history_sha256}</code></dd></div>
            <div><dt>SHA-256 de rankings</dt><dd className="settings-fingerprint"><code>{settings.sources.rankings_sha256}</code></dd></div>
          </dl>
        </section>
      </div>
    </details>
  </div>;
}
