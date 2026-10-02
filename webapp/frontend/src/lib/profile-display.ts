import type { ProfileExperimentSummary, ProfileRunResult } from "../api/types";

/** Profile amounts are exact integer minor units; formatting never computes a payout. */
export function formatProfileMoney(amount: number, currency: string, scale: number): string {
  if (!Number.isSafeInteger(amount) || !Number.isInteger(scale) || scale < 0 || scale > 6) {
    throw new RangeError("Profile money must be safe integer units with a supported scale");
  }
  const negative = amount < 0 ? "-" : "";
  const digits = BigInt(amount < 0 ? -amount : amount).toString().padStart(scale + 1, "0");
  const integer = scale ? digits.slice(0, -scale) : digits;
  const fraction = scale ? `.${digits.slice(-scale)}` : "";
  return `${negative}${currency} ${BigInt(integer).toLocaleString("es-DO")}${fraction}`;
}

export function profileMoney(data: ProfileExperimentSummary, amount: number): string {
  return formatProfileMoney(amount, data.display.currency, data.display.scale);
}

export const PROFILE_OUTCOME_LABELS: Record<ProfileRunResult["outcome"], string> = {
  goal: "Meta alcanzada", ruin: "Quiebre", limit: "Límite de sesión",
  history_exhausted: "Historial agotado", cancelled: "Cancelado durante la sesión",
};

export const PROFILE_COLLISION_LABELS: Record<string, string> = {
  goal: "meta", ruin: "quiebre", max_bet_draws: "límite de sorteos apostados",
  max_elapsed_draws: "límite de sorteos transcurridos", end_minute: "hora límite",
  duration_minutes: "duración límite", recovery_round_limit: "límite de rondas de recuperación",
};

export function profileOutcome(result: ProfileRunResult): string {
  const reasons = result.collisions.map((reason) => PROFILE_COLLISION_LABELS[reason] ?? reason);
  return `${PROFILE_OUTCOME_LABELS[result.outcome]}${reasons.length ? ` (${reasons.join(", ")})` : ""}`;
}
