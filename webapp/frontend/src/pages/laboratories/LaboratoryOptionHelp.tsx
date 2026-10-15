import { useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { OPTION_HELP } from "./option-help";
import type { HelpKind, OptionExplanation } from "./option-help";

interface Props { kind: HelpKind; value: string; open: boolean; onOpen: () => void; onClose: () => void }

function Explanation({ what, effect, example }: OptionExplanation) {
  return <><p>{what}</p><p><strong>En qué afecta:</strong> {effect}</p><p><strong>Ejemplo:</strong> {example}</p></>;
}

export function LaboratoryOptionHelp({ kind, value, open, onOpen, onClose }: Props) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const [comparing, setComparing] = useState(false);
  const group = OPTION_HELP[kind];
  const selected = group.options.find((option) => option.value === value)!;

  function close(restoreFocus: boolean) {
    setComparing(false);
    onClose();
    if (restoreFocus) trigger.current?.focus();
  }

  useLayoutEffect(() => {
    if (!open) return;
    const anchor = trigger.current!;
    const content = panel.current!;
    function position() {
      const rect = anchor.getBoundingClientRect();
      const box = content.getBoundingClientRect();
      const edge = 16;
      const below = rect.bottom + 8;
      content.style.left = `${Math.max(edge, Math.min(rect.left, window.innerWidth - box.width - edge))}px`;
      content.style.top = `${below + box.height <= window.innerHeight - edge ? below : Math.max(edge, rect.top - box.height - 8)}px`;
    }
    position();
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [open, comparing, value]);

  useLayoutEffect(() => {
    if (!open) return;
    panel.current?.focus({ preventScroll: true });
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    function dismiss(event: PointerEvent) {
      if (event.target instanceof Node && !panel.current?.contains(event.target) && !trigger.current?.contains(event.target)) close(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape" && !event.defaultPrevented) {
        event.preventDefault();
        close(true);
      }
    }
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [open, onClose]);

  return <>
    <button ref={trigger} type="button" className="lab-option-help-trigger"
      aria-label={`Ayuda sobre ${group.label.toLowerCase()}`} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => { if (open) close(false); else { setComparing(false); onOpen(); } }}><span aria-hidden="true">ⓘ</span></button>
    {open && createPortal(<div ref={panel} id={id} role="dialog" aria-modal="false" aria-labelledby={`${id}-title`} aria-describedby={`${id}-intro`}
      tabIndex={-1} className="lab-option-popover">
      <div className="lab-option-popover-heading">
        <h3 id={`${id}-title`}>{comparing ? group.title : selected.label}</h3>
        <button type="button" className="lab-option-help-close" onClick={() => close(true)} aria-label="Cerrar ayuda"><span aria-hidden="true">×</span></button>
      </div>
      <p id={`${id}-intro`} className="lab-option-help-intro">{group.introduction}</p>
      <div ref={body} className="lab-option-help-content">{comparing ? <ul className="lab-option-comparison">{group.options.map((option) => <li key={option.value} aria-current={option.value === value ? "true" : undefined}>
        <h4>{option.label}</h4>{option.value === value && <span className="lab-option-current">Seleccionado</span>}
        <Explanation {...option} />
      </li>)}</ul> : <Explanation {...selected} />}</div>
      <button type="button" className="lab-option-help-compare" onClick={() => { setComparing((current) => !current); body.current?.scrollTo?.(0, 0); }}>
        {comparing ? "Volver a la opción elegida" : "Comparar opciones"}
      </button>
    </div>, document.body)}
  </>;
}
