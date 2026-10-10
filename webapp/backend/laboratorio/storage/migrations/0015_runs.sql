CREATE TABLE saved_runs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX saved_runs_created_at ON saved_runs(created_at, id);
CREATE TABLE saved_run_sessions (
    run_id TEXT NOT NULL REFERENCES saved_runs(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    outcome TEXT NOT NULL CHECK(outcome IN ('goal','ruin','limit','incomplete')),
    start_index INTEGER NOT NULL,
    end_index INTEGER NOT NULL,
    start_label TEXT NOT NULL,
    end_label TEXT NOT NULL,
    draws INTEGER NOT NULL,
    bets INTEGER NOT NULL,
    wagered INTEGER NOT NULL,
    paid INTEGER NOT NULL,
    final_balance INTEGER NOT NULL,
    bets_json TEXT,
    PRIMARY KEY (run_id, ordinal)
) WITHOUT ROWID;
