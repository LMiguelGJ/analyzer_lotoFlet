import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { QueueDrawer } from "./QueueDrawer";
import { useQueue } from "./QueueProvider";

const NAV_ITEMS = [
  { to: "/experimentos", label: "Experimentos", icon: "◫" },
  { to: "/configuraciones", label: "Estrategias", icon: "◇" },
  { to: "/datos", label: "Datos", icon: "▤" },
  { to: "/ajustes", label: "Ajustes", icon: "⚙" },
] as const;

interface ShellProps {
  title: string;
  children: ReactNode;
}

function preferredTheme(): "light" | "dark" {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function Shell({ title, children }: ShellProps) {
  const [queueOpen, setQueueOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark" | null>(() => {
    try {
      const stored = window.localStorage.getItem("laboratorio-theme");
      return stored === "light" || stored === "dark" ? stored : null;
    } catch {
      return null;
    }
  });
  const { status, error } = useQueue();
  const location = useLocation();
  const queueRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (theme === null) {
      document.documentElement.removeAttribute("data-theme");
      return;
    }
    document.documentElement.dataset.theme = theme;
    try { window.localStorage.setItem("laboratorio-theme", theme); } catch { /* Theme remains active in memory for this session. */ }
  }, [theme]);

  function handleSkipLinkClick(event: React.MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    document.getElementById("main-content")?.focus();
  }

  function toggleTheme() {
    setTheme(theme === null ? (preferredTheme() === "dark" ? "light" : "dark") : theme === "dark" ? "light" : "dark");
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
            <h1 className="break-normal">{title}</h1>
          </div>
          <div className="shell-app-bar-actions">
            <button
              type="button"
              className="m3-icon-button"
              aria-label={`Cambiar tema. Tema actual: ${theme ?? "automático"}`}
              title="Cambiar tema"
              onClick={toggleTheme}
            >
              <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
            </button>
            <button
              ref={queueRef}
              type="button"
              aria-label="Abrir cola de cálculo"
              aria-expanded={queueOpen}
              aria-haspopup="dialog"
              aria-describedby="queue-state"
              title={error ? error === "network" ? "Cola de cálculo: sin conexión" : "Cola de cálculo: sin datos recientes" : status?.active_id ? "Cola de cálculo: en curso" : "Abrir cola de cálculo"}
              className="m3-icon-button"
              onClick={() => setQueueOpen(true)}
            >
              <span aria-hidden="true">☷</span>
              <span id="queue-state" className="ledger-sr-only">{queueStatus}</span>
            </button>
          </div>
        </header>

        <nav id="primary-navigation" aria-label="Navegación principal" className="shell-navigation">
          <ul>
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} aria-label={item.to === "/experimentos" ? "Simulaciones" : undefined} className={({ isActive }) => `shell-nav-link${isActive ? " is-active" : ""}`}>
                  <span className="shell-nav-icon" aria-hidden="true">{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main id="main-content" tabIndex={-1} className="shell-main">
          <div className="shell-page-content">{children}</div>
        </main>

        {!location.pathname.startsWith("/ajustes") && !location.pathname.startsWith("/experimentos/nuevo") && <Link className="m3-extended-fab" aria-label="Acceso rápido: Nueva simulación" to="/experimentos/nuevo">
          <span aria-hidden="true">＋</span>
          <span>Nueva simulación</span>
        </Link>}
      </div>
      <QueueDrawer open={queueOpen} onClose={() => setQueueOpen(false)} trigger={queueRef} />
    </div>
  );
}
