import type { ReactNode } from "react";
import { useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { QueueDrawer } from "./QueueDrawer";
import { useQueue } from "./QueueProvider";

const NAV_ITEMS = [
  { to: "/experimentos", label: "Simulaciones" },
  { to: "/configuraciones", label: "Estrategias" },
  { to: "/datos", label: "Datos" },
  { to: "/ajustes", label: "Ajustes" },
] as const;

function navLinkClassName({ isActive }: { isActive: boolean }): string {
  const base = "shell-nav-link block border-l-2 px-4 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent";
  return isActive
    ? `${base} border-accent text-text`
    : `${base} border-transparent text-text-secondary hover:text-text`;
}

interface ShellProps {
  title: string;
  children: ReactNode;
}

export function Shell({ title, children }: ShellProps) {
  const [queueOpen, setQueueOpen] = useState(false);
  const { status, error } = useQueue();
  const queueRef = useRef<HTMLButtonElement>(null);

  function handleSkipLinkClick(event: React.MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    document.getElementById("main-content")?.focus();
  }

  return (
    <div className="min-h-screen bg-bg text-text">
      <a href="#main-content" className="skip-link" onClick={handleSkipLinkClick}>
        Saltar al contenido principal
      </a>

      <div data-testid="shell-layout" className="flex min-h-screen flex-col min-[900px]:flex-row">
        <nav
          id="primary-navigation"
          aria-label="Navegación principal"
          className="w-full shrink-0 border-b border-border bg-surface px-3 py-3 min-[900px]:w-[210px] min-[900px]:border-b-0 min-[900px]:border-r min-[900px]:px-0 min-[900px]:py-6"
        >
          <div className="mb-3 flex items-center justify-between gap-2 px-1 min-[900px]:mb-6 min-[900px]:block min-[900px]:px-4">
            <p className="font-heading text-xl min-[900px]:mb-1 min-[900px]:text-2xl">Laboratorio Quiniela 80</p>
            <button
              ref={queueRef}
              type="button"
              aria-label="Abrir cola de cálculo"
              aria-expanded={queueOpen}
              aria-haspopup="dialog"
              title={error ? error === "network" ? "Cola de cálculo: sin conexión" : "Cola de cálculo: sin datos recientes" : status?.active_id ? "Cola de cálculo: en curso" : "Abrir cola de cálculo"}
              className="ledger-button ledger-button-secondary min-h-9 shrink-0 px-2 min-[321px]:px-3"
              onClick={() => setQueueOpen(true)}
            >
              <span aria-hidden="true" className="hidden min-[321px]:inline">Cola{status?.active_id ? " · En curso" : ""}{error ? error === "network" ? " · Sin conexión" : " · Sin datos recientes" : ""}</span>
              <span aria-hidden="true" className="min-[321px]:hidden">≡</span>
            </button>
          </div>
          <ul className="grid grid-cols-2 gap-x-1 min-[480px]:flex min-[480px]:flex-wrap min-[480px]:gap-1 min-[900px]:block">
            {NAV_ITEMS.map((item) => (
              <li key={item.to} className="min-w-0">
                <NavLink to={item.to} className={navLinkClassName}>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0 flex-1">
          <header className="min-w-0 border-b border-border px-page-margin py-4">
            <h1 className="break-normal font-heading text-2xl leading-tight min-[900px]:text-4xl">{title}</h1>
          </header>

          <main
            id="main-content"
            tabIndex={-1}
            className="mx-auto max-w-[1440px] px-page-margin py-section-gap focus:outline-none"
          >
            {children}
          </main>
        </div>
      </div>
      <QueueDrawer open={queueOpen} onClose={() => setQueueOpen(false)} trigger={queueRef} />
    </div>
  );
}
