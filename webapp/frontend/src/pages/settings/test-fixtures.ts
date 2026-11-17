import type { HistoryResponse, HistorySnapshot, NumberListInfo, SettingsResponse } from "../../api/types";

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
    limit_bytes: 2147483648, logical_used_bytes: 524288000, profile_artifact_bytes: 10, dataset_artifact_bytes: 20,
    strategy_artifact_bytes: 30, logical_margin_bytes: 0, free_disk_bytes: 2000, disk_margin_bytes: 1500,
    database_bytes: 40, wal_bytes: 5, shm_bytes: 1, temp_bytes: 2, history_artifact_bytes: 50,
    run_artifact_bytes: 60, sqlite_bytes: 46, warning: false, logical_used_bytes_exact: "524288000",
    profile_artifact_bytes_exact: "10", dataset_artifact_bytes_exact: "20", history_artifact_bytes_exact: "50",
    run_artifact_bytes_exact: "60", admission_logical_bytes_exact: "524288000",
  },
  quota: { effective_bytes: "2147483648", persisted_bytes: "2147483648", source: "database", writable: true },
  sources: { history_id: "history", history_sha256: "d".repeat(64), rankings_id: "rankings", rankings_sha256: "c".repeat(64), code_version: "26e333b" },
  connection: { host: "127.0.0.1", port: 8765, version: "0.1.0" },
};

export const chanceList: NumberListInfo = {
  id: "chance_express", name: "Loteka Chance Express", positions: 5, draws: 1381,
  first_label: "2025-03-05 12:00", last_label: "2026-09-25 18:20", active: true, available: true,
  prizes: [80, 8, 4, 2, 1], default_prizes: [80, 8, 4, 2, 1],
};
export const leidsaList: NumberListInfo = {
  id: "leidsa_quiniela", name: "Quiniela Leidsa", positions: 3, draws: 4239,
  first_label: "2023-01-04 14:55", last_label: "2026-11-16 20:55", active: false, available: true,
  prizes: [60, 8, 4], default_prizes: [60, 8, 4],
};
export const listsFixture: NumberListInfo[] = [chanceList, leidsaList];
export const leidsaActiveLists: NumberListInfo[] = [{ ...chanceList, active: false }, { ...leidsaList, active: true }];
