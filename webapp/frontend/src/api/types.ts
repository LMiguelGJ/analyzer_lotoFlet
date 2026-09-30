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

export interface Game {
  name: string;
  numbers: number;
  positions: number;
  prizes: number[];
  allows_repeats: boolean;
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
export type RunResult = Omit<SessionResult, "bets"> & { delta: number };

export interface RunSummary {
  ordinal: number;
  configuration_id: string | null;
  status: RunStatus;
  result: RunResult | null;
  bets_count: number;
}

export interface ExperimentSummary {
  id: string;
  /** UTC ISO timestamp; null for records created before migration 0002. Optional only for older captured frontend fixtures. */
  created_at?: string | null;
  status: ExperimentStatus;
  request: ExperimentRequest;
  sources: {
    history_id: string;
    history_sha256: string;
    rankings_id: string;
    rankings_sha256: string;
    code_version: string;
  };
  runs: RunSummary[];
}

export interface CompareResult {
  id: string;
  status: ExperimentStatus;
  completed: number;
  requested: number;
  complete: boolean;
  runs: RunSummary[];
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
  /** Legacy numeric compatibility only; exact display and arithmetic use logical_used_bytes_exact. */
  logical_used_bytes: number;
  logical_used_bytes_exact: string;
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
