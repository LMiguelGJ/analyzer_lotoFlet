import type { HTMLAttributes, ReactNode } from "react";

export interface BlockProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
  border?: "outline" | "top";
}

export function Block({ children, border = "outline", className = "", ...props }: BlockProps) {
  return <section className={`ledger-block ${border === "top" ? "ledger-block-top-rule" : ""} ${className}`.trim()} {...props}>{children}</section>;
}

export interface SectionHeaderProps {
  title: string;
  kicker?: string;
  /** Sequence prefixes are reserved for ordered workflows whose order carries meaning (for example, creation steps). */
  number?: "01" | "02" | "03";
  id?: string;
  className?: string;
}

export function SectionHeader({ title, kicker, number, id, className = "" }: SectionHeaderProps) {
  return <header className={className}>
    {kicker && <div className="ledger-kicker">{kicker}</div>}
    <h2 id={id} className="ledger-section-title">{number && <span aria-hidden="true">{number} </span>}{title}</h2>
  </header>;
}
