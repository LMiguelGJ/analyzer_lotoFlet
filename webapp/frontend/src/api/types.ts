export interface ApiFieldError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export type RunOutcome = "goal" | "ruin" | "limit" | "incomplete";
export type DetailStatus = "complete" | "partial" | "sessions_truncated";

/** POST request shape: defaults are obtained from GET /runs/options. */
export interface CreateRunRequest {
  name?: string | null;
  rules?: { positions?: number; prizes?: number[]; minimum_stake?: number };
  strategy?: {
    kind?: "mix" | "parity";
    components?: { system: string; percent: number }[];
    coverage?: number;
  };
  conditions?: { capital?: number; goal?: number; max_draws?: number | null };
  window?: { start_date?: string | null; end_date?: string | null };
  history_sha256?: string | null;
}

/** Shape stored with a report; history provenance is not the request fingerprint field. */
export interface PersistedRunConfig {
  name: string;
  rules: { positions: number; prizes: number[]; minimum_stake: number };
  strategy: {
    kind: "mix" | "parity";
    components: { system: string; percent: number }[];
    coverage: number;
  };
  conditions: { capital: number; goal: number; max_draws: number | null };
  window: { start_date: string | null; end_date: string | null };
  history: { sha256: string; origin: "frozen" | "import" };
}

export interface RunOptions {
  systems: { id: string; label: string }[];
  defaults: CreateRunRequest;
  limits: {
    coverage: { min: number; max: number };
    positions: { min: number; max: number };
    name: number;
    detail: { sessions: number; bets: number; bytes: number };
  };
  history: HistorySnapshot;
}

export interface RunDetail {
  status: DetailStatus;
  total_sessions: number;
  stored_sessions: number;
  total_bets: number;
  stored_bets: number;
  limits: { sessions: number; bets: number; bytes: number };
}

export interface RunReport {
  id: string;
  name: string;
  created_at: string;
  schema_version: number;
  config: PersistedRunConfig;
  summary: {
    totals: {
      sessions: number;
      goal: number;
      ruin: number;
      limit: number;
      incomplete: number;
      bets: number;
      wagered: number;
      paid: number;
      net: number;
      return_pct: number | null;
      mean_net_closed: number | null;
    };
    window: { draws: number; ranked_draws: number; first_label: string; last_label: string };
    detail: RunDetail;
    engine_version: number;
    elapsed_seconds: number;
  };
}

export interface Page<T> {
  total: number;
  offset: number;
  limit: number;
  items: T[];
}

export interface RunSession {
  ordinal: number;
  outcome: RunOutcome;
  start_index: number;
  end_index: number;
  start_label: string;
  end_label: string;
  draws: number;
  bets: number;
  wagered: number;
  paid: number;
  final_balance: number;
  net: number;
  detail_available: boolean;
}

export interface SessionBet {
  index: number;
  label: string;
  numbers: number[];
  results: number[];
  wagered: number;
  paid: number;
  balance: number;
}

export interface SessionBetsPage {
  session: Omit<RunSession, "detail_available"> & { detail_available: boolean };
  total: number;
  offset: number;
  limit: number;
  detail_available: boolean;
  items: SessionBet[];
}

export interface HistorySnapshot {
  sha256: string;
  origin: "frozen" | "import";
  draws: number;
  ranked_draws: number;
  first_label: string;
  last_label: string;
  added_draws: number;
  created_at: string | null;
  active: boolean;
}

export interface HistoryResponse {
  active: HistorySnapshot;
  sources: HistorySnapshot[];
}

export interface HistoryImportResponse {
  created: boolean;
  added: number;
  active: HistorySnapshot;
}

export interface SettingsResponse {
  storage: {
    limit_bytes: number;
    logical_used_bytes: number;
    profile_artifact_bytes: number;
    dataset_artifact_bytes: number;
    strategy_artifact_bytes: number;
    logical_margin_bytes: number;
    free_disk_bytes: number;
    disk_margin_bytes: number;
    database_bytes: number;
    wal_bytes: number;
    shm_bytes: number;
    temp_bytes: number;
    history_artifact_bytes: number;
    run_artifact_bytes: number;
    sqlite_bytes: number;
    warning: boolean;
    logical_used_bytes_exact: string;
    profile_artifact_bytes_exact: string;
    dataset_artifact_bytes_exact: string;
    history_artifact_bytes_exact: string;
    run_artifact_bytes_exact: string;
    admission_logical_bytes_exact: string;
  };
  quota: { effective_bytes: string; persisted_bytes: string | null; source: string; writable: boolean };
  sources: { history_id: string; history_sha256: string; rankings_id: string; rankings_sha256: string; code_version: string };
  connection: { host: string; port: number; version: string };
}
