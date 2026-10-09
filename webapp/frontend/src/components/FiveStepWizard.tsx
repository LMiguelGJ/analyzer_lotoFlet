import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

export function useFiveStepWizard(count: number, validate: (step: number) => boolean) {
  const [step, setStep] = useState(0);
  const [maxReachableStep, setMaxReachableStep] = useState(0);
  const back = useCallback(() => setStep((current) => Math.max(0, current - 1)), []);
  const next = useCallback(() => {
    if (step < count - 1 && validate(step)) {
      setStep(step + 1);
      setMaxReachableStep((current) => Math.max(current, step + 1));
    }
  }, [count, step, validate]);
  const goTo = useCallback((value: number) => {
    const target = Math.max(0, Math.min(count - 1, value));
    setStep(target);
    setMaxReachableStep((current) => Math.max(current, target));
  }, [count]);
  return { step, maxReachableStep, next, back, goTo };
}

export function FiveStepWizard({
  steps, activeStep, onNext, onBack, onSelectStep, maxReachableStep = activeStep, busy = false, children,
}: {
  steps: readonly { title: string; description: string }[];
  activeStep: number;
  onNext: () => void;
  onBack: () => void;
  onSelectStep?: (index: number) => void;
  maxReachableStep?: number;
  busy?: boolean;
  children: ReactNode;
}) {
  const current = steps[activeStep];
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
    headingRef.current?.scrollIntoView?.({ block: "start" });
  }, [activeStep]);
  return <div className="m3-wizard-frame">
    <section className="m3-wizard" aria-label="Asistente para crear una simulación">
      <div className="wizard-progress-sr" role="progressbar" aria-label={`Paso ${activeStep + 1} de ${steps.length}`} aria-valuenow={activeStep + 1} aria-valuemin={1} aria-valuemax={steps.length} />
      <nav className="wizard-stepper" aria-label="Pasos de la simulación">
        <ol>{steps.map((item, index) => {
          const reachable = index <= maxReachableStep;
          const label = ["Estrategia", "Reglas", "Alcance", "Capital y meta", "Revisión"][index] ?? item.title;
          return <li key={`${index}-${item.title}`}>
            <button type="button" className={`wizard-step${activeStep === index ? " is-current" : reachable ? " is-reached" : " is-pending"}`} aria-current={activeStep === index ? "step" : undefined}
              aria-disabled={!reachable || busy} tabIndex={!reachable || busy ? -1 : undefined}
              disabled={!reachable || busy} onClick={() => onSelectStep?.(index)}>
              <span className="wizard-step-number">{index + 1}</span><span className="wizard-step-label">{label}</span>
            </button>
          </li>;
        })}</ol>
      </nav>
      <p className="m3-wizard-step">Paso {activeStep + 1} de {steps.length}</p>
      <h2 ref={headingRef} tabIndex={-1} className="m3-wizard-title">{current.title}</h2>
      <p className="field-help">{current.description}</p>
    </section>
    <div className="wizard-content">{children}</div>
    <div className="m3-wizard-actions" role="group" aria-label="Navegación del asistente">
      <button type="button" className="btn btn-secondary" disabled={activeStep === 0 || busy} onClick={onBack}>Atrás</button>
      {activeStep < steps.length - 1
        ? <button type="button" className="btn btn-primary" disabled={busy} onClick={onNext}>Siguiente</button>
        : <span className="m3-wizard-step">Listo para confirmar abajo</span>}
    </div>
  </div>;
}
