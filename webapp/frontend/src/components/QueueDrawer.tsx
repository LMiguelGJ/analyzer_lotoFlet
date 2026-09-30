import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import type { QueuePage } from "../api/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { useQueue } from "./QueueProvider";
import type { QueueAction } from "./QueueProvider";

const control = "h-control rounded-control border border-border-control px-3 font-mono text-sm hover:bg-field disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent";
const focusable = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

type Confirmation = QueueAction & { repeat?: boolean };

interface Props { open: boolean; onClose: () => void; trigger: React.RefObject<HTMLButtonElement | null> }
export function QueueDrawer({ open, onClose, trigger }: Props) {
  const { status, error, loading, offset, setOffset, refresh, requests, errors, busy, perform, check } = useQueue();
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const [confirm, setConfirm] = useState<Confirmation | null>(null);
  const confirmationTrigger = useRef<HTMLButtonElement | null>(null);
  const [notice, setNotice] = useState("");
  const noticeRef = useRef<HTMLParagraphElement>(null);
  const noticeExpired = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  useEffect(() => {
    if (!open) return;
    const root = document.getElementById("root");
    const wasInert = root?.hasAttribute("inert");
    root?.setAttribute("inert", "");
    panel.current?.focus();
    return () => {
      if (!wasInert) root?.removeAttribute("inert");
      trigger.current?.focus();
      setOffset(0);
    };
  }, [open, trigger, setOffset]);

  // A nested confirmation makes the drawer inert. Its trigger cannot regain
  // focus until the drawer becomes interactive again on cancellation.
  useEffect(() => {
    if (open && !confirm) document.getElementById("root")?.setAttribute("inert", "");
    panel.current?.toggleAttribute("inert", !!confirm);
    if (open && !confirm && confirmationTrigger.current) {
      const button = confirmationTrigger.current;
      confirmationTrigger.current = null;
      if (button.isConnected && !button.disabled) button.focus();
    }
  }, [open, confirm]);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (document.querySelector('[role="alertdialog"]')) return;
      if (event.key === "Escape") { event.preventDefault(); event.stopImmediatePropagation(); onClose(); return; }
      if (event.key !== "Tab") return;
      const nodes = Array.from(panel.current?.querySelectorAll<HTMLElement>(focusable) ?? []);
      if (!nodes.length) { event.preventDefault(); panel.current?.focus(); return; }
      const first = nodes[0], last = nodes[nodes.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [open, onClose]);

  useEffect(() => {
    if (!notice) return;
    noticeExpired.current = false;
    noticeRef.current?.focus();
    const timer = setTimeout(() => {
      noticeExpired.current = true;
      if (document.activeElement !== noticeRef.current) setNotice("");
    }, 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  function requestConfirmation(event: React.MouseEvent<HTMLButtonElement>, action: Confirmation) {
    confirmationTrigger.current = event.currentTarget;
    setConfirm(action);
  }

  function submit(action: QueueAction, repeat = false) {
    confirmationTrigger.current = null;
    setConfirm(null);
    setNotice("Enviando solicitud; resultado todavía no confirmado.");
    void perform(action, repeat).then((outcome) => {
      if (!alive.current) return;
      if (outcome === "accepted") setNotice(repeat ? action.kind === "start" ? "Inicio reenviado; esperando el estado del servidor." : "Solicitud de cancelación reenviada; cancelación aún no confirmada." :
        action.kind === "start" ? "Inicio solicitado. Esperando la cola actualizada." : "Solicitud de cancelación enviada. Esperando el estado del servidor.");
      if (outcome === "uncertain") setNotice("No se confirmó si el servidor recibió la solicitud. Comprobá el estado antes de repetirla.");
      if (outcome === "rejected") setNotice("La solicitud fue rechazada. Comprobá el estado actualizado del experimento.");
    });
  }

  if (!open) return null;
  const pageReady = status && status.pending.offset === offset && status.held.offset === offset;
  const row = (id: string, kind: "active" | "pending" | "held") => (
    <li key={`${kind}-${id}`} className="border-t border-border py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link to={`/experimentos/${encodeURIComponent(id)}`} onClick={onClose} className="min-w-0 break-all text-accent underline" aria-label={`Inspeccionar ${id}`}>{id}</Link>
        <div className="flex gap-2">
          {kind === "held" && <button className={control} type="button" disabled={!!busy || !!requests[id]} onClick={() => submit({ id, kind: "start" })} aria-label={`Iniciar ${id}`}>Iniciar</button>}
          <button className={control} type="button" disabled={!!busy || !!requests[id]} onClick={(event) => requestConfirmation(event, { id, kind: "cancel" })} aria-label={`Cancelar ${id}`}>Cancelar</button>
        </div>
      </div>
      {requests[id] && <>
        <p className="mt-1 text-sm text-text-secondary">{requests[id].terminal ? "Estado final confirmado; esperando que se actualice esta página." : requests[id].kind === "cancel" ? requests[id].outcome === "resent" ? "Solicitud reenviada; cancelación aún no confirmada." : requests[id].outcome === "uncertain" ? "Solicitud original no confirmada; cancelación aún no confirmada." : "Solicitud enviada; cancelación aún no confirmada." : requests[id].outcome === "uncertain" ? "Inicio original no confirmado; comprobá el estado." : "Inicio solicitado; esperando estado actualizado."}</p>
        {!requests[id].terminal && requests[id].outcome !== "sending" && <div className="mt-2 flex flex-wrap gap-2">
          <button className={control} type="button" disabled={!!busy || !!requests[id].checking} onClick={() => void check(id)} aria-label={`Comprobar estado ${id}`}>Comprobar estado</button>
          {requests[id].kind === "cancel" && (requests[id].checkedStatus === "pending" || requests[id].checkedStatus === "running" || requests[id].checkedStatus === "held") && <button className={control} type="button" disabled={!!busy} onClick={(event) => requestConfirmation(event, { id, kind: "cancel", repeat: true })} aria-label={`Reenviar cancelación ${id}`}>Reenviar cancelación</button>}
          {requests[id].kind === "start" && requests[id].checkedStatus === "held" && <button className={control} type="button" disabled={!!busy} onClick={(event) => requestConfirmation(event, { id, kind: "start", repeat: true })} aria-label={`Reintentar inicio ${id}`}>Reintentar inicio</button>}
        </div>}
      </>}
      {errors[id] && <p role="alert" className="mt-1 text-sm text-text">{errors[id]}</p>}
    </li>
  );
  const section = (name: string, page: QueuePage | undefined, kind: "pending" | "held") => <section className="mt-6" aria-label={name}>
    <h3 className="text-lg font-semibold">{name} · {page?.total ?? "—"}</h3>
    {page && page.offset === offset ? <>
      <p className="text-sm text-text-secondary">{page.count ? `${page.offset + 1}–${page.offset + page.count} de ${page.total}` : `No hay elementos en esta página (${page.total} en total).`}</p>
      <ul className="mt-2">{page.items.map((id) => row(id, kind))}</ul>
    </> : <p className="text-sm text-text-secondary">Actualizando página…</p>}
  </section>;

  return createPortal(<>
    <div className="fixed inset-0 z-40 bg-black/60" onClick={onClose} aria-hidden="true" />
    <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} className="fixed inset-y-0 right-0 z-40 w-full max-w-lg overflow-y-auto border-l border-border-control bg-surface p-6 text-text shadow-2xl focus:outline-none">
      <div className="flex items-center justify-between gap-3"><h2 id={titleId} className="font-heading text-2xl italic">Cola de experimentos</h2><button type="button" className={control} onClick={onClose}>Cerrar cola</button></div>
      <p className="mt-2 text-sm text-text-secondary">Un cálculo a la vez. La cola y los retenidos se consultan por páginas independientes; pueden cambiar entre consultas.</p>
      {error && <p role="status" className="mt-4 text-sm text-text-secondary">{error === "network" ? "No se pudo contactar al servidor local. El cálculo podría continuar; se muestra el último estado conocido." : "No se pudo actualizar la cola; se muestra el último estado conocido."}</p>}
      <button type="button" className={`${control} mt-3`} onClick={refresh}>Reintentar cola</button>
      {loading && !status && <p role="status" className="mt-4">Consultando cola…</p>}
      {notice && <p ref={noticeRef} tabIndex={-1} role="status" onBlur={() => { if (noticeExpired.current) setNotice(""); }} className="mt-4 text-sm text-accent focus:outline-none">{notice}</p>}
      {status?.last_failure && <p role="status" className="mt-4 text-sm text-text-secondary">Problema reciente en {status.last_failure.experiment_id}: {status.last_failure.persisted ? "El estado de fallo se guardó." : "El estado de fallo no se pudo confirmar en el almacenamiento."} Consultá el detalle al reconectar.</p>}
      <section className="mt-6" aria-label="Activo"><h3 className="text-lg font-semibold">Activo</h3>{status?.active_id ? <ul>{row(status.active_id, "active")}</ul> : <p className="text-sm text-text-secondary">No hay experimento activo en la última consulta.</p>}</section>
      {section("Pendientes", pageReady ? status.pending : undefined, "pending")}
      {section("Retenidos tras reinicio", pageReady ? status.held : undefined, "held")}
      {status && <div className="mt-6 flex flex-wrap items-center gap-3 font-mono text-sm"><button type="button" className={control} disabled={offset === 0} onClick={() => setOffset(offset - 20)}>Anterior cola</button><span>Página {Math.floor(offset / 20) + 1}</span><button type="button" className={control} disabled={offset + 20 >= Math.max(status.pending.total, status.held.total)} onClick={() => setOffset(offset + 20)}>Siguiente cola</button></div>}
    </div>
    <ConfirmDialog open={!!confirm} restoreFocus={false} title={confirm?.repeat ? confirm.kind === "start" ? "¿Reintentar inicio?" : "¿Reenviar cancelación?" : "¿Cancelar experimento?"} description={confirm?.repeat ? confirm.kind === "start" ? "El estado retenido se comprobó. El servidor rechazará un inicio duplicado si el trabajo ya entró en la cola." : "La cancelación original no está confirmada. El estado aún admite cancelación; reenviarla puede devolver un conflicto si terminó entretanto." : "Se conservarán los resultados ya terminados. El cálculo actual no se guardará como completo y lo restante no se ejecutará. La cancelación se confirmará al actualizar el estado; este experimento no se puede reanudar."} confirmLabel={confirm?.repeat ? confirm.kind === "start" ? "Confirmar reintento" : "Confirmar reenvío" : "Confirmar cancelación"} onConfirm={() => { if (confirm) submit(confirm, !!confirm.repeat); }} onCancel={() => setConfirm(null)} />
  </>, document.body);
}
