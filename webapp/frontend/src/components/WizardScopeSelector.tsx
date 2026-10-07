import { useNavigate } from "react-router-dom";

export type WizardMode = "classic" | "history" | "profile" | "batch";
const modeDetails: Record<WizardMode, { label: string; path: string }> = {
  classic: { label: "Clásico", path: "/simulaciones/nueva" },
  history: { label: "Histórica", path: "/simulaciones/nueva-historica" },
  profile: { label: "Perfil", path: "/simulaciones/nueva/perfil" },
  batch: { label: "Lote de perfiles", path: "/simulaciones/nueva/sesion" },
};

export function WizardScopeSelector({ currentMode, busy = false }: { currentMode: WizardMode; busy?: boolean }) {
  const navigate = useNavigate();
  function choose(mode: WizardMode) {
    if (busy || mode === currentMode) return;
    if (!window.confirm("Cambiar de tipo inicia un flujo nuevo. El borrador, la referencia guardada y los importes de este flujo no se convertirán ni se trasladarán. ¿Continuar?")) return;
    navigate(modeDetails[mode].path);
  }
  return <fieldset className="space-y-3 border-t border-border pt-4" disabled={busy}>
    <legend className="field-label">Tipo de simulación</legend>
    <p className="field-help">Cambiar de tipo inicia un borrador nuevo; no convierte ni traslada datos de este flujo.</p>
    <div className="flex flex-wrap gap-2">{(Object.keys(modeDetails) as WizardMode[]).map((mode) => <button key={mode} type="button" className={`btn ${mode === currentMode ? "btn-primary" : "btn-tertiary"}`} aria-pressed={mode === currentMode} disabled={busy || mode === currentMode} onClick={() => choose(mode)}>{modeDetails[mode].label}</button>)}</div>
  </fieldset>;
}
