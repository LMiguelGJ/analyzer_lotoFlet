import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

/**
 * Accessible confirmation modal (UX51): focus trap, Escape closes, focus
 * returns to the triggering control on close. Built with a manual focus
 * trap rather than the native <dialog> element so behavior is deterministic
 * under jsdom and across browsers; open/close is fully controlled by the
 * parent (no internal state).
 *
 * Rendered via a portal into document.body, with #root marked `inert` while
 * open: that removes every other element from the Tab order and from click
 * handling, so the trap holds for Tab starting from any element - not just
 * from the two buttons this component currently renders. The onCancel
 * callback is read from a ref inside the keydown effect (which depends only
 * on `open`), so a parent re-render that passes a brand-new inline
 * `onCancel` closure never re-runs the open/focus effect and never steals
 * focus back to the first control.
 *
 * Deletion callers tie this to the backend's confirm_id contract by passing
 * the target resource id as `onConfirm`'s closure; this component itself
 * stays generic.
 */

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  /** Let a containing modal restore focus after removing its own inert state. */
  restoreFocus?: boolean;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Eliminar",
  cancelLabel = "Cancelar",
  onConfirm,
  onCancel,
  restoreFocus = true,
}: ConfirmDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;

  useEffect(() => {
    if (!open) return;

    const appRoot = document.getElementById("root");
    // Native inert blurs a focused descendant, so capture before isolating it.
    if (restoreFocus) previouslyFocused.current = document.activeElement as HTMLElement | null;
    appRoot?.setAttribute("inert", "");
    const node = dialogRef.current;
    const firstFocusable = node?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    firstFocusable?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancelRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusables = Array.from(node?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? []);
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      appRoot?.removeAttribute("inert");
      if (restoreFocus && previouslyFocused.current && previouslyFocused.current !== document.body &&
          previouslyFocused.current.isConnected && !previouslyFocused.current.closest("[inert]")) {
        previouslyFocused.current.focus();
      }
    };
  }, [open, restoreFocus]);

  if (!open) return null;

  return createPortal(
    <div className="confirm-dialog-scrim fixed inset-0 z-50 flex items-center justify-center">
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="confirm-dialog-panel w-full max-w-md p-6 text-text"
      >
        <h2 id={titleId} className="section-header break-words">
          {title}
        </h2>
        <p id={descriptionId} className="mb-6 break-words text-sm leading-relaxed text-text-secondary">
          {description}
        </p>
        <div className="flex flex-wrap justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="btn btn-secondary"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="btn btn-destructive"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
