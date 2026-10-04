import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import type { QueuePage } from "../api/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { Loading } from "./ui";
import { useQueue } from "./QueueProvider";
import type { QueueAction } from "./QueueProvider";

const control = "btn btn-secondary";
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
  const row = (id: string, kind: "active" | "pending" | "held") => {
    const request = requests[id];
    const locked = !!request;
    const uncertain = request?.outcome === "uncertain" || request?.outcome === "resent";
    const resendCancel = request?.kind === "cancel" && ["pending", "running", "held"].includes(request.checkedStatus ?? "");
    const retryStart = request?.kind === "start" && request.checkedStatus === "held";
    const canResend = !!request && !request.terminal && (resendCancel || retryStart);
    const canCheck = !!request && !request.terminal && request.outcome !== "sending";
    // Three lanes: pending (request in flight), uncertain (may have arrived), confirmed (known state).
    const lane = !request ? "confirmed" : request.outcome === "sending" ? "pending" : uncertain ? "uncertain" : "confirmed";
    const statusCopy = !request
      ? kind === "active" ? "En curso" : kind === "pending" ? "Esperando" : "Detenido"
      : request.terminal
        ? "Estado final confirmado; esta fila espera la próxima consulta."
        : lane === "pending"
          ? "Actualizando…"
          : lane === "uncertain"
            ? "La solicitud puede haber llegado; comprobá el estado desde la cola antes de reintentar."
            : request.kind === "cancel"
              ? "Solicitud recibida; esperando confirmación del estado."
              : "Inicio solicitado; esperando confirmación del estado.";
    // One primary action per state; everything else is secondary.
    const primaryIsCheck = canCheck && !canResend;
    const startClass = !locked && kind === "held" ? "btn btn-primary" : control;
    const cancelClass = !locked && kind !== "held" ? "btn btn-primary" : control;
    return <li key={`${kind}-${id}`} className="queue-row py-3" data-lane={lane}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <Link to={`/experimentos/${encodeURIComponent(id)}`} onClick={onClose} className="break-all font-mono text-sm link" aria-label={`Inspeccionar ${id}`}>{id}</Link>
          <p className="mt-1 text-sm text-text-secondary">{statusCopy}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {kind === "held" && <button className={startClass} type="button" disabled={!!busy || locked} onClick={() => submit({ id, kind: "start" })} aria-label={`Iniciar ${id}`}>Iniciar</button>}
          <button className={cancelClass} type="button" disabled={!!busy || locked} onClick={(event) => requestConfirmation(event, { id, kind: "cancel" })} aria-label={`Cancelar ${id}`}>Cancelar</button>
          {canCheck && <button className={primaryIsCheck ? "btn btn-primary" : control} type="button" disabled={!!busy || !!request.checking} onClick={() => void check(id)} aria-label={`Comprobar estado ${id}`}>{request.checking ? "Comprobando…" : "Comprobar estado"}</button>}
          {canResend && <button className="btn btn-primary" type="button" disabled={!!busy} onClick={(event) => requestConfirmation(event, { id, kind: request.kind, repeat: true })} aria-label={request.kind === "cancel" ? `Reenviar cancelación ${id}` : `Reintentar inicio ${id}`}>{request.kind === "cancel" ? "Reenviar cancelación" : "Reintentar inicio"}</button>}
        </div>
      </div>
      {errors[id] && errors[id] !== statusCopy && <p role="alert" className="mt-2 text-sm text-text">{errors[id]}</p>}
    </li>;
  };
  const section = (name: string, page: QueuePage | undefined, kind: "pending" | "held") => <section className="queue-section mt-6" aria-label={name}>
    <h3 className="section-header">{name} · {page?.total ?? "—"}</h3>
    {page && page.offset === offset ? <>
      <p className="text-sm text-text-secondary">{page.count ? `${page.offset + 1}–${page.offset + page.count} de ${page.total}` : `No hay elementos en esta página (${page.total} en total).`}</p>
      <ul className="mt-2">{page.items.map((id) => row(id, kind))}</ul>
    </> : <p className="text-sm text-text-secondary">{error ? "Sin datos de esta página." : "Actualizando…"}</p>}
  </section>;

  return createPortal(<>
    <div className="fixed inset-0 z-40 bg-black/60" onClick={onClose} aria-hidden="true" />
    <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} className="fixed inset-y-0 right-0 z-40 w-full max-w-lg overflow-y-auto border-l border-border-control bg-surface p-6 text-text focus:outline-none">
      <div className="flex items-center justify-between gap-3"><h2 id={titleId} className="font-heading text-2xl">Cola de experimentos</h2><button type="button" className={control} onClick={onClose}>Cerrar cola</button></div>
      <details className="mt-2 border-y border-border py-3"><summary className="disclosure-summary">Detalles técnicos</summary>
        <p className="mt-3 text-sm text-text-secondary">La cola ejecuta un cálculo a la vez y consulta los trabajos en páginas independientes de 20. El estado puede cambiar entre consultas. Los trabajos detenidos solo se pueden iniciar después de comprobar su estado; si una solicitud no se confirma, comprobalo antes de reenviarla.</p>
      </details>
      {error && <div role="alert" className="mt-4 border-y border-border py-3 text-sm text-text-secondary"><p>{error === "network" ? "Sin conexión con el servidor. No se pudo comprobar la cola." : "No se pudo comprobar la cola por un error del servidor."}</p><p className="mt-1">El cálculo puede continuar en el servidor; comprobá el estado desde la cola con «Reintentar cola».</p><p className="mt-1">Se conserva el último estado conocido.</p></div>}
      <button type="button" className={`${control} mt-3`} onClick={refresh}>Reintentar cola</button>
      {loading && !status && !error && <Loading rows={3} label="Consultando cola…" className="mt-4" />}
      {notice && <p ref={noticeRef} tabIndex={-1} role="status" onBlur={() => { if (noticeExpired.current) setNotice(""); }} className="mt-4 text-sm text-accent focus:outline-none">{notice}</p>}
      {status?.last_failure && <p role="status" className="mt-4 text-sm text-text-secondary">Problema reciente en {status.last_failure.experiment_id}: {status.last_failure.persisted ? "El estado de fallo se guardó." : "El estado de fallo no se pudo confirmar en el almacenamiento."} Consultá el detalle al reconectar.</p>}
      <section className="queue-section mt-6" aria-label="En curso"><h3 className="section-header">En curso</h3>{status?.active_id ? <ul>{row(status.active_id, "active")}</ul> : <p className="text-sm text-text-secondary">No hay experimento activo en la última consulta.</p>}</section>
      {section("Esperando", pageReady ? status.pending : undefined, "pending")}
      {section("Detenido", pageReady ? status.held : undefined, "held")}
      {status && <div className="mt-6 flex flex-wrap items-center gap-3 text-sm"><button type="button" className={control} disabled={offset === 0} onClick={() => setOffset(offset - 20)}>Anterior cola</button><span>Página {Math.floor(offset / 20) + 1}</span><button type="button" className={control} disabled={offset + 20 >= Math.max(status.pending.total, status.held.total)} onClick={() => setOffset(offset + 20)}>Siguiente cola</button></div>}
    </div>
    <ConfirmDialog open={!!confirm} restoreFocus={false} title={confirm?.repeat ? confirm.kind === "start" ? `¿Reintentar el inicio de ${confirm.id}?` : `¿Reenviar la cancelación de ${confirm.id}?` : `¿Cancelar el experimento ${confirm?.id ?? ""}?`} description={confirm?.repeat ? confirm.kind === "start" ? `El estado detenido de ${confirm.id} se comprobó. El inicio se solicitará de nuevo y todavía deberá confirmarse.` : `La solicitud anterior de ${confirm.id} no está confirmada. Reenviar puede producir un conflicto si terminó entretanto.` : `Se conservarán los resultados ya terminados de ${confirm?.id ?? "este experimento"}. El cálculo actual no se guardará como completo y lo restante no se ejecutará. La cancelación deberá confirmarse al comprobar el estado.`} confirmLabel={confirm?.repeat ? confirm.kind === "start" ? "Confirmar reintento" : "Confirmar reenvío" : "Confirmar cancelación"} onConfirm={() => { if (confirm) submit(confirm, !!confirm.repeat); }} onCancel={() => setConfirm(null)} />
  </>, document.body);
}
