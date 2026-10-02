import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient, NetworkError } from "../../api/client";
import { ProfileExperimentPage } from "./ProfileExperimentPage";
import { audazDataset, audazProfile, cyclingProfile, datasetItem, profileItem, recoveryDataset, recoveryProfile } from "./profile-model.test";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getProfiles: vi.fn(), getDatasets: vi.fn(),
    getDataset: vi.fn(), getDatasetDraws: vi.fn(), createProfileExperiment: vi.fn() } };
});
const id = "c".repeat(32);
function setup() {
  const router = createMemoryRouter([
    { path: "/experimentos/nuevo/perfil", element: <ProfileExperimentPage /> },
    { path: "/experimentos/:id", element: <p>Detalle creado</p> },
  ], { initialEntries: ["/experimentos/nuevo/perfil"] });
  const view = render(<RouterProvider router={router} />);
  return { ...view, router, user: userEvent.setup() };
}
async function selectChoices(user: ReturnType<typeof userEvent.setup>, profileId = "local-game") {
  await screen.findByRole("option", { name: new RegExp(`${profileId} · revisión 2`) });
  await user.selectOptions(screen.getByRole("combobox", { name: "Perfil y revisión" }), `${profileId}@2`);
  await screen.findByRole("option", { name: /local-json/ });
  await user.selectOptions(screen.getByRole("combobox", { name: "Versión de datos compatible" }), datasetItem.dataset_sha256);
  await screen.findByRole("option", { name: "2025-01-01 05:10" });
}
async function fill(user: ReturnType<typeof userEvent.setup>, profileId = "local-game") {
  await selectChoices(user, profileId);
  await user.selectOptions(screen.getByRole("combobox", { name: "Sorteo inicial" }), "2025-01-01 05:10");
  await user.type(screen.getByRole("textbox", { name: "Nombre de la sesión" }), "Sesión local");
  await user.type(screen.getByRole("textbox", { name: /Capital inicial/ }), "2000");
  await user.type(screen.getByRole("textbox", { name: /Meta de saldo final/ }), "2800");
  await user.type(screen.getByRole("textbox", { name: /Límite de sorteos transcurridos/ }), "12");
  await user.selectOptions(screen.getByRole("combobox", { name: "Liquidación explícita" }), "all");
  await user.type(screen.getByRole("textbox", { name: /Cobertura/ }), "2");
  await user.type(screen.getByRole("textbox", { name: /Números distintos/ }), "0,1");
  await user.type(screen.getByRole("textbox", { name: /Apuesta fija por número/ }), "1.25");
}

beforeEach(() => {
  vi.mocked(apiClient.getProfiles).mockReset().mockImplementation(async (offset = 0) => ({ total: 1, offset, limit: 20, items: [profileItem], templates: [] }));
  vi.mocked(apiClient.getDatasets).mockReset().mockImplementation(async (offset = 0) => ({ total: 1, offset, limit: 20, items: [datasetItem] }));
  vi.mocked(apiClient.getDataset).mockReset().mockResolvedValue(datasetItem);
  vi.mocked(apiClient.getDatasetDraws).mockReset().mockImplementation(async (_sha, offset = 0) => ({ total: 1, offset, limit: 100, items: ["2025-01-01 05:10"] }));
  vi.mocked(apiClient.createProfileExperiment).mockReset().mockResolvedValue({ id, status: "pending" });
});

describe("profile session creator", () => {
  it("submits explicitly selected Q80 cycling without fixed stake and blocks uncertain duplicate", async () => {
    vi.mocked(apiClient.getProfiles).mockResolvedValue({ total: 1, offset: 0, limit: 20,
      items: [cyclingProfile], templates: [] });
    const { user } = setup();
    await fill(user);
    await user.selectOptions(screen.getByRole("combobox", { name: "Política de apuesta" }), "cycling");
    expect(screen.queryByRole("textbox", { name: /Apuesta fija por número/ })).not.toBeInTheDocument();
    vi.mocked(apiClient.createProfileExperiment).mockRejectedValueOnce(new NetworkError());
    await user.dblClick(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Podría estar en la cola/);
    expect(apiClient.createProfileExperiment).toHaveBeenCalledTimes(1);
    const body = vi.mocked(apiClient.createProfileExperiment).mock.calls[0][0];
    expect(body).toMatchObject({ schema_version: 2, staking: { capability: "q80-first-prize-cycling/v1" } });
    expect(JSON.stringify(body)).not.toContain("per_number_stake");
  });
  it("offers generic Audaz only for server-compatible selected coverage and posts schema 3", async () => {
    vi.mocked(apiClient.getProfiles).mockResolvedValue({ total: 1, offset: 0, limit: 20,
      items: [audazProfile], templates: [] });
    vi.mocked(apiClient.getDatasets).mockResolvedValue({ total: 1, offset: 0, limit: 20,
      items: [audazDataset] });
    vi.mocked(apiClient.getDataset).mockResolvedValue(audazDataset);
    const { user } = setup();
    await fill(user, "rational-game");
    await user.clear(screen.getByRole("textbox", { name: /Cobertura/ }));
    await user.type(screen.getByRole("textbox", { name: /Cobertura/ }), "1");
    await user.clear(screen.getByRole("textbox", { name: /Números distintos/ }));
    await user.type(screen.getByRole("textbox", { name: /Números distintos/ }), "0");
    const policy = screen.getByRole("combobox", { name: "Política de apuesta" });
    expect(within(policy).getByRole("option", { name: /Audaz/ })).toBeInTheDocument();
    await user.selectOptions(policy, "audaz");
    expect(screen.queryByRole("textbox", { name: /Apuesta fija por número/ })).not.toBeInTheDocument();
    expect(screen.getByText(/hasta cobertura 1/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" }));
    await waitFor(() => expect(apiClient.createProfileExperiment).toHaveBeenCalledTimes(1));
    const body = vi.mocked(apiClient.createProfileExperiment).mock.calls[0][0];
    expect(body).toMatchObject({ schema_version: 3, selector: { coverage: 1 },
      staking: { capability: "profile-audaz/v1" } });
    expect(JSON.stringify(body)).not.toContain("per_number_stake");
  });
  it.each(["cycle", "stop"] as const)("submits schema-4 recovery with explicit target, rounds, compatible coverage and %s mode", async (end_mode) => {
    vi.mocked(apiClient.getProfiles).mockResolvedValue({ total: 1, offset: 0, limit: 20,
      items: [recoveryProfile], templates: [] });
    vi.mocked(apiClient.getDatasets).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [recoveryDataset] });
    vi.mocked(apiClient.getDataset).mockResolvedValue(recoveryDataset);
    const { user } = setup();
    await fill(user, "rational-recovery");
    await user.selectOptions(screen.getByRole("combobox", { name: "Política de apuesta" }), "recovery");
    await user.type(screen.getByRole("textbox", { name: /Margen objetivo/ }), "12.34");
    await user.type(screen.getByRole("textbox", { name: /Rondas de recuperación/ }), "4");
    await user.selectOptions(screen.getByRole("combobox", { name: "Al completar las rondas" }), end_mode);
    await user.click(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" }));
    await waitFor(() => expect(apiClient.createProfileExperiment).toHaveBeenCalledTimes(1));
    expect(apiClient.createProfileExperiment).toHaveBeenCalledWith(expect.objectContaining({ schema_version: 4,
      selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 2, numbers: [0, 1], seed: null, algorithm_version: null },
      staking: { schema_version: 1, target_margin: 1234, rounds: 4, end_mode } }));
    expect(JSON.stringify(vi.mocked(apiClient.createProfileExperiment).mock.calls[0][0])).not.toContain("per_number_stake");
  });
  it("does not POST recovery if current server compatibility withdraws coverage", async () => {
    vi.mocked(apiClient.getProfiles).mockResolvedValueOnce({ total: 1, offset: 0, limit: 20,
      items: [recoveryProfile], templates: [] });
    vi.mocked(apiClient.getDatasets).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [recoveryDataset] });
    vi.mocked(apiClient.getDataset).mockResolvedValue(recoveryDataset);
    vi.mocked(apiClient.getProfiles).mockResolvedValueOnce({ total: 1, offset: 0, limit: 20, templates: [], items: [{
      ...recoveryProfile, profile_execution: { ...recoveryProfile.profile_execution, staking_capabilities: ["flat-per-number/v1"],
        recovery_compatibility: { available: false, maximum_compatible_coverage: 0, coverage_rule: "strict", parameters: [] } },
    }] });
    const { user } = setup();
    await fill(user, "rational-recovery");
    await user.selectOptions(screen.getByRole("combobox", { name: "Política de apuesta" }), "recovery");
    await user.type(screen.getByRole("textbox", { name: /Margen objetivo/ }), "10");
    await user.type(screen.getByRole("textbox", { name: /Rondas de recuperación/ }), "2");
    await user.selectOptions(screen.getByRole("combobox", { name: "Al completar las rondas" }), "stop");
    await user.click(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/cambiaron/);
    expect(apiClient.createProfileExperiment).not.toHaveBeenCalled();
  });
  it.each(["selector_capabilities", "settlements", "entry_policies"] as const)(
    "does not POST when the server withdraws %s at recheck", async (capability) => {
      vi.mocked(apiClient.getProfiles).mockResolvedValueOnce({ total: 1, offset: 0, limit: 20,
        items: [profileItem], templates: [] });
      vi.mocked(apiClient.getProfiles).mockResolvedValueOnce({ total: 1, offset: 0, limit: 20,
        items: [{ ...profileItem, profile_execution: {
          ...profileItem.profile_execution, [capability]: [],
        } }], templates: [] });
      const { user } = setup();
      await fill(user);
      await user.click(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(/cambiaron/);
      expect(apiClient.createProfileExperiment).not.toHaveBeenCalled();
    },
  );
  it("does not POST Q80 if the server withdraws the capability at recheck", async () => {
    vi.mocked(apiClient.getProfiles).mockResolvedValueOnce({ total: 1, offset: 0, limit: 20,
      items: [cyclingProfile], templates: [] });
    const { user } = setup();
    await fill(user);
    await user.selectOptions(screen.getByRole("combobox", { name: "Política de apuesta" }), "cycling");
    await user.click(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/cambiaron/);
    expect(apiClient.createProfileExperiment).not.toHaveBeenCalled();
  });
  it("creates the exact request once and opens existing detail", async () => {
    const { user, router } = setup();
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" }));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/experimentos/${id}`));
    expect(apiClient.createProfileExperiment).toHaveBeenCalledTimes(1);
    expect(vi.mocked(apiClient.createProfileExperiment).mock.calls[0][0]).toMatchObject({
      kind: "profile", dataset_sha256: datasetItem.dataset_sha256,
      profile_sha256: profileItem.profile_sha256, conditions: { capital: 200000, goal: 280000, settlement: "all" },
      selector: { capability: "static-numbers/v1", numbers: [0, 1] },
      staking: { capability: "flat-per-number/v1", per_number_stake: 125 },
    });
  });
  it("finds profiles, datasets and draws beyond the first page and date filter", async () => {
    vi.mocked(apiClient.getProfiles).mockImplementation(async (offset = 0) => ({ total: 21, offset, limit: 20,
      items: offset ? [profileItem] : [{ ...profileItem, profile: { ...profileItem.profile, profile_id: "other" } }], templates: [] }));
    vi.mocked(apiClient.getDatasets).mockImplementation(async (offset = 0) => ({ total: 21, offset, limit: 20,
      items: offset ? [datasetItem] : [{ ...datasetItem, dataset_sha256: "d".repeat(64) }] }));
    vi.mocked(apiClient.getDatasetDraws).mockImplementation(async (_sha, offset = 0, _limit, date) => ({ total: date ? 1 : 101, offset, limit: 100,
      items: date ? ["2025-01-01 05:10"] : offset ? ["2025-01-01 05:10"] : ["2024-12-30 05:10"] }));
    const { user } = setup();
    await screen.findByRole("option", { name: /other/ });
    await user.click(screen.getByRole("navigation", { name: "Páginas de perfiles" }).querySelector("button:last-child")!);
    await user.selectOptions(screen.getByRole("combobox", { name: "Perfil y revisión" }), "local-game@2");
    await user.click(screen.getByRole("navigation", { name: "Páginas de datos" }).querySelector("button:last-child")!);
    await user.selectOptions(screen.getByRole("combobox", { name: "Versión de datos compatible" }), datasetItem.dataset_sha256);
    await screen.findByRole("option", { name: "2024-12-30 05:10" });
    await user.click(screen.getByRole("navigation", { name: "Páginas de sorteos" }).querySelector("button:last-child")!);
    expect(await screen.findByRole("option", { name: "2025-01-01 05:10" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Filtrar sorteos por fecha"), "2025-01-01");
    expect(await screen.findByRole("option", { name: "2025-01-01 05:10" })).toBeInTheDocument();
    expect(apiClient.getProfiles).toHaveBeenCalledWith(20, 20);
    expect(apiClient.getDatasets).toHaveBeenCalledWith(20, 20);
    expect(apiClient.getDatasetDraws).toHaveBeenCalledWith(datasetItem.dataset_sha256, 0, 100, "2025-01-01");
  });
  it("blocks stale server bindings before POST, and preserves the draft", async () => {
    const { user } = setup();
    await fill(user);
    vi.mocked(apiClient.getDataset).mockResolvedValueOnce({ ...datasetItem, profile_sha256: "e".repeat(64) });
    await user.click(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/cambiaron/);
    expect(apiClient.createProfileExperiment).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox", { name: "Nombre de la sesión" })).toHaveValue("Sesión local");
  });
  it("does not lock submission when preflight failed before any POST", async () => {
    const { user } = setup(); await fill(user);
    vi.mocked(apiClient.getDataset).mockRejectedValueOnce(new NetworkError());
    await user.click(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/No se envió la sesión/);
    expect(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" })).toBeEnabled();
    expect(apiClient.createProfileExperiment).not.toHaveBeenCalled();
  });
  it("never automatically resubmits after an uncertain network outcome or double click", async () => {
    const { user } = setup(); await fill(user);
    vi.mocked(apiClient.createProfileExperiment).mockRejectedValueOnce(new NetworkError());
    await user.dblClick(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Podría estar en la cola/);
    expect(screen.getByRole("button", { name: "Crear sesión y agregar a la cola" })).toBeDisabled();
    expect(apiClient.createProfileExperiment).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "Comprobá Experimentos" })).toHaveAttribute("href", "/experimentos");
  });
  it("shows no false compatibility and keeps keyboard-labeled controls accessible", async () => {
    vi.mocked(apiClient.getDatasets).mockResolvedValue({ total: 1, offset: 0, limit: 20,
      items: [{ ...datasetItem, profile_sha256: "e".repeat(64) }] });
    const { user, container } = setup();
    await screen.findByRole("option", { name: /local-game/ });
    await user.selectOptions(screen.getByRole("combobox", { name: "Perfil y revisión" }), "local-game@2");
    expect(screen.getByRole("combobox", { name: "Versión de datos compatible" }).querySelectorAll("option")).toHaveLength(1);
    expect(screen.getByText(/No hay datos compatibles/)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
