import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Button, Field, Loading, SectionHeader } from "./index";

describe("flat foundation primitives", () => {
  it("associates field labels and errors and honors disabled state", () => {
    render(<Field id="quota" label="Cuota" error="Valor inválido" disabled />);
    expect(screen.getByRole("textbox", { name: "Cuota" })).toBeDisabled();
    expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Valor inválido")).toHaveAttribute("id", "quota-error");
  });

  it("wraps checkbox controls in an associated 48px clickable label", async () => {
    const user = userEvent.setup();
    render(<Field id="history-active" type="checkbox" label="Historial activo" />);
    const checkbox = screen.getByRole("checkbox", { name: "Historial activo" });
    const label = screen.getByText("Historial activo").closest("label");
    expect(label).toHaveClass("ledger-choice-label");
    expect(label).toContainElement(checkbox);
    expect(checkbox).toHaveClass("ledger-choice-control");
    await user.click(screen.getByText("Historial activo"));
    expect(checkbox).toBeChecked();
  });

  it("keeps disabled choices non-interactive while their label remains associated", async () => {
    const user = userEvent.setup();
    render(<Field id="locked" type="radio" label="Solo lectura" disabled />);
    const choice = screen.getByRole("radio", { name: "Solo lectura" });
    await user.click(screen.getByText("Solo lectura"));
    expect(choice).toBeDisabled();
    expect(choice).not.toBeChecked();
    expect(screen.getByText("Solo lectura").closest("label")).toHaveClass("is-disabled");
  });

  it("preserves text input props while keeping its existing field layout", () => {
    render(<Field id="name" label="Nombre" placeholder="Escribí un nombre" maxLength={80} autoComplete="off" />);
    expect(screen.getByRole("textbox", { name: "Nombre" })).toHaveAttribute("placeholder", "Escribí un nombre");
    expect(screen.getByRole("textbox")).toHaveAttribute("maxlength", "80");
    expect(screen.getByRole("textbox")).toHaveAttribute("autocomplete", "off");
  });

  it("makes loading buttons unavailable and exposes their busy state", () => {
    render(<Button loading>Guardar</Button>);
    expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
    expect(screen.getByRole("button")).toHaveAttribute("aria-busy", "true");
  });

  it("uses an accessible status with decorative skeleton rows hidden", () => {
    const { container } = render(<Loading rows={2} label="Cargando corridas…" />);
    expect(screen.getByRole("status")).toHaveTextContent("Cargando corridas…");
    expect(container.querySelectorAll(".ledger-skeleton-row")).toHaveLength(2);
    expect(container.querySelector("[aria-hidden='true']")).toContainElement(container.querySelector(".ledger-skeleton-row"));
  });

  it("does not number flat sheet section headers unless asked", () => {
    render(<SectionHeader title="Reglas" />);
    expect(screen.getByRole("heading", { name: "Reglas" })).toBeInTheDocument();
    expect(screen.queryByText("01")).not.toBeInTheDocument();
  });
});
