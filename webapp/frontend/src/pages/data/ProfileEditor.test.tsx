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
  await user.click(screen.getByRole("button", { name: "Crear perfil" }));
  if (useTemplate) await user.selectOptions(screen.getByLabelText("Referencia opcional"), "0");
  await user.type(screen.getByLabelText("ID nuevo del perfil"), "my-game");
  await user.type(screen.getByLabelText(/Revisión \(1/), "1");
  if (!useTemplate) {
    await user.type(screen.getByLabelText(/Tamaño del universo/), "100");
    await user.type(screen.getByLabelText(/Posiciones por sorteo/), String(positions));
    await user.selectOptions(screen.getByLabelText(/Se repiten números/), "yes");
    await user.type(screen.getByLabelText(/Moneda \(código/), "DOP");
    for (let index = 0; index < positions; index++) await user.type(screen.getByLabelText(`Posición ${index + 1} · multiplicador`), ["60", "10", "5", "2", "1"][index] ?? "0");
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
  it.each([1, 3, 5])("creates %i position documents with explicit money policy and server-derived digest", async (count) => {
    const user = userEvent.setup();
    render(<ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    await fill(user, count);
    vi.mocked(apiClient.registerProfile).mockImplementationOnce(async (profile) => registered(profile));
    await user.click(screen.getByRole("button", { name: "Registrar perfil inmutable" }));
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
    await user.click(screen.getByRole("button", { name: "Crear perfil" }));
    await user.selectOptions(screen.getByLabelText("Referencia opcional"), "0");
    expect(screen.getByLabelText(/Posiciones por sorteo/)).toHaveValue("3");
    expect(screen.getByLabelText("Posición 1 · multiplicador")).toHaveValue("60/1");
    expect(screen.getByText(/1 unidad\(es\) sin escala/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Apuesta mínima/)).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "Registrar perfil inmutable" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/ID:/);
    expect(apiClient.registerProfile).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("ID nuevo del perfil"), "example");
    await user.type(screen.getByLabelText(/Revisión \(1/), "1");
    await user.type(screen.getByLabelText(/Escala decimal/), "0");
    await user.click(screen.getByRole("button", { name: "Registrar perfil inmutable" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Incremento/);
    expect(apiClient.registerProfile).not.toHaveBeenCalled();
  });
  it("rejects missing fractional and oversafe values before POST", async () => {
    const user = userEvent.setup();
    render(<ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    await fill(user, 1);
    await user.clear(screen.getByLabelText("Posición 1 · multiplicador"));
    await user.type(screen.getByLabelText("Posición 1 · multiplicador"), "1/3");
    await user.click(screen.getByRole("button", { name: "Registrar perfil inmutable" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/pagos enteros/);
    await user.clear(screen.getByLabelText("Posición 1 · multiplicador"));
    await user.type(screen.getByLabelText("Posición 1 · multiplicador"), "9007199254740992");
    await user.click(screen.getByRole("button", { name: "Registrar perfil inmutable" }));
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
    await user.click(screen.getByRole("button", { name: "Registrar perfil inmutable" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/ya están guardados/);
    expect(apiClient.registerProfile).not.toHaveBeenCalled();
    view.rerender(<ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    for (const [status, detail, expected] of [[409, "profile quota has insufficient headroom", /cuota/],
      [409, "profile version conflicts with registered content", /revisión nueva/], [422, "invalid game profile", /422/]] as const) {
      vi.mocked(apiClient.registerProfile).mockRejectedValueOnce(new ApiError(status, detail));
      await user.click(screen.getByRole("button", { name: "Registrar perfil inmutable" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(expected);
      expect(apiClient.registerProfile).toHaveBeenCalledTimes(status === 422 ? 3 : detail.startsWith("profile version") ? 2 : 1);
    }
  });
  it("holds the pending register lock until the single response completes", async () => {
    let resolve!: (value: ProfileListing) => void;
    vi.mocked(apiClient.registerProfile).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    const user = userEvent.setup();
    render(<ProfileEditor templates={[]} profiles={[]} onRegistered={onRegistered} onBusyChange={onBusyChange} />);
    await fill(user, 1);
    const button = screen.getByRole("button", { name: "Registrar perfil inmutable" });
    fireEvent.click(button); fireEvent.click(button);
    expect(apiClient.registerProfile).toHaveBeenCalledTimes(1);
    expect(button).toBeDisabled();
    expect(screen.getByLabelText("ID nuevo del perfil")).toBeDisabled();
    expect(screen.getByText(/respuesta pendiente/)).toBeInTheDocument();
    const profile = vi.mocked(apiClient.registerProfile).mock.calls[0][0];
    await act(async () => { resolve(registered(profile)); });
    expect(onBusyChange).toHaveBeenCalledWith(false);
    expect(onRegistered).toHaveBeenCalledTimes(1);
  });
});
