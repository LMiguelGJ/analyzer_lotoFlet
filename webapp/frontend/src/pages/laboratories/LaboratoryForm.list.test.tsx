import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "jest-axe";
import { ApiError } from "../../api/client";
import * as api from "../../api/laboratories";
import type { LaboratoryOptions } from "../../api/laboratories";
import { LaboratoryForm } from "./LaboratoryForm";

vi.mock("../../api/laboratories", () => ({ createLaboratory: vi.fn(), getLaboratoryOptions: vi.fn() }));
const optionsMock = vi.mocked(api.getLaboratoryOptions), createMock = vi.mocked(api.createLaboratory);

const chance: LaboratoryOptions = {
  list: { id: "chance_express", name: "Loteka Chance Express", positions: 5 },
  systems: [{ id: "parity", label: "Paridad", available: true }, { id: "transition", label: "Transición", available: true }],
  prizes: [80, 8, 4, 2, 1], window: { start: "2025-09-02 05:10", end: "2026-09-25 18:20" }, history_sha256: "d".repeat(64),
};
const reason = "No disponible para esta lista";
const leidsa: LaboratoryOptions = {
  list: { id: "leidsa_quiniela", name: "Quiniela Leidsa", positions: 3 },
  systems: [
    { id: "parity", label: "Paridad", available: true }, { id: "freq_hist", label: "Frecuencia histórica", available: true },
    { id: "freq_recent", label: "Frecuencia reciente", available: true }, { id: "decay", label: "Decaimiento", available: true },
    { id: "cold", label: "Fríos", available: true },
    { id: "transition", label: "Transición", available: false, reason }, { id: "notebook", label: "Cuaderno", available: false, reason },
  ],
  prizes: [60, 8, 4], window: { start: "2023-01-04 14:55", end: "2026-11-16 20:55" }, history_sha256: "e".repeat(64),
};
/** What the options endpoint reports once the list offers its nine systems. */
const leidsaNine: LaboratoryOptions = {
  list: { id: "leidsa_quiniela", name: "Quiniela Leidsa", positions: 3 },
  systems: [
    { id: "parity", label: "Paridad", available: true }, { id: "cold", label: "Fríos", available: true },
    { id: "freq_hist", label: "Frecuencia histórica", available: true }, { id: "freq_recent", label: "Frecuencia reciente", available: true },
    { id: "decay", label: "Decaimiento", available: true }, { id: "transition", label: "Transición", available: true },
    { id: "overdue", label: "Ciclo vencido", available: true }, { id: "digits", label: "Terminaciones y decenas", available: true },
    { id: "ensemble", label: "Ensamble", available: true },
  ],
  prizes: [60, 8, 4], window: { start: "2023-01-04 14:55", end: "2026-11-16 20:55" }, history_sha256: "e".repeat(64),
};
beforeEach(() => { vi.clearAllMocks(); });

describe("laboratory form follows the active list", () => {
  it("keeps Chance Express as it was: five prizes 80/8/4/2/1, the reference window and the six archived systems", async () => {
    optionsMock.mockResolvedValue(chance);
    render(<LaboratoryForm onCreated={vi.fn()} />);
    await screen.findByLabelText("Nombre");
    const group = screen.getByRole("group", { name: "Premios por posición" });
    expect(within(group).getAllByRole("textbox").map((input) => (input as HTMLInputElement).value)).toEqual(["80", "8", "4", "2", "1"]);
    expect(within(group).getByLabelText("5.º")).toBeInTheDocument();
    expect(screen.getByLabelText("Ventana: inicio")).toHaveValue("2025-09-02 05:10");
    expect(screen.getByLabelText("Ventana: fin")).toHaveValue("2026-09-25 18:20");
    expect(within(screen.getByLabelText("Sistema de selección")).getAllByRole("option")).toHaveLength(6);
    expect(screen.getByLabelText("Sistema de selección")).toHaveValue("transition");
  });

  it("shows three prize fields and the list's window under Leidsa, and submits three prizes", async () => {
    optionsMock.mockResolvedValue(leidsa);
    createMock.mockResolvedValue({ schema_version: 1, id: "x", name: "L", reference_id: null, config: {} as never });
    const onCreated = vi.fn();
    const user = userEvent.setup();
    render(<LaboratoryForm onCreated={onCreated} />);
    await screen.findByLabelText("Nombre");
    const group = screen.getByRole("group", { name: "Premios por posición" });
    expect(within(group).getAllByRole("textbox").map((input) => (input as HTMLInputElement).value)).toEqual(["60", "8", "4"]);
    expect(within(group).queryByLabelText("4.º")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Ventana: inicio")).toHaveValue("2023-01-04 14:55");
    expect(screen.getByLabelText("Ventana: fin")).toHaveValue("2026-11-16 20:55");
    await user.type(screen.getByLabelText("Nombre"), "Mi laboratorio Leidsa");
    await user.click(screen.getByRole("button", { name: "Crear laboratorio" }));
    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    const config = createMock.mock.calls[0][1];
    expect(config.prizes).toEqual([60, 8, 4]);
    expect(config.system).toBe("cold");
    expect(config.window_start).toBe("2023-01-04 14:55");
    expect(onCreated).toHaveBeenCalled();
  });

  it("offers the nine Leidsa systems with the labels the list reports", async () => {
    optionsMock.mockResolvedValue(leidsaNine);
    render(<LaboratoryForm onCreated={vi.fn()} />);
    const select = await screen.findByLabelText("Sistema de selección");
    expect(within(select).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Paridad", "Fríos", "Frecuencia histórica", "Frecuencia reciente", "Decaimiento",
      "Transición", "Ciclo vencido", "Terminaciones y decenas", "Ensamble",
    ]);
    expect(select).toHaveValue("cold");
  });

  it.each([
    ["transition", "Transición", /en la misma posición/],
    ["ensemble", "Ensamble", /contexto horario/],
  ])("explains %s with the Leidsa text instead of the Chance copy", async (value, label, chanceOnly) => {
    optionsMock.mockResolvedValue(leidsaNine);
    const user = userEvent.setup();
    render(<LaboratoryForm onCreated={vi.fn()} />);
    await user.selectOptions(await screen.findByLabelText("Sistema de selección"), value);
    await user.click(screen.getByRole("button", { name: "Ayuda sobre sistema de selección" }));
    const panel = screen.getByRole("dialog", { name: label });
    expect(within(panel).getByText(/hipótesis de patrón/)).toBeVisible();
    expect(within(panel).queryByText(chanceOnly)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Comparar opciones" }));
    expect(within(screen.getByRole("dialog")).getAllByRole("heading", { level: 4 }).map((node) => node.textContent))
      .toEqual(["Paridad", "Fríos", "Frecuencia histórica", "Frecuencia reciente", "Decaimiento", "Transición", "Ciclo vencido", "Terminaciones y decenas", "Ensamble"]);
  });

  it("lists unavailable systems disabled with their reason and keeps the available ones selectable", async () => {
    optionsMock.mockResolvedValue(leidsa);
    render(<LaboratoryForm onCreated={vi.fn()} />);
    const select = await screen.findByLabelText("Sistema de selección");
    const options = within(select).getAllByRole("option") as HTMLOptionElement[];
    expect(options).toHaveLength(7);
    const transition = options.find((option) => option.value === "transition")!;
    expect(transition).toBeDisabled();
    expect(transition).toHaveTextContent(`Transición — ${reason}`);
    expect(options.filter((option) => !option.disabled).map((option) => option.value)).toEqual(["parity", "freq_hist", "freq_recent", "decay", "cold"]);
    await userEvent.selectOptions(select, "decay");
    expect(select).toHaveValue("decay");
  });

  it("explains the systems that only Leidsa offers without breaking the help panel", async () => {
    optionsMock.mockResolvedValue(leidsa);
    const user = userEvent.setup();
    render(<LaboratoryForm onCreated={vi.fn()} />);
    await user.selectOptions(await screen.findByLabelText("Sistema de selección"), "decay");
    await user.click(screen.getByRole("button", { name: "Ayuda sobre sistema de selección" }));
    const panel = screen.getByRole("dialog", { name: "Decaimiento" });
    expect(within(panel).getByText(/peso que baja/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Comparar opciones" }));
    expect(within(screen.getByRole("dialog")).getAllByRole("heading", { level: 4 })).toHaveLength(5);
  });

  it("validates only the active list's prizes and has no accessibility violations", async () => {
    optionsMock.mockResolvedValue(leidsa);
    const user = userEvent.setup();
    const { container } = render(<LaboratoryForm onCreated={vi.fn()} />);
    await screen.findByLabelText("Nombre");
    expect(await axe(container)).toHaveNoViolations();
    await user.type(screen.getByLabelText("Nombre"), "Prueba");
    await user.clear(screen.getByLabelText("3.º"));
    await user.click(screen.getByRole("button", { name: "Crear laboratorio" }));
    expect(await screen.findByText("El premio es un entero positivo.")).toBeInTheDocument();
    expect(createMock).not.toHaveBeenCalled();
  });

  it("shows the server message and a retry when the options cannot be read", async () => {
    optionsMock.mockRejectedValueOnce(new ApiError(409, "Falta el archivo de la lista «Quiniela Leidsa».")).mockResolvedValue(chance);
    render(<LaboratoryForm onCreated={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Falta el archivo de la lista «Quiniela Leidsa».");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByLabelText("Nombre")).toBeInTheDocument();
  });

  it("shows «Parámetros del sistema» collapsed with the field of the chosen system and sends it", async () => {
    optionsMock.mockResolvedValue(leidsaNine);
    createMock.mockResolvedValue({ schema_version: 1, id: "x", name: "L", reference_id: null, config: {} as never });
    const user = userEvent.setup();
    render(<LaboratoryForm onCreated={vi.fn()} />);
    await screen.findByLabelText("Nombre");
    const summary = screen.getByText("Parámetros del sistema");
    expect(summary.closest("details")).not.toHaveAttribute("open");
    await user.selectOptions(screen.getByLabelText("Sistema de selección"), "decay");
    await user.click(summary);
    expect(screen.getByLabelText("Vida media (sorteos)")).toHaveAttribute("placeholder", "500");
    expect(screen.queryByLabelText("Ventana (sorteos)")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Vida media (sorteos)"), "300");
    await user.selectOptions(screen.getByLabelText("Desempate"), "seeded");
    await user.type(screen.getByLabelText("Nombre"), "Decaimiento 300");
    await user.click(screen.getByRole("button", { name: "Crear laboratorio" }));
    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(createMock.mock.calls[0][1].ranking_params).toEqual({ half_life: 300, tie_break: "seeded" });
  });

  it("offers the ensemble components as checkboxes and explains the opposite votes", async () => {
    optionsMock.mockResolvedValue(leidsaNine);
    const user = userEvent.setup();
    render(<LaboratoryForm onCreated={vi.fn()} />);
    await screen.findByLabelText("Nombre");
    await user.selectOptions(screen.getByLabelText("Sistema de selección"), "ensemble");
    await user.click(screen.getByText("Parámetros del sistema"));
    expect(screen.getAllByRole("checkbox")).toHaveLength(7);
    expect(screen.getByText(/casi iguales/)).toBeInTheDocument();
    expect(screen.getByText(/votan al revés/)).toBeInTheDocument();
  });

  it("shows no system parameters for Paridad or Chance Express", async () => {
    optionsMock.mockResolvedValue(leidsaNine);
    const user = userEvent.setup();
    const { unmount } = render(<LaboratoryForm onCreated={vi.fn()} />);
    await screen.findByLabelText("Nombre");
    await user.selectOptions(screen.getByLabelText("Sistema de selección"), "parity");
    expect(screen.queryByText("Parámetros del sistema")).not.toBeInTheDocument();
    unmount();
    optionsMock.mockResolvedValue(chance);
    render(<LaboratoryForm onCreated={vi.fn()} />);
    await screen.findByLabelText("Nombre");
    expect(screen.queryByText("Parámetros del sistema")).not.toBeInTheDocument();
  });
});
