import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { QueueDrawer } from "./QueueDrawer";
import { useQueue } from "./QueueProvider";

const NAV_ITEMS = [
  { to: "/simulaciones", label: "Simulaciones" },
  { to: "/configuraciones", label: "Estrategias" },
  { to: "/datos", label: "Datos" },
  { to: "/ajustes", label: "Ajustes" },
] as const;

export interface PrimaryAction {
  label: string;
  to: string;
}

interface ShellProps {
  title: string;
  mobileTitle?: string;
  primaryAction?: PrimaryAction | null;
  children: ReactNode;
}

export function Shell({ title, mobileTitle, primaryAction = null, children }: ShellProps) {
  const [queueOpen, setQueueOpen] = useState(false);
  const [mobileViewport, setMobileViewport] = useState(() => window.innerWidth < 900);
  const { status, error } = useQueue();
  const queueRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const updateViewport = () => setMobileViewport(window.innerWidth < 900);
    window.addEventListener("resize", updateViewport);
    return () => window.removeEventListener("resize", updateViewport);
  }, []);

  useEffect(() => {
    delete document.documentElement.dataset.theme;
    try { window.localStorage.removeItem("laboratorio-theme"); } catch { /* Legacy preference cleanup is best-effort. */ }
  }, []);

  function handleSkipLinkClick(event: React.MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    document.getElementById("main-content")?.focus();
  }

  const queueStatus = error
    ? error === "network" ? "Sin conexión" : "Sin datos recientes"
    : status?.active_id ? "En curso" : "Sin cálculos en curso";
  const pendingCount = status?.pending.total;

  return (
    <div className="shell-root">
      <a href="#main-content" className="skip-link" onClick={handleSkipLinkClick}>
        Saltar al contenido principal
      </a>
      <div data-testid="shell-layout" className="shell-layout">
        <header className="shell-app-bar">
          <div className="shell-app-bar-title">
            <span className="shell-brand legend">LABORATORIO / QUINIELA 80</span>
            <h1 className="break-normal">{mobileViewport && mobileTitle ? mobileTitle : title}</h1>
          </div>
          <nav id="primary-navigation" aria-label="Navegación principal" className="shell-navigation">
            <ul>{NAV_ITEMS.map((item) => <li key={item.to}>
              <NavLink to={item.to} className={({ isActive }) => `shell-nav-link legend${isActive ? " is-active" : ""}`}>
                <span>{item.label}</span>
              </NavLink>
            </li>)}</ul>
          </nav>
          {primaryAction && <Link className="shell-primary-action legend" aria-label={`Acceso rápido: ${primaryAction.label}`} to={primaryAction.to}>{primaryAction.label}</Link>}
          <div className="shell-app-bar-actions">
            <button ref={queueRef} type="button" aria-label="Abrir cola de cálculo" aria-expanded={queueOpen} aria-haspopup="dialog" aria-describedby="queue-state"
              title={error ? error === "network" ? "Cola de cálculo: sin conexión" : "Cola de cálculo: sin datos recientes" : status?.active_id ? "Cola de cálculo: en curso" : "Abrir cola de cálculo"}
              className="shell-queue-button legend" onClick={() => setQueueOpen(true)}>
              Cola · {queueStatus}{typeof pendingCount === "number" && ` · ${pendingCount} en espera`}<span id="queue-state" className="ledger-sr-only">{queueStatus}</span>
            </button>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} className="shell-main"><div className="shell-page-content">{children}</div></main>
      </div>
      <QueueDrawer open={queueOpen} onClose={() => setQueueOpen(false)} trigger={queueRef} />
    </div>
  );
}
