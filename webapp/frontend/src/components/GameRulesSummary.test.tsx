import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ProfileListing } from "../api/types";
import { classicRulesView, profileRulesView } from "../lib/game-rules";
import { GameRulesSummary } from "./GameRulesSummary";

describe("GameRulesSummary", () => {
  it("shows a native revision, exact prizes and money in its own currency without editable controls", () => {
    const listing: ProfileListing = {
      profile: { schema_version: 1, profile_id: "eur-profile", revision: 9, universe_size: 12,
        positions: 1, allows_repeats: false, multipliers: [{ numerator: 7, denominator: 3 }], currency: "EUR",
        scale: 2, minimum_stake: 125, maximum_stake: 500, stake_increment: 5, max_coverage: 2,
        max_exposure: 1000, best_rule: "maximum-payout/v1" },
      profile_sha256: "b".repeat(64), execution_supported: false,
      profile_execution: { ready: false, selector_capabilities: [], staking_capabilities: [], entry_policies: [],
        settlements: ["best"], requires_compatible_dataset: true },
    };
    render(<GameRulesSummary view={profileRulesView(listing, "catalog /catalog/profiles", "best")} />);
    const summary = screen.getByLabelText("Resumen de reglas de perfil");
    expect(within(summary).getByText("eur-profile")).toBeInTheDocument();
    expect(within(summary).getByText("9")).toBeInTheDocument();
    expect(within(summary).getByText("b".repeat(64))).toBeInTheDocument();
    expect(within(summary).getByText(/multiplicador exacto 7\/3/)).toBeInTheDocument();
    expect(within(summary).getByText("EUR 1.25")).toBeInTheDocument();
    expect(summary).not.toHaveTextContent("RD$");
    expect(within(summary).queryByRole("textbox")).not.toBeInTheDocument();
    expect(within(summary).getByText(/Ejecución no soportada/)).toBeInTheDocument();
    expect(within(summary).getByText(/"minimum_stake": 125/)).toBeInTheDocument();
  });

  it("does not invent repetition or settlement fields for a historical draft", () => {
    render(<GameRulesSummary view={classicRulesView({ numbers: "100", positions: "1", prizes: ["80"], minimum_stake: "" }, "saved backtest", { draft: true, settlementContract: "historical-unreported" })} />);
    expect(screen.getByText("No informadas por este contrato")).toBeInTheDocument();
    expect(screen.getByText(/contrato histórico no expone/)).toBeInTheDocument();
    expect(screen.getByText(/no proporciona ID, revisión/)).toBeInTheDocument();
  });
});
