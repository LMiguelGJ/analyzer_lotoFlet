CREATE TABLE laboratory_definitions (
    id TEXT PRIMARY KEY NOT NULL CHECK (typeof(id) = 'text' AND length(id) = 36),
    name TEXT NOT NULL CHECK (typeof(name) = 'text' AND length(name) > 0),
    name_key TEXT NOT NULL UNIQUE CHECK (typeof(name_key) = 'text' AND length(name_key) > 0),
    definition_json TEXT NOT NULL CHECK (typeof(definition_json) = 'text'),
    definition_bytes INTEGER NOT NULL CHECK (typeof(definition_bytes) = 'integer' AND definition_bytes >= 0),
    created_at TEXT NOT NULL CHECK (typeof(created_at) = 'text' AND length(created_at) > 0)
);

CREATE TABLE storage_bootstrap_state (
    state_key TEXT PRIMARY KEY NOT NULL,
    state_value TEXT NOT NULL
);

ALTER TABLE reference_lab_runs
    ADD COLUMN owner_laboratory_id TEXT
    REFERENCES laboratory_definitions(id) ON DELETE CASCADE
    CHECK (owner_laboratory_id IS NULL OR owner_laboratory_id = lab_id);

CREATE INDEX reference_lab_runs_owner_created_id_idx
    ON reference_lab_runs(owner_laboratory_id, created_at DESC, id DESC);
