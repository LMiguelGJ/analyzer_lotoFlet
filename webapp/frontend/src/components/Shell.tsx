import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { QueueDrawer } from "./QueueDrawer";
import { useQueue } from "./QueueProvider";

const NAV_ITEMS = [
  { to: "/simulaciones", label: "Simulaciones", icon: "◫" },
  { to: "/configuraciones", label: "Estrategias", icon: "◇" },
  { to: "/datos", label: "Datos", icon: "▤" },
  { to: "/ajustes", label: "Ajustes", icon: "⚙" },
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
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      const stored = window.localStorage.getItem("laboratorio-theme");
      return stored === "light" || stored === "dark" ? stored : "dark";
    } catch {
      return "dark";
    }
  });
  const { status, error } = useQueue();
  const queueRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const updateViewport = () => setMobileViewport(window.innerWidth < 900);
    window.addEventListener("resize", updateViewport);
    return () => window.removeEventListener("resize", updateViewport);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { window.localStorage.setItem("laboratorio-theme", theme); } catch { /* Theme remains active in memory for this session. */ }
  }, [theme]);

  function handleSkipLinkClick(event: React.MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    document.getElementById("main-content")?.focus();
  }

  function toggleTheme() {
    setTheme(theme === "dark" ? "light" : "dark");
  }

  const queueStatus = error
    ? error === "network" ? "Sin conexión" : "Sin datos recientes"
    : status?.active_id ? "En curso" : "Sin cálculos en curso";

  return (
    <div className="shell-root">
      <a href="#main-content" className="skip-link" onClick={handleSkipLinkClick}>
        Saltar al contenido principal
      </a>
      <div data-testid="shell-layout" className="shell-layout">
        <header className="shell-app-bar">
          <div className="shell-app-bar-title">
            <span className="shell-brand">Laboratorio Quiniela 80</span>
            <h1 className="break-normal">{mobileViewport && mobileTitle ? mobileTitle : title}</h1>
          </div>
          <div className="shell-app-bar-actions">
            <button type="button" className="m3-icon-button" aria-label={`Cambiar tema. Tema actual: ${theme}`} title="Cambiar tema" onClick={toggleTheme}>
              <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
            </button>
            <button ref={queueRef} type="button" aria-label="Abrir cola de cálculo" aria-expanded={queueOpen} aria-haspopup="dialog" aria-describedby="queue-state"
              title={error ? error === "network" ? "Cola de cálculo: sin conexión" : "Cola de cálculo: sin datos recientes" : status?.active_id ? "Cola de cálculo: en curso" : "Abrir cola de cálculo"}
              className="m3-icon-button" onClick={() => setQueueOpen(true)}>
              <span aria-hidden="true">☷</span><span id="queue-state" className="ledger-sr-only">{queueStatus}</span>
            </button>
          </div>
        </header>
        <nav id="primary-navigation" aria-label="Navegación principal" className="shell-navigation">
          <ul>{NAV_ITEMS.map((item) => <li key={item.to}>
            <NavLink to={item.to} className={({ isActive }) => `shell-nav-link${isActive ? " is-active" : ""}`}>
              <span className="shell-nav-icon" aria-hidden="true">{item.icon}</span><span>{item.label}</span>
            </NavLink>
          </li>)}</ul>
        </nav>
        <main id="main-content" tabIndex={-1} className="shell-main"><div className="shell-page-content">{children}</div></main>
        {primaryAction && <Link className="m3-extended-fab" aria-label={`Acceso rápido: ${primaryAction.label}`} to={primaryAction.to}>
          <span aria-hidden="true">＋</span><span>{primaryAction.label}</span>
        </Link>}
      </div>
      <QueueDrawer open={queueOpen} onClose={() => setQueueOpen(false)} trigger={queueRef} />
    </div>
  );
}
