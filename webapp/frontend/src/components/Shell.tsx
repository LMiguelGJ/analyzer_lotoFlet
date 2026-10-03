import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { QueueDrawer } from "./QueueDrawer";
import { useQueue } from "./QueueProvider";

/**
 * Fixed sidebar navigation + content shell (UX12-UX18). Below 800px (the
 * `nav` breakpoint, tailwind.config.ts) the sidebar collapses behind an
 * explicit toggle bar that stays in the document's normal flow (`sticky`,
 * never CSS-`fixed`) above the header, so it reserves its own space and can
 * never float over the title; the shell switches from a stacked column
 * to a side-by-side row at 800px (`nav`). The separate 1100px `wide`
 * breakpoint is reserved for content such as the wizard summary. The
 * toggle's open/close state, its aria-expanded / aria-controls wiring,
 * Escape-to-close and Escape's focus return to the toggle are unit-tested
 * in Shell.test.tsx. What jsdom cannot verify - whether the CSS breakpoints
 * themselves reflow correctly at 800px/1100px and at 200% zoom - needs a
 * real-browser check (LW18).
 */

const NAV_ITEMS = [
  { to: "/experimentos", label: "Simulaciones" },
  { to: "/datos#perfiles", label: "Perfiles de juego" },
  { to: "/datos#historiales", label: "Historiales" },
  { to: "/configuraciones", label: "Estrategias" },
  { to: "/ajustes", label: "Administración" },
] as const;

function navLinkClassName({ isActive }: { isActive: boolean }): string {
  const base = "shell-nav-link block border-l-2 px-4 py-2 text-sm";
  return isActive
    ? `${base} border-accent text-text`
    : `${base} border-transparent text-text-secondary hover:text-text`;
}

interface ShellProps {
  title: string;
  children: ReactNode;
}

export function Shell({ title, children }: ShellProps) {
  const [navOpen, setNavOpen] = useState(false);
  const [queueOpen, setQueueOpen] = useState(false);
  const { status, error } = useQueue();
  const toggleRef = useRef<HTMLButtonElement>(null);
  const queueRef = useRef<HTMLButtonElement>(null);
  const location = useLocation();

  useEffect(() => {
    if (!location.hash) return;
    const target = document.getElementById(location.hash.slice(1));
    if (!target) return;
    target.setAttribute("tabindex", "-1");
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    target.focus();
  }, [location.pathname, location.search, location.hash]);

  useEffect(() => {
    if (!navOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !document.querySelector('[role="dialog"], [role="alertdialog"]')) {
        event.preventDefault();
        setNavOpen(false);
        toggleRef.current?.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [navOpen]);

  function handleSkipLinkClick(event: React.MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    document.getElementById("main-content")?.focus();
  }

  return (
    <div className="min-h-screen bg-bg text-text">
      <a href="#main-content" className="skip-link" onClick={handleSkipLinkClick}>
        Saltar al contenido principal
      </a>

      <div
        data-testid="nav-toggle-bar"
        className="sticky top-0 z-40 hidden border-b border-border bg-surface px-page-margin py-2 max-nav:block"
      >
        <button
          ref={toggleRef}
          type="button"
          className="btn btn-secondary"
          aria-expanded={navOpen}
          aria-controls="primary-navigation"
          onClick={() => setNavOpen((value) => !value)}
        >
          {navOpen ? "Cerrar navegación" : "Abrir navegación"}
        </button>
      </div>

      <div data-testid="shell-layout" className="flex min-h-screen flex-col nav:flex-row">
        <nav
          id="primary-navigation"
          aria-label="Navegación principal"
          data-nav-open={navOpen}
          className={`w-full shrink-0 border-b border-border bg-surface py-6 nav:w-[210px] nav:border-b-0 nav:border-r ${
            navOpen ? "block" : "hidden nav:block"
          }`}
        >
          <p className="mb-1 px-4 font-heading text-2xl">Laboratorio</p>
          <p className="mb-4 px-4 text-sm text-text-secondary">Simulaciones honestas con datos históricos.</p>
          <ul>
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} className={navLinkClassName}>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0 flex-1">
          <header className="flex min-w-0 items-center justify-between gap-3 border-b border-border px-page-margin py-4">
            <h1 className="min-w-0 break-words font-heading text-4xl">{title}</h1>
            <button
              ref={queueRef}
              type="button"
              aria-expanded={queueOpen}
              aria-haspopup="dialog"
              className="btn btn-secondary shrink-0"
              onClick={() => { setNavOpen(false); setQueueOpen(true); }}
            >
              Cola{status?.active_id ? " · En curso" : ""}{error ? error === "network" ? " · Sin conexión" : " · Sin datos recientes" : ""}
            </button>
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
