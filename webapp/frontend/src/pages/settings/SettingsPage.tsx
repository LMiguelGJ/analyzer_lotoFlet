import { useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { ApiError, NetworkError } from "../../api/client";
import { getHistory, importHistory } from "../../api/history";
import { getSettings, updateSettings } from "../../api/settings";
import type { HistoryImportResponse, HistoryResponse, HistorySnapshot, SettingsResponse } from "../../api/types";
import { Block, SectionHeader } from "../../components/ui/Block";
import { Button } from "../../components/ui/Controls";
import { ErrorBanner, Loading } from "../../components/ui/Feedback";
import { formatDiskBytes, formatExactBytes, quotaInputError, remainingBytes } from "./settings-model";
import "./settings.css";

const MAX_IMPORT_BYTES = 32 * 1024 * 1024;
const BYTE_FORMAT = (value: string) => formatExactBytes(value);

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

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [quotaDraft, setQuotaDraft] = useState("");
  const [quotaError, setQuotaError] = useState<string | null>(null);
  const [quotaSaved, setQuotaSaved] = useState(false);
  const [mutationBusy, setMutationBusy] = useState(false);
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
  const quotaInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async (initial = false) => {
    readController.current?.abort();
    const controller = new AbortController();
    readController.current = controller;
    const sequence = ++readSequence.current;
    const epoch = mutationEpoch.current;
    if (initial) { setLoading(true); setLoadError(null); }
    try {
      const [nextHistory, nextSettings] = await Promise.all([
        getHistory({ signal: controller.signal }), getSettings({ signal: controller.signal }),
      ]);
      if (controller.signal.aborted || sequence !== readSequence.current || epoch !== mutationEpoch.current) return false;
      setHistory(nextHistory);
      setSettings(nextSettings);
      setQuotaDraft(nextSettings.quota.effective_bytes);
      setQuotaError(null);
      setQuotaSaved(false);
      setLoadError(null);
      setRefreshError(false);
      return true;
    } catch {
      if (controller.signal.aborted || sequence !== readSequence.current || epoch !== mutationEpoch.current) return false;
      if (initial) setLoadError("No se pudieron cargar los ajustes y el historial.");
      else setRefreshError(true);
      return false;
    } finally {
      if (!controller.signal.aborted && sequence === readSequence.current && epoch === mutationEpoch.current && initial) setLoading(false);
    }
  }, []);

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

  async function saveQuota(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busyGuard.current || !settings?.quota.writable) return;
    const validation = quotaInputError(quotaDraft);
    setQuotaError(validation);
    setQuotaSaved(false);
    if (validation) return;
    const controller = beginMutation();
    try {
      const saved = await updateSettings(quotaDraft, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setSettings(saved);
      setQuotaDraft(saved.quota.effective_bytes);
      setQuotaError(null);
      setQuotaSaved(true);
    } catch (error) {
      if (controller.signal.aborted) return;
      setQuotaError(apiMessage(error, error instanceof NetworkError ? "No se pudo contactar al servidor local. No se confirmó el cambio de cuota." : "No se pudo guardar la cuota."));
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
      const [nextHistory, nextSettings] = await Promise.all([
        getHistory({ signal: refreshController.signal }), getSettings({ signal: refreshController.signal }),
      ]);
      if (!mounted.current || controller.signal.aborted || refreshController.signal.aborted || sequence !== readSequence.current || epoch !== mutationEpoch.current) return false;
      setHistory(nextHistory);
      setSettings(nextSettings);
      setQuotaDraft(nextSettings.quota.effective_bytes);
      setQuotaError(null);
      setQuotaSaved(false);
      return true;
    } catch {
      return false;
    }
  }

  const inputError = quotaError ?? (quotaDraft ? quotaInputError(quotaDraft) : "Ingresá una cuota en bytes.");
  const disabled = mutationBusy;

  if (loading) return <Loading label="Cargando ajustes e historial" rows={4} className="settings-loading" />;
  if (loadError || !settings || !history) return <ErrorBanner cause={loadError ?? "No se pudieron cargar los datos."} recovery="Podés volver a intentar la lectura del servidor." actionLabel="Reintentar" onAction={() => void refresh(true)} />;

  const storage = settings.storage;
  const quotaWritable = settings.quota.writable;
  const left = remainingBytes(settings.quota.effective_bytes, storage.admission_logical_bytes_exact);
  const sourceLabel = settings.quota.source === "environment" || settings.quota.source === "env" ? "entorno" : settings.quota.source;

  return <div className="settings-page">
    <div className="settings-intro">
      <p>Revisá el espacio local y las fuentes de datos que usan las corridas.</p>
    </div>
    <Block aria-labelledby="settings-storage-title" className="settings-section">
      <SectionHeader id="settings-storage-title" title="Almacenamiento" />
      {storage.warning && <p className="settings-warning" role="status">Poco margen de almacenamiento o de disco</p>}
      <dl className="settings-summary">
        <div><dt>Uso lógico total</dt><dd>{BYTE_FORMAT(storage.admission_logical_bytes_exact)}</dd></div>
        <div><dt>Cuota efectiva</dt><dd>{BYTE_FORMAT(settings.quota.effective_bytes)}</dd></div>
        <div><dt>Disponible según cuota</dt><dd>{BYTE_FORMAT(left)}</dd></div>
        <div><dt>Disco disponible</dt><dd>{formatDiskBytes(storage.free_disk_bytes)}</dd></div>
        <div><dt>Margen de disco</dt><dd>{formatDiskBytes(storage.disk_margin_bytes)}</dd></div>
        <div><dt>Base de datos</dt><dd>{formatDiskBytes(storage.database_bytes)}</dd></div>
        <div><dt>WAL</dt><dd>{formatDiskBytes(storage.wal_bytes)}</dd></div>
      </dl>
      <p className="settings-note">El uso lógico incluye el historial, los artefactos de corridas y los datos heredados; no equivale al tamaño físico del archivo de base de datos.</p>
      <details className="ledger-disclosure settings-details">
        <summary>Detalles de almacenamiento</summary>
        <dl className="settings-summary settings-details-list">
          <div><dt>SHM</dt><dd>{formatDiskBytes(storage.shm_bytes)}</dd></div>
          <div><dt>Temporales</dt><dd>{formatDiskBytes(storage.temp_bytes)}</dd></div>
          <div><dt>SQLite</dt><dd>{formatDiskBytes(storage.sqlite_bytes)}</dd></div>
          <div><dt>Artefactos de historial</dt><dd>{BYTE_FORMAT(storage.history_artifact_bytes_exact)}</dd></div>
          <div><dt>Artefactos de corridas</dt><dd>{BYTE_FORMAT(storage.run_artifact_bytes_exact)}</dd></div>
        </dl>
      </details>
      <form className="settings-quota-form" onSubmit={(event) => void saveQuota(event)} noValidate>
        <div className="field">
          <label className="ledger-label" htmlFor="settings-quota">Cuota en bytes</label>
          <input ref={quotaInputRef} id="settings-quota" className="ledger-control" type="text" inputMode="numeric" autoComplete="off" value={quotaDraft} disabled={!quotaWritable || disabled} aria-invalid={Boolean(inputError)} aria-describedby="quota-help quota-error" onChange={(event) => { setQuotaDraft(event.target.value); setQuotaError(null); setQuotaSaved(false); }} />
          <p id="quota-help" className="ledger-hint">Valor exacto en bytes. Configuración: {sourceLabel}{quotaWritable ? "." : "; solo lectura, definida fuera de esta pantalla."}</p>
          {inputError && <p id="quota-error" className="ledger-error" role="alert">{inputError}</p>}
          {!quotaWritable && <p className="ledger-hint">La cuota está en modo de solo lectura.</p>}
        </div>
        <Button type="submit" variant="primary" disabled={disabled || !quotaWritable || Boolean(inputError)} aria-busy={disabled}>{disabled ? "Guardando…" : "Guardar cuota"}</Button>
        {quotaSaved && <p className="settings-success" role="status">Cuota guardada</p>}
      </form>
    </Block>

    <Block aria-labelledby="settings-history-title" className="settings-section">
      <SectionHeader id="settings-history-title" title="Fuentes de historial" />
      <p className="settings-note">Al importar, se fusionan los sorteos y la fuente importada queda activa. Los orígenes de corridas anteriores conservan su huella; el historial guardado no se modifica.</p>
      <div className="settings-history-list" aria-label="Fuentes de historial">
        {history.sources.map((source) => <section className="settings-history-source" key={source.sha256} aria-label={`${source.active ? "Activo" : "Inactivo"} · ${source.origin === "frozen" ? "Historial congelado" : "Historial importado"}`}>
          <div className="settings-source-heading"><h3>{source.active ? "Activo" : "Inactivo"} · {source.origin === "frozen" ? "Historial congelado" : "Historial importado"}</h3><p>{snapshotDescription(source)}</p></div>
          <dl className="settings-source-metrics"><div><dt>Sorteos</dt><dd>{source.draws}</dd></div><div><dt>Sorteos con ranking</dt><dd>{source.ranked_draws} de {source.draws}</dd></div></dl>
          <div className="settings-fingerprint"><span>SHA-256</span><code>{source.sha256}</code></div>
        </section>)}
      </div>
      <p className="settings-note">No se pueden elegir, borrar ni modificar fuentes desde esta pantalla. Los sorteos nuevos no generan rankings automáticamente.</p>
      <form className="settings-import-form" onSubmit={(event) => event.preventDefault()}>
        <div className="field">
          <label className="ledger-label" htmlFor="history-file">Importar historial JSON</label>
          <p id="history-file-hint" className="ledger-hint">La selección comienza la importación inmediatamente. Límite: 32 MiB. El archivo debe contener JSON válido.</p>
          <input ref={fileInputRef} id="history-file" aria-label="Elegir archivo de historial" aria-describedby="history-file-hint" type="file" accept=".json,application/json" disabled={disabled} onChange={(event) => void handleFileChange(event)} />
        </div>
      </form>
      {importError && <div className="settings-message settings-error" role="alert"><p>{importError}</p>{ambiguousImport && <Button variant="secondary" onClick={() => void reconcileHistory()} disabled={disabled}>Actualizar historial</Button>}</div>}
      {confirmedImport && <div className="settings-success" role="status"><p>{confirmedImport}</p><p>Historial activo: {history.active.first_label} a {history.active.last_label}; sorteos con ranking: {history.active.ranked_draws} de {history.active.draws}.</p><p className="settings-fingerprint">SHA-256 <code>{history.active.sha256}</code></p></div>}
      {refreshError && <p className="settings-error" role="alert">{confirmedImport ? "No se pudo actualizar el historial después de la importación confirmada." : "No se pudo actualizar el historial."}</p>}
    </Block>
  </div>;
}
