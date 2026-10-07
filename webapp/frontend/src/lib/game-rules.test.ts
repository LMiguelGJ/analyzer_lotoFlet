import { describe, expect, it } from "vitest";
import type { ProfileListing } from "../api/types";
import { CLASSIC_SETTLEMENT_LABELS, classicRulesMoney, classicRulesView, profileRulesMoney, profileRulesView, profileSettlementLabel } from "./game-rules";

const listing: ProfileListing = {
  profile: { schema_version: 1, profile_id: "usd-native", revision: 7, universe_size: 100,
    positions: 2, allows_repeats: true, multipliers: [{ numerator: 7, denominator: 3 }, { numerator: 80, denominator: 1 }],
    currency: "USD", scale: 2, stake_increment: 5, minimum_stake: 125, maximum_stake: 2500,
    max_coverage: 4, max_exposure: 10000, best_rule: "maximum-payout/v1" },
  profile_sha256: "a".repeat(64), execution_supported: true,
  profile_execution: { ready: true, selector_capabilities: [], staking_capabilities: [], entry_policies: [],
    settlements: ["all", "best"], requires_compatible_dataset: true },
};

describe("non-destructive rules projection", () => {
  it("retains exact native revision, digest, rational prizes and limits without calculating payouts", () => {
    const before = JSON.stringify(listing);
    const view = profileRulesView(listing, "catalog snapshot", "best");
    expect(view.kind).toBe("profile");
    expect(view.listing).toBe(listing);
    expect(view.listing.profile.multipliers[0]).toEqual({ numerator: 7, denominator: 3 });
    expect(JSON.stringify(listing)).toBe(before);
    expect(profileRulesMoney(listing.profile, 125)).toBe("USD 1.25");
  });

  it("keeps classic first-match best distinct from profile maximum payout and respects native v0", () => {
    expect(CLASSIC_SETTLEMENT_LABELS.best).toContain("primera posición coincidente");
    expect(profileSettlementLabel(listing.profile, "best")).toContain("Mayor pago");
    expect(profileSettlementLabel({ ...listing.profile, best_rule: "first-match/v0" }, "best")).toContain("first-match/v0");
  });

  it("preserves incomplete draft text instead of parsing, rounding or replacing it", () => {
    const rules = { numbers: "", positions: "2", prizes: ["1.25", ""], minimum_stake: "0001" };
    const view = classicRulesView(rules, "historical draft", { draft: true, settlementContract: "historical-unreported" });
    expect(view.rules).toBe(rules);
    expect(view.rules.allows_repeats).toBeUndefined();
    expect(classicRulesMoney("1.25")).toContain("1.25 DOP");
    expect(classicRulesMoney("0001")).toContain("0001 DOP");
    expect(classicRulesMoney(125)).toBe("RD$125");
  });

  it("retains raw native units when the existing formatter cannot support a scale", () => {
    expect(profileRulesMoney({ ...listing.profile, scale: 7 }, 125)).toBe("125 unidades nativas de USD (escala 7; formato no compatible)");
  });
});
