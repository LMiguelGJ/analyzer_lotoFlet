/** Mirrors webapp/backend/laboratorio/domain/contracts.py and api/*.py response shapes. */

export type SelectorKind = "system" | "blend" | "random" | "parity";
export type StakingStyle = "flat" | "ladder" | "bold";
export type SettlementMode = "all" | "best";

/** Execution status vocabulary (contracts.ExperimentStatus / RunStatus). Never conflated with Outcome. */
export type ExperimentStatus =
  | "pending"
  | "held"
  | "running"
  | "completed"
  | "cancelled"
  | "interrupted"
  | "failed";

export type RunStatus =
  | "pending"
  | "running"
  | "completed"
  | "cancelled"
  | "not_run"
  | "interrupted"
  | "failed";

/** Session outcome vocabulary (contracts.Outcome). Distinct from ExperimentStatus/RunStatus. */
export type Outcome = "goal" | "ruin" | "limit" | "history_exhausted";

export interface BlendComponent {
  system: string;
  weight: number;
}

export interface Strategy {
  name: string;
  selector: SelectorKind;
  system?: string | null;
  components?: BlendComponent[] | null;
  coverage: number;
  staking: StakingStyle;
}

export interface Conditions {
  start_draw: string;
  capital: number;
  goal: number;
  settlement: SettlementMode;
  max_bets?: number | null;
  max_minutes?: number | null;
  /** 0..Number.MAX_SAFE_INTEGER (see [F16]): the largest range JSON.parse/response.json() round-trip exactly. */
  seed: number;
}

export interface ExperimentRequest {
  name: string;
  conditions: Conditions;
  strategies: Strategy[];
}

export interface Page<T> {
  total: number;
  offset: number;
  limit: number;
  items: T[];
}

export interface StartingDrawAvailability {
  date: string;
  history_total: number;
  ranked_total: number;
}

export interface Game {
  name: string;
  numbers: number;
  positions: number;
  prizes: number[];
  allows_repeats: boolean;
}

/** Exact integer rational payout, never a floating-point multiplier. */
export interface PayoutMultiplier {
  numerator: number;
  denominator: number;
}

/** Versioned profile document. Profile-engine readiness is reported separately by the server. */
export interface GameProfile {
  schema_version: number;
  profile_id: string;
  revision: number;
  universe_size: number;
  positions: number;
  allows_repeats: boolean;
  multipliers: PayoutMultiplier[];
  currency: string;
  scale: number;
  stake_increment: number;
  minimum_stake: number;
  maximum_stake: number;
  max_coverage: number;
  max_exposure: number;
  best_rule: "maximum-payout/v1" | "first-match/v0";
}

export interface ProfileExecution {
  ready: boolean;
  selector_capabilities: readonly string[];
  staking_capabilities: readonly string[];
  entry_policies: readonly string[];
  settlements: readonly SettlementMode[];
  requires_compatible_dataset: boolean;
  audaz_compatibility?: {
    available: boolean;
    maximum_compatible_coverage: number;
    coverage_rule: string;
  };
  recovery_compatibility?: {
    available: boolean;
    maximum_compatible_coverage: number;
    coverage_rule: string;
    parameters: readonly string[];
  };
}

export interface ProfileListing {
  profile: GameProfile;
  /** Server-derived digest; never computed in the browser. */
  profile_sha256: string;
  execution_supported: boolean;
  profile_execution: ProfileExecution;
}

/** Reference metadata only: missing fields prevent treating it as a persisted profile. */
export interface PartialProfileTemplate {
  name: string;
  provenance: string;
  known_fields: Partial<Pick<GameProfile,
    "universe_size" | "positions" | "allows_repeats" | "multipliers" | "currency" | "minimum_stake">>;
  missing_fields: (keyof GameProfile)[];
  execution_supported: false;
}

export interface ProfileCatalog extends Page<ProfileListing> {
  templates: PartialProfileTemplate[];
}

/** Import requests carry the original file bytes, never decoded/re-encoded text. */
export interface ImportRequest {
  raw_base64: string;
  format: "csv" | "json";
  mapping: { date: string; time: string; positions: string[] };
  source: { source_id: string; kind: "historical" | "artificial"; revision: string; provenance: string };
  clock: { mode: "naive_legacy" | "iana"; zone: string | null };
  profile: GameProfile;
}

export interface ImportPreview {
  promotable: boolean;
  source_sha256: string;
  dataset_sha256: string | null;
  rows_seen: number;
  records_total: number;
  duplicates_merged: number;
  error_count: number;
  errors_truncated: boolean;
  errors: { row: number | null; code: string; message: string }[];
  sample: { date: string; time: string; numbers: number[] }[];
  execution_supported: false;
}

/** Inert discovery projection; inline profile snapshots need not be separately registered. */
export interface DatasetListing {
  dataset_sha256: string;
  source_sha256: string;
  created_at: string;
  source_id: string;
  source_revision: string;
  profile_id: string;
  profile_revision: number;
  positions: number;
  universe_size: number;
  records_total: number;
  first_draw: string;
  last_draw: string;
  clock: ImportRequest["clock"];
  execution_supported: false;
  profile_sha256: string;
  profile_execution: ProfileExecution;
}

export interface ImportPromotion {
  dataset_sha256: string;
  created_at: string;
  created: boolean;
  duplicate_source_differs: boolean;
  retained_source_sha256: string;
  submitted_source_sha256: string;
  rows_seen: number;
  records_total: number;
  duplicates_merged: number;
  execution_supported: false;
}

export interface Sources {
  history_sha256: string;
  rankings_sha256: string;
  history_id: string;
  rankings_id: string;
  code_version: string;
  first_draw?: string;
  last_draw?: string;
}

export interface Catalog {
  game: Game;
  systems: Record<string, string>;
  selectors: SelectorKind[];
  coverages: number[];
  parity_coverage: number;
  starting_draws: string[];
  starting_draws_total: number;
  sources: Sources;
}

/** Mirrors domain/session.py's Bet, as serialized by asdict() in api/experiments.py's replay(). */
export interface Bet {
  label: string;
  numbers: number[];
  per_number: number;
  wagered: number;
  results: number[];
  paid: number;
  balance: number;
}

/** Mirrors domain/session.py's SessionResult; the full shape including `bets`. */
export interface SessionResult {
  outcome: Outcome;
  bets_count: number;
  wagered: number;
  paid: number;
  final_balance: number;
  bets: Bet[];
}

/** api/__init__.py's run_summary() strips `bets` and projects delta from the saved request's capital. */
export interface FinancialMetrics {
  /** Optional only for older response fixtures; absent is unavailable, not zero. */
  net?: number;
  return_per_wagered?: number | null;
  roi?: number | null;
  max_drawdown?: number;
  metric_scope?: "saved_individual_run";
  ratio_rounding?: "decimal-half-up-6";
}

export interface TrajectoryPoint {
  source_index: number;
  label: string;
  balance: number;
  replay: string;
}

export interface Trajectory {
  result_kind?: "profile";
  schema_version?: 2 | 3 | 4;
  initial_capital: number;
  total: number;
  max_points: number;
  reduction_method: "none" | "minmax-even-v1";
  minimum: { balance: number; source_index: number | null };
  maximum: { balance: number; source_index: number | null };
  points: TrajectoryPoint[];
}

export type RunResult = Omit<SessionResult, "bets"> & FinancialMetrics & { delta: number };

export interface LegacyRunSummary {
  result_kind?: "legacy";
  ordinal: number;
  configuration_id: string | null;
  status: RunStatus;
  result: RunResult | null;
  bets_count: number;
}

export type RunSummary = LegacyRunSummary;

export interface LegacyExperimentSummary {
  /** Historical responses omit this discriminator. */
  request_kind?: "legacy";
  id: string;
  /** UTC ISO timestamp; null for records created before migration 0002. Optional only for older captured frontend fixtures. */
  created_at?: string | null;
  status: ExperimentStatus;
  request: ExperimentRequest;
  /** Always present in current API; optional for pre-schema-4 captured fixtures. */
  profile?: GameProfile;
  sources: {
    history_id: string;
    history_sha256: string;
    rankings_id: string;
    rankings_sha256: string;
    code_version: string;
  };
  runs: LegacyRunSummary[];
}

export interface ProfileConditions {
  schema_version: number;
  start_draw: string;
  capital: number;
  goal: number;
  settlement: SettlementMode;
  max_elapsed_draws: number | null;
  max_bet_draws: number | null;
  end_minute: number | null;
  duration_minutes: number | null;
}

interface ProfileRequestBase {
  kind: "profile";
  name: string;
  dataset_sha256: string;
  profile_id: string;
  profile_revision: number;
  profile_sha256: string;
  entry_policy: string;
  conditions: ProfileConditions;
  selector: { schema_version: number; capability: string; coverage: number; numbers: number[] | null; seed: number | null; algorithm_version: string | null };
}

export interface ProfileExperimentRequest extends ProfileRequestBase {
  schema_version: 1;
  staking: { schema_version: 1; capability: string; per_number_stake: number };
}

/** Schema 2 has a dynamic stake; there is no flat per-number amount in its request. */
export interface ProfileCyclingRequest extends ProfileRequestBase {
  schema_version: 2;
  staking: { schema_version: 1; capability: "q80-first-prize-cycling/v1" };
}

/** Schema 3 selects generic audaz staking dynamically from profile and session state. */
export interface ProfileAudazRequest extends ProfileRequestBase {
  schema_version: 3;
  staking: { schema_version: 1; capability: "profile-audaz/v1" };
}

/** Schema 4 carries explicit profile-money margin, ladder length and exhaustion behavior. */
export interface ProfileRecoveryRequest extends ProfileRequestBase {
  schema_version: 4;
  staking: { schema_version: 1; target_margin: number; rounds: number; end_mode: "cycle" | "stop" };
}

export interface ProfileBet {
  label: string;
  stakes: [number, number][];
  results: number[];
  wagered: number;
  paid: number;
  balance: number;
}

export interface ProfileRunResult extends FinancialMetrics {
  /** run_summary() projects asdict(result), without the full result envelope's kind/bets. */
  schema_version: 1 | 2 | 3 | 4;
  profile_id: string;
  profile_revision: number;
  outcome: Outcome | "cancelled";
  collisions: string[];
  elapsed_draws: number;
  bet_draws: number;
  wagered: number;
  paid: number;
  final_balance: number;
  delta: number;
}

export interface ProfileRunSummary {
  result_kind: "profile";
  ordinal: number;
  configuration_id: string | null;
  status: RunStatus;
  result: ProfileRunResult | null;
  bets_count: number;
}

interface ProfileSummaryBase {
  request_kind: "profile";
  id: string;
  created_at?: string | null;
  status: ExperimentStatus;
  profile: GameProfile;
  display: { name: string; currency: string; scale: number; capital: number; goal: number; selector_label: string; staking_label: string };
  sources: LegacyExperimentSummary["sources"];
  runs: ProfileRunSummary[];
}

export interface ProfileV1ExperimentSummary extends ProfileSummaryBase {
  request: ProfileExperimentRequest;
  runs: (ProfileRunSummary & { result: (ProfileRunResult & { schema_version: 1 }) | null })[];
}
export interface ProfileCyclingExperimentSummary extends ProfileSummaryBase {
  request: ProfileCyclingRequest;
  runs: (ProfileRunSummary & { result: (ProfileRunResult & { schema_version: 2 }) | null })[];
}
export interface ProfileAudazExperimentSummary extends ProfileSummaryBase {
  request: ProfileAudazRequest;
  runs: (ProfileRunSummary & { result: (ProfileRunResult & { schema_version: 3 }) | null })[];
}
export interface ProfileRecoveryExperimentSummary extends ProfileSummaryBase {
  request: ProfileRecoveryRequest;
  runs: (ProfileRunSummary & { result: (ProfileRunResult & { schema_version: 4 }) | null })[];
}
export type ProfileExperimentSummary = ProfileV1ExperimentSummary | ProfileCyclingExperimentSummary | ProfileAudazExperimentSummary | ProfileRecoveryExperimentSummary;

export type ExperimentSummary = LegacyExperimentSummary | ProfileExperimentSummary;
export type AnyRunSummary = LegacyRunSummary | ProfileRunSummary;

export interface LegacyCompareResult {
  id: string;
  status: ExperimentStatus;
  completed: number;
  requested: number;
  complete: boolean;
  request_kind?: "legacy";
  runs: LegacyRunSummary[];
}

export interface ProfileCompareResult extends Omit<LegacyCompareResult, "request_kind" | "runs"> {
  request_kind: "profile";
  runs: ProfileRunSummary[];
}

export type CompareResult = LegacyCompareResult | ProfileCompareResult;

export type ProfileReplayPage = (Page<ProfileBet> & { result_kind: "profile"; schema_version?: never })
  | (Page<ProfileBet> & { result_kind: "profile"; schema_version: 2 | 3 | 4 });
export type ReplayPage = (Page<Bet> & { result_kind?: "legacy" }) | ProfileReplayPage;

export function isProfileExperiment(value: ExperimentSummary): value is ProfileExperimentSummary {
  return value.request_kind === "profile";
}
export function isProfileRun(value: AnyRunSummary): value is ProfileRunSummary {
  return value.result_kind === "profile";
}
export function isProfileComparison(value: CompareResult): value is ProfileCompareResult {
  return value.request_kind === "profile";
}
/** The replay endpoint discriminates profile pages; legacy responses omit result_kind. */
export function isProfileReplay(value: unknown): value is ProfileReplayPage {
  return typeof value === "object" && value !== null && "result_kind" in value && value.result_kind === "profile"
    && "items" in value && Array.isArray(value.items);
}

export interface ConfigurationSummary {
  id: string;
  name: string;
  strategy: Strategy;
}

export interface QueueFailure {
  experiment_id: string;
  persisted: boolean;
  reason: string;
  persistence_error: string | null;
}

export interface QueuePage {
  total: number;
  offset: number;
  limit: number;
  count: number;
  items: string[];
}

export interface QueueStatus {
  active_id: string | null;
  pending: QueuePage;
  held: QueuePage;
  last_failure: QueueFailure | null;
}

export interface StorageStatus {
  limit_bytes: number;
  /** Historical experiment/run bytes, not the aggregate quota consumption. */
  logical_used_bytes: number;
  logical_used_bytes_exact: string;
  /** Numeric compatibility field; use exact strings for all quota arithmetic. */
  profile_artifact_bytes: number;
  profile_artifact_bytes_exact: string;
  /** Zero until actual persisted datasets and their admission are implemented. */
  dataset_artifact_bytes_exact: string;
  /** Authoritative quota usage: legacy experiment bytes plus both stored profile JSON copies. */
  admission_logical_bytes_exact: string;
  logical_margin_bytes: number;
  free_disk_bytes: number;
  disk_margin_bytes: number;
  database_bytes: number;
  wal_bytes: number;
  shm_bytes: number;
  temp_bytes: number;
  sqlite_bytes: number;
  warning: boolean;
}

export interface SettingsView {
  storage: StorageStatus;
  quota: {
    effective_bytes: string;
    persisted_bytes: string | null;
    source: "default" | "persisted" | "environment";
    writable: boolean;
  };
  sources: Pick<Sources, "history_id" | "history_sha256" | "rankings_id" | "rankings_sha256" | "code_version">;
  connection: { host: string; port: number; version: string };
}
