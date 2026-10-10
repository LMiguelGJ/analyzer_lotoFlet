import type { HistoryResponse, HistorySnapshot, SettingsResponse } from "../../api/types";

export const frozenHistory: HistorySnapshot = {
  sha256: "a".repeat(64), origin: "frozen", draws: 120, ranked_draws: 100,
  first_label: "2025-03-05", last_label: "2026-09-25", added_draws: 0, created_at: null, active: true,
};
export const importedHistory: HistorySnapshot = {
  sha256: "b".repeat(64), origin: "import", draws: 130, ranked_draws: 105,
  first_label: "2025-01-01", last_label: "2026-10-01", added_draws: 10, created_at: "2026-10-02T12:00:00Z", active: false,
};
export const historyFixture: HistoryResponse = { active: frozenHistory, sources: [frozenHistory, importedHistory] };
export const settingsFixture: SettingsResponse = {
  storage: {
    limit_bytes: 1000, logical_used_bytes: 1, profile_artifact_bytes: 10, dataset_artifact_bytes: 20,
    strategy_artifact_bytes: 30, logical_margin_bytes: 0, free_disk_bytes: 2000, disk_margin_bytes: 1500,
    database_bytes: 40, wal_bytes: 5, shm_bytes: 1, temp_bytes: 2, history_artifact_bytes: 50,
    run_artifact_bytes: 60, sqlite_bytes: 46, warning: true, logical_used_bytes_exact: "1",
    profile_artifact_bytes_exact: "10", dataset_artifact_bytes_exact: "20", history_artifact_bytes_exact: "50",
    run_artifact_bytes_exact: "60", admission_logical_bytes_exact: "9007199254740993",
  },
  quota: { effective_bytes: "1000", persisted_bytes: "1000", source: "database", writable: true },
  sources: { history_id: "history", history_sha256: "a".repeat(64), rankings_id: "rankings", rankings_sha256: "c".repeat(64), code_version: "26e333b" },
  connection: { host: "127.0.0.1", port: 8765, version: "0.1.0" },
};
