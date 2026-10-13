import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getReferenceLabs } from "../../api/referenceLabs";
import { CatalogPage } from "./CatalogPage";
import type { ReferenceCatalog } from "../../api/referenceLabs";
vi.mock("../../api/referenceLabs", () => ({ getReferenceLabs: vi.fn() }));

const ids = ["transicion_1_audaz", "frios_1_audaz", "selector_1_audaz", "mezclas_1_audaz", "ensemble_5_audaz", "ensemble_10_audaz", "ensemble_20_audaz", "frios_25_escalera", "mezclas_50_audaz", "transicion_50_audaz", "paridad_50_audaz", "frios_50_escalera", "paridad_50_escalera", "paridad_50_plana"];
const catalog: ReferenceCatalog = {
  contract_version: 1,
  reference_history: { sha256: "d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711", origin: "frozen_reference", draws: 105426, ranked_draws: 100, first_label: "2025-03-05", last_label: "2026-09-25" },
  capabilities: { session_summary: true, per_bet_trace: false },
  items: ids.map((lab_id) => ({ lab_id, system: lab_id.startsWith("transicion") ? "transition" : lab_id.startsWith("frios") ? "cold" : lab_id.startsWith("mezclas") ? "mix" : lab_id.startsWith("paridad") ? "parity" : lab_id.startsWith("ensemble") ? "ensemble" : "select_interpretable", coverage: Number(lab_id.match(/_(\d+)_/)?.[1] ?? 1), stake_style: lab_id.endsWith("escalera") ? "ladder" as const : lab_id.endsWith("plana") ? "flat" as const : "bold" as const, selection_kind: lab_id.startsWith("paridad") ? "parity" as const : "ranking" as const, capital: 2000, goal: 2800, prizes: [80, 8, 4, 2, 1], window: { start: "2025-09-02 05:10", end: "2026-09-25 18:20" }, duration_cap: null, editable: false as const })),
};
const getCatalogMock = vi.mocked(getReferenceLabs);
beforeEach(() => { getCatalogMock.mockReset(); getCatalogMock.mockResolvedValue(catalog); });

describe("reference laboratories catalog", () => {
  it("links all fourteen named immutable laboratories to separate routes and shows frozen provenance", async () => {
    render(<MemoryRouter><CatalogPage /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Laboratorios de referencia" })).toBeInTheDocument();
    const links = screen.getAllByRole("link").filter((link) => link.getAttribute("href")?.startsWith("/laboratorios/"));
    expect(links).toHaveLength(14);
    expect(links[0]).toHaveAttribute("href", "/laboratorios/transicion_1_audaz");
    expect(links[0]).toHaveTextContent("Transición · 1 número · Audaz");
    expect(screen.getByText(catalog.reference_history.sha256)).toBeInTheDocument();
    expect(screen.getByText(/14 laboratorios disponibles/)).toBeInTheDocument();
    const { axe } = await import("jest-axe");
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("keeps a network failure visible and exposes recovery rather than an empty catalog", async () => {
    getCatalogMock.mockRejectedValueOnce(new Error("offline"));
    render(<MemoryRouter><CatalogPage /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar los laboratorios.");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
