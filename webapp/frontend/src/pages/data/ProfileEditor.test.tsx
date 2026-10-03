import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "../../api/client";
import type { PartialProfileTemplate, ProfileListing } from "../../api/types";
import { ProfileEditor } from "./ProfileEditor";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, registerProfile: vi.fn() } };
});
const template: PartialProfileTemplate = { name: "Example 60/10/5", provenance: "reference only",
  known_fields: { universe_size: 100, positions: 3, allows_repeats: true,
    multipliers: [{ numerator: 60, denominator: 1 }, { numerator: 10, denominator: 1 }, { numerator: 5, denominator: 1 }],
    currency: "DOP", minimum_stake: 1 }, missing_fields: ["profile_id", "revision", "scale", "stake_increment", "maximum_stake", "max_coverage", "max_exposure"], execution_supported: false };
const readiness = { ready: true, selector_capabilities: ["static-numbers/v1"], staking_capabilities: ["flat-per-number/v1"],
  entry_policies: ["all_rows/v1"], settlements: ["all", "best"] as const, requires_compatible_dataset: true };
const registered = (profile: ProfileListing["profile"]): ProfileListing => ({ profile, profile_sha256: "a".repeat(64), execution_supported: false, profile_execution: readiness });
const onRegistered = vi.fn();
const onBusyChange = vi.fn();

async function fill(user: ReturnType<typeof userEvent.setup>, positions: number, useTemplate = false) {
  await user.click(screen.getByRole("button", { name: "Crear perfil de juego" }));
  if (useTemplate) await user.selectOptions(screen.getByLabelText("Referencia opcional"), "0");
  await user.click(screen.getByText("Detalles técnicos"));
  await user.clear(screen.getByLabelText("ID nuevo del perfil"));
  await user.type(screen.getByLabelText("ID nuevo del perfil"), "my-game");
  await user.clear(screen.getByLabelText(/Revisión \(1/));
  await user.type(screen.getByLabelText(/Revisión \(1/), "1");
  if (!useTemplate) {
    await user.clear(screen.getByLabelText(/Tamaño del universo/));
    await user.type(screen.getByLabelText(/Tamaño del universo/), "100");
    await user.clear(screen.getByLabelText(/Posiciones por sorteo/));
    await user.type(screen.getByLabelText(/Posiciones por sorteo/), String(positions));
    await user.selectOptions(screen.getByLabelText(/Se repiten números/), "yes");
    await user.clear(screen.getByLabelText(/Moneda \(código/));
    await user.type(screen.getByLabelText(/Moneda \(código/), "DOP");
    for (let index = 0; index < positions; index++) {
      const multiplier = screen.getByLabelText(`Posición ${index + 1} · multiplicador`);
      await user.clear(multiplier);
      await user.type(multiplier, ["60", "10", "5", "2", "1"][index] ?? "0");
    }
  }
  for (const label of [/Escala decimal/, /Incremento de apuesta/, /Apuesta mínima/, /Apuesta máxima/, /Cobertura máxima/, /Exposición máxima/]) {
    await user.clear(screen.getByLabelText(label));
  }
  await user.type(screen.getByLabelText(/Escala decimal/), "2");
  await user.type(screen.getByLabelText(/Incremento de apuesta/), "0.25");
  await user.type(screen.getByLabelText(/Apuesta mínima/), "0.25");
  await user.type(screen.getByLabelText(/Apuesta máxima/), "2.00");
  await user.type(screen.getByLabelText(/Cobertura máxima/), "3");
  await user.type(screen.getByLabelText(/Exposición máxima/), "10.00");
}

beforeEach(() => { vi.mocked(apiClient.registerProfile).mockReset(); onRegistered.mockReset(); onBusyChange.mockReset(); });
describe("profile editor", () => {
  it("opens with an editable Quiniela 80 profile ready to register", async () => {
    const user = userEvent.setup();
    render(<ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    await user.click(screen.getByRole("button", { name: "Crear perfil de juego" }));
    expect(screen.getByLabelText("ID nuevo del perfil")).toHaveValue("quiniela-80");
    expect(screen.getByLabelText(/Revisión \(1/)).toHaveValue("1");
    expect(screen.getByLabelText(/Tamaño del universo/)).toHaveValue("100");
    expect(screen.getByLabelText(/Posiciones por sorteo/)).toHaveValue("3");
    expect(screen.getByLabelText(/Se repiten números/)).toHaveValue("yes");
    expect(screen.getByLabelText("Posición 1 · multiplicador")).toHaveValue("60");
    expect(screen.getByLabelText("Posición 2 · multiplicador")).toHaveValue("10");
    expect(screen.getByLabelText("Posición 3 · multiplicador")).toHaveValue("5");
    expect(screen.getByLabelText(/Moneda \(código/)).toHaveValue("DOP");
    expect(screen.getByLabelText(/Escala decimal/)).toHaveValue("0");
    expect(screen.getByText("0 = sin escala.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Apuesta mínima/)).toHaveValue("1");
    expect(screen.getByText(/sin devolución adicional de la apuesta/)).toBeInTheDocument();
    expect(screen.getByText("Detalles técnicos").closest("details")).not.toHaveAttribute("open");
  });
  it.each([1, 3, 5])("creates %i position documents with explicit money policy and server-derived digest", async (count) => {
    const user = userEvent.setup();
    render(<ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    await fill(user, count);
    vi.mocked(apiClient.registerProfile).mockImplementationOnce(async (profile) => registered(profile));
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    await waitFor(() => expect(onRegistered).toHaveBeenCalledTimes(1));
    const sent = vi.mocked(apiClient.registerProfile).mock.calls[0][0];
    expect(sent).toMatchObject({ schema_version: 1, profile_id: "my-game", revision: 1, positions: count, universe_size: 100,
      allows_repeats: true, currency: "DOP", scale: 2, stake_increment: 25, minimum_stake: 25,
      maximum_stake: 200, max_exposure: 1000, max_coverage: 3, best_rule: "maximum-payout/v1" });
    expect(sent.multipliers).toHaveLength(count);
    expect(onRegistered.mock.calls[0][0].profile_sha256).toBe("a".repeat(64));
  });
  it("prefills only documented template fields and requires missing financial fields", async () => {
    const user = userEvent.setup();
    render(<ProfileEditor templates={[template]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    await user.click(screen.getByRole("button", { name: "Crear perfil de juego" }));
    await user.selectOptions(screen.getByLabelText("Referencia opcional"), "0");
    expect(screen.getByLabelText(/Posiciones por sorteo/)).toHaveValue("3");
    expect(screen.getByLabelText("Posición 1 · multiplicador")).toHaveValue("60/1");
    expect(screen.getByText(/1 unidad\(es\) sin escala/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Apuesta mínima/)).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/ID:/);
    expect(apiClient.registerProfile).not.toHaveBeenCalled();
    await user.click(screen.getByText("Detalles técnicos"));
    await user.type(screen.getByLabelText("ID nuevo del perfil"), "example");
    await user.type(screen.getByLabelText(/Revisión \(1/), "1");
    await user.type(screen.getByLabelText(/Escala decimal/), "0");
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Incremento/);
    expect(apiClient.registerProfile).not.toHaveBeenCalled();
  });
  it("rejects missing fractional and oversafe values before POST", async () => {
    const user = userEvent.setup();
    render(<ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    await fill(user, 1);
    await user.clear(screen.getByLabelText("Posición 1 · multiplicador"));
    await user.type(screen.getByLabelText("Posición 1 · multiplicador"), "1/3");
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/pagos enteros/);
    await user.clear(screen.getByLabelText("Posición 1 · multiplicador"));
    await user.type(screen.getByLabelText("Posición 1 · multiplicador"), "9007199254740992");
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/límite/);
    expect(apiClient.registerProfile).not.toHaveBeenCalled();
  });
  it("rejects same version locally, reports quota/conflict/422 and never auto-retries", async () => {
    const user = userEvent.setup();
    const existing = registered({ schema_version: 1, profile_id: "my-game", revision: 1, universe_size: 100, positions: 1,
      allows_repeats: true, multipliers: [{ numerator: 60, denominator: 1 }], currency: "DOP", scale: 2,
      stake_increment: 25, minimum_stake: 25, maximum_stake: 200, max_coverage: 3, max_exposure: 1000, best_rule: "maximum-payout/v1" });
    const view = render(<ProfileEditor templates={[]} profiles={[existing]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    await fill(user, 1);
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Ese ID y revisión ya existen/);
    expect(apiClient.registerProfile).not.toHaveBeenCalled();
    view.rerender(<ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    for (const [status, detail, expected] of [[409, "profile quota has insufficient headroom", /No hay espacio/],
      [409, "profile version conflicts with registered content", /revisión nueva/], [422, "invalid game profile", /El servidor rechazó el perfil/]] as const) {
      vi.mocked(apiClient.registerProfile).mockRejectedValueOnce(new ApiError(status, detail));
      await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(expected);
      if (status === 422) {
        await user.click(screen.getAllByText("Detalles técnicos").at(-1)!);
        expect(screen.getByText("Código HTTP:").parentElement).toHaveTextContent("422");
      }
      expect(apiClient.registerProfile).toHaveBeenCalledTimes(status === 422 ? 3 : detail.startsWith("profile version") ? 2 : 1);
    }
  });
  it("opens a collapsed host disclosure, keeps typed values and focuses the first invalid field linked to the error", async () => {
    const user = userEvent.setup();
    render(<details><summary>Host</summary><ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} /></details>);
    const host = screen.getByText("Host").closest("details") as HTMLDetailsElement;
    host.open = true;
    await user.click(screen.getByRole("button", { name: "Crear perfil de juego" }));
    await user.click(screen.getByText("Detalles técnicos"));
    await user.clear(screen.getByLabelText("ID nuevo del perfil"));
    await user.clear(screen.getByLabelText(/Revisión \(1/));
    await user.type(screen.getByLabelText(/Revisión \(1/), "7");
    host.open = false;
    fireEvent.submit(screen.getByRole("button", { name: "Guardar perfil" }).closest("form") as HTMLFormElement);
    expect(host.open).toBe(true);
    const alert = screen.getByRole("alert");
    expect(screen.getByLabelText("ID nuevo del perfil")).toHaveFocus();
    expect(screen.getByLabelText("ID nuevo del perfil")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("ID nuevo del perfil")).toHaveAttribute("aria-describedby", alert.id);
    expect(screen.getByLabelText(/Revisión \(1/)).toHaveValue("7");
    expect(apiClient.registerProfile).not.toHaveBeenCalled();
  });
  it("focuses the field that actually fails, and clears its invalid state when edited", async () => {
    const user = userEvent.setup();
    render(<ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    await user.click(screen.getByRole("button", { name: "Crear perfil de juego" }));
    await user.click(screen.getByText("Detalles técnicos"));
    await user.clear(screen.getByLabelText("ID nuevo del perfil"));
    await user.type(screen.getByLabelText("ID nuevo del perfil"), "my-game");
    await user.clear(screen.getByLabelText(/Revisión \(1/));
    await user.type(screen.getByLabelText(/Revisión \(1/), "1");
    await user.clear(screen.getByLabelText(/Tamaño del universo/));
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    expect(screen.getByLabelText(/Tamaño del universo/)).toHaveFocus();
    expect(screen.getByLabelText(/Tamaño del universo/)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("ID nuevo del perfil")).not.toHaveAttribute("aria-invalid");
    await user.type(screen.getByLabelText(/Tamaño del universo/), "100");
    expect(screen.getByLabelText(/Tamaño del universo/)).not.toHaveAttribute("aria-invalid");
  });
  it("holds the pending register lock until the single response completes", async () => {
    let resolve!: (value: ProfileListing) => void;
    vi.mocked(apiClient.registerProfile).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    const user = userEvent.setup();
    render(<ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    await fill(user, 1);
    const button = screen.getByRole("button", { name: "Guardar perfil" });
    fireEvent.click(button); fireEvent.click(button);
    expect(apiClient.registerProfile).toHaveBeenCalledTimes(1);
    expect(button).toBeDisabled();
    expect(screen.getByLabelText("ID nuevo del perfil")).toBeDisabled();
    expect(screen.getByText(/esperá la respuesta/)).toBeInTheDocument();
    const profile = vi.mocked(apiClient.registerProfile).mock.calls[0][0];
    await act(async () => { resolve(registered(profile)); });
    expect(onBusyChange).toHaveBeenCalledWith(false);
    expect(onRegistered).toHaveBeenCalledTimes(1);
  });
});
