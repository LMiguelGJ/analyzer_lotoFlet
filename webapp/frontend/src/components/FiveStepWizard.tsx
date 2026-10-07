import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

export function useFiveStepWizard(count: number, validate: (step: number) => boolean) {
  const [step, setStep] = useState(0);
  const back = useCallback(() => setStep((current) => Math.max(0, current - 1)), []);
  const next = useCallback(() => {
    if (step < count - 1 && validate(step)) setStep(step + 1);
  }, [count, step, validate]);
  const goTo = useCallback((value: number) => setStep(Math.max(0, Math.min(count - 1, value))), [count]);
  return { step, next, back, goTo };
}

export function FiveStepWizard({
  steps, activeStep, onNext, onBack, busy = false, children,
}: {
  steps: readonly { title: string; description: string }[];
  activeStep: number;
  onNext: () => void;
  onBack: () => void;
  busy?: boolean;
  children: ReactNode;
}) {
  const current = steps[activeStep];
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
    headingRef.current?.scrollIntoView?.({ block: "start" });
  }, [activeStep]);
  return <>
    <section className="m3-wizard" aria-label="Asistente para crear una simulación">
      <div className="m3-wizard-progress" role="progressbar" aria-label={`Paso ${activeStep + 1} de ${steps.length}`} aria-valuenow={activeStep + 1} aria-valuemin={1} aria-valuemax={steps.length}>
        <span style={{ width: `${((activeStep + 1) / steps.length) * 100}%` }} />
      </div>
      <p className="m3-wizard-step">Paso {activeStep + 1} de {steps.length}</p>
      <h2 ref={headingRef} tabIndex={-1} className="m3-wizard-title">{current.title}</h2>
      <p className="field-help">{current.description}</p>
      <div className="m3-wizard-actions">
        <button type="button" className="btn btn-outlined" disabled={activeStep === 0 || busy} onClick={onBack}>Atrás</button>
        {activeStep < steps.length - 1
          ? <button type="button" className="btn btn-primary" disabled={busy} onClick={onNext}>Siguiente</button>
          : <span className="m3-wizard-step">Listo para confirmar abajo</span>}
      </div>
    </section>
    {children}
  </>;
}
