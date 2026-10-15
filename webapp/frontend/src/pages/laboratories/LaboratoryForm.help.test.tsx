import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "jest-axe";
import * as api from "../../api/laboratories";
import { LaboratoryForm } from "./LaboratoryForm";

vi.mock("../../api/laboratories", () => ({ createLaboratory: vi.fn() }));
beforeEach(() => vi.clearAllMocks());

const cases = [
  ["Sistema de selección", "system", "transition", "Transición", /número anterior/i],
  ["Sistema de selección", "system", "cold", "Fríos", /tiempo sin aparecer/i],
  ["Sistema de selección", "system", "select_interpretable", "Selector interpretable", /mejor promedio de aciertos/i],
  ["Sistema de selección", "system", "mix", "Mezclas", /frecuencia histórica/i],
  ["Sistema de selección", "system", "ensemble", "Ensemble", /cinco rankings/i],
  ["Sistema de selección", "system", "parity", "Paridad", /pares o impares/i],
  ["Estilo de apuesta", "stake_style", "bold", "Audaz", /saldo disponible/i],
  ["Estilo de apuesta", "stake_style", "ladder", "Escalera", /diez rondas/i],
  ["Estilo de apuesta", "stake_style", "flat", "Plana", /una unidad por número/i],
] as const;

function helpButton(group: string) { return screen.getByRole("button", { name: `Ayuda sobre ${group.toLowerCase()}` }); }

describe("laboratory option help", () => {
  it("keeps help hidden until requested and preserves native option lists", () => {
    render(<LaboratoryForm onCreated={vi.fn()} />);
    expect(helpButton("Sistema de selección")).toHaveAttribute("aria-expanded", "false");
    expect(helpButton("Estilo de apuesta")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText("Comparar opciones")).not.toBeInTheDocument();
    const systems = screen.getByLabelText("Sistema de selección");
    const styles = screen.getByLabelText("Estilo de apuesta");
    expect(systems.tagName).toBe("SELECT");
    expect(styles.tagName).toBe("SELECT");
    expect(within(systems).getAllByRole("option")).toHaveLength(6);
    expect(within(styles).getAllByRole("option")).toHaveLength(3);
    expect(systems).toHaveValue("transition");
    expect(styles).toHaveValue("bold");
  });

  it.each(cases)("explains %s / %s / %s without submitting", async (group, _kind, value, label, fact) => {
    const user = userEvent.setup();
    const onCreated = vi.fn();
    render(<LaboratoryForm onCreated={onCreated} />);
    await user.selectOptions(screen.getByLabelText(group), value);
    await user.click(helpButton(group));
    const panel = screen.getByRole("dialog", { name: label });
    expect(within(panel).getByText(fact)).toBeVisible();
    expect(within(panel).getByText("En qué afecta:")).toBeVisible();
    expect(within(panel).getByText("Ejemplo:")).toBeVisible();
    expect(helpButton(group)).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText(group)).toHaveValue(value);
    expect(api.createLaboratory).not.toHaveBeenCalled();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("compares only the requested group, marks its current choice and keeps the draft", async () => {
    const user = userEvent.setup();
    render(<LaboratoryForm onCreated={vi.fn()} />);
    await user.type(screen.getByLabelText("Nombre"), "Mi borrador");
    await user.selectOptions(screen.getByLabelText("Estilo de apuesta"), "flat");
    await user.click(helpButton("Estilo de apuesta"));
    await user.click(screen.getByRole("button", { name: "Comparar opciones" }));
    const panel = screen.getByRole("dialog", { name: "Estilos de apuesta" });
    expect(within(panel).getAllByRole("heading", { level: 4 }).map((node) => node.textContent)).toEqual(["Audaz", "Escalera", "Plana"]);
    expect(within(panel).getByText("Seleccionado").closest("li")).toHaveAttribute("aria-current", "true");
    expect(within(panel).getByText("Seleccionado").closest("li")).toHaveTextContent("Plana");
    await user.click(screen.getByRole("button", { name: "Volver a la opción elegida" }));
    expect(screen.getByRole("dialog", { name: "Plana" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Cerrar ayuda" }));
    expect(helpButton("Estilo de apuesta")).toHaveFocus();
    expect(screen.getByLabelText("Nombre")).toHaveValue("Mi borrador");
    expect(screen.getByLabelText("Estilo de apuesta")).toHaveValue("flat");
    expect(api.createLaboratory).not.toHaveBeenCalled();
  });

  it("opens by keyboard, closes with Escape, and returns focus to its trigger", async () => {
    const user = userEvent.setup();
    render(<LaboratoryForm onCreated={vi.fn()} />);
    const trigger = helpButton("Sistema de selección");
    trigger.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("dialog", { name: "Transición" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Comparar opciones" }));
    expect(within(screen.getByRole("dialog")).getAllByRole("heading", { level: 4 })).toHaveLength(6);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    await user.keyboard(" ");
    expect(screen.getByRole("dialog", { name: "Transición" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Comparar opciones" })).toBeVisible();
    expect(api.createLaboratory).not.toHaveBeenCalled();
  });

  it("allows one panel, dismisses outside without stealing focus, and follows the selected value", async () => {
    const user = userEvent.setup();
    render(<LaboratoryForm onCreated={vi.fn()} />);
    await user.click(helpButton("Sistema de selección"));
    await user.click(helpButton("Estilo de apuesta"));
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.getByRole("dialog", { name: "Audaz" })).toBeVisible();
    expect(helpButton("Sistema de selección")).toHaveAttribute("aria-expanded", "false");
    await user.click(screen.getByLabelText("Nombre"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Nombre")).toHaveFocus();
    await user.selectOptions(screen.getByLabelText("Sistema de selección"), "cold");
    await user.click(helpButton("Sistema de selección"));
    expect(screen.getByRole("dialog", { name: "Fríos" })).toBeVisible();
    expect(api.createLaboratory).not.toHaveBeenCalled();
  });

  it("exposes accessible names and relationships in selected and comparison views", async () => {
    const user = userEvent.setup();
    const { container } = render(<LaboratoryForm onCreated={vi.fn()} />);
    expect(await axe(container)).toHaveNoViolations();
    await user.click(helpButton("Sistema de selección"));
    expect(helpButton("Sistema de selección")).toHaveAttribute("aria-controls", screen.getByRole("dialog").id);
    expect(await axe(screen.getByRole("dialog"))).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Comparar opciones" }));
    expect(await axe(screen.getByRole("dialog"))).toHaveNoViolations();
  });
});
