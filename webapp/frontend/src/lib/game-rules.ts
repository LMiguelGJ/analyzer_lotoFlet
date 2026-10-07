import type { Game, GameProfile, GameSettingsSource, ProfileListing, SettlementMode } from "../api/types";
import { formatDOP } from "./format";
import { formatProfileMoney } from "./profile-display";

/** Draft text stays text: this projection neither validates nor constructs a request. */
export interface ClassicRulesValues {
  name?: string;
  numbers: number | string;
  positions: number | string;
  prizes: readonly (number | string)[];
  allows_repeats?: boolean;
  minimum_stake: number | string;
}

export type GameRulesView = {
  kind: "classic";
  rules: ClassicRulesValues;
  provenance: string;
  source?: GameSettingsSource;
  draft: boolean;
  /** Historical requests expose no settlement/repetition fields. Do not infer them. */
  settlementContract: "classic" | "historical-unreported";
  settlement?: SettlementMode;
} | {
  kind: "profile";
  listing: ProfileListing;
  provenance: string;
  settlement?: SettlementMode;
};

export function classicRulesView(
  rules: Game | ClassicRulesValues,
  provenance: string,
  options: Partial<Pick<Extract<GameRulesView, { kind: "classic" }>, "source" | "draft" | "settlement" | "settlementContract">> = {},
): Extract<GameRulesView, { kind: "classic" }> {
  return { kind: "classic", rules, provenance, draft: false, settlementContract: "classic", ...options };
}

export function profileRulesView(listing: ProfileListing, provenance: string, settlement?: SettlementMode): Extract<GameRulesView, { kind: "profile" }> {
  return { kind: "profile", listing, provenance, settlement };
}

export const CLASSIC_SETTLEMENT_LABELS: Record<SettlementMode, string> = {
  all: "Sumar los premios",
  best: "Contar la primera posición coincidente por número",
};

export function profileSettlementLabel(profile: GameProfile, mode: SettlementMode): string {
  if (mode === "all") return "Sumar premios de todas las posiciones";
  return profile.best_rule === "maximum-payout/v1"
    ? "Mayor pago por número repetido"
    : "Primera posición coincidente por número (first-match/v0)";
}

export function gameSettingsSourceLabel(source?: GameSettingsSource): string {
  if (source === "stored") return "Guardadas desde la web";
  if (source === "environment") return "Variables de entorno LABORATORIO_GAME_*";
  if (source === "default") return "Predeterminadas";
  return "No informado por esta lectura";
}

export function classicRulesMoney(value: number | string): string {
  // Never parse a draft amount or replace invalid input with zero.
  return typeof value === "number" && Number.isInteger(value)
    ? formatDOP(value)
    : `${value || "Sin definir"} DOP (texto del borrador, pesos enteros)`;
}

export function profileRulesMoney(profile: GameProfile, value: number): string {
  try { return formatProfileMoney(value, profile.currency, profile.scale); }
  catch (error) {
    if (!(error instanceof RangeError)) throw error;
    return `${value} unidades nativas de ${profile.currency} (escala ${profile.scale}; formato no compatible)`;
  }
}
