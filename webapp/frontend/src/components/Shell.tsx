import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/corridas", label: "Corridas" },
  { to: "/ajustes", label: "Ajustes" },
] as const;

interface ShellProps {
  title: string;
  children: ReactNode;
}

export function Shell({ title, children }: ShellProps) {
  function handleSkipLinkClick(event: React.MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    document.getElementById("main-content")?.focus();
  }

  return (
    <div className="shell-root">
      <a href="#main-content" className="skip-link" onClick={handleSkipLinkClick}>
        Saltar al contenido principal
      </a>
      <div data-testid="shell-layout" className="shell-layout">
        <header className="shell-app-bar">
          <div className="shell-app-bar-title">
            <span className="shell-brand legend">LABORATORIO / QUINIELA 80</span>
            <h1 className="break-normal">{title}</h1>
          </div>
          <nav id="primary-navigation" aria-label="Navegación principal" className="shell-navigation">
            <ul>{NAV_ITEMS.map((item) => <li key={item.to}>
              <NavLink to={item.to} className={({ isActive }) => `shell-nav-link legend${isActive ? " is-active" : ""}`}>
                <span>{item.label}</span>
              </NavLink>
            </li>)}</ul>
          </nav>
        </header>
        <main id="main-content" tabIndex={-1} className="shell-main"><div className="shell-page-content">{children}</div></main>
      </div>
    </div>
  );
}
