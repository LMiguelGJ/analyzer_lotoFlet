CREATE TABLE reference_lab_runs (
    id TEXT PRIMARY KEY NOT NULL CHECK (typeof(id) = 'text' AND length(id) = 36),
    lab_id TEXT NOT NULL CHECK (typeof(lab_id) = 'text' AND length(lab_id) > 0),
    contract_version INTEGER NOT NULL CHECK (typeof(contract_version) = 'integer' AND contract_version = 1),
    created_at TEXT NOT NULL CHECK (typeof(created_at) = 'text' AND length(created_at) > 0),
    metadata_json TEXT NOT NULL CHECK (typeof(metadata_json) = 'text'),
    result_json TEXT NOT NULL CHECK (typeof(result_json) = 'text')
);

CREATE INDEX reference_lab_runs_created_id_idx
    ON reference_lab_runs(created_at DESC, id DESC);
CREATE INDEX reference_lab_runs_lab_created_id_idx
    ON reference_lab_runs(lab_id, created_at DESC, id DESC);

CREATE TABLE reference_lab_sessions (
    run_id TEXT NOT NULL REFERENCES reference_lab_runs(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (typeof(ordinal) = 'integer' AND ordinal >= 0),
    session_json TEXT NOT NULL CHECK (typeof(session_json) = 'text'),
    PRIMARY KEY (run_id, ordinal)
);
