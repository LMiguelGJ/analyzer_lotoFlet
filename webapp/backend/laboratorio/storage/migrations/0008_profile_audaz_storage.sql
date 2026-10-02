-- Rebuild only the tables whose version checks must admit schema 3. Keep the
-- experiment_profiles table and all its triggers untouched; retain every wire byte.
CREATE TABLE experiments_v8 (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN (
        'pending', 'held', 'running', 'completed', 'cancelled', 'interrupted', 'failed'
    )),
    request_json TEXT NOT NULL,
    history_id TEXT NOT NULL,
    history_sha256 TEXT NOT NULL,
    rankings_id TEXT NOT NULL,
    rankings_sha256 TEXT NOT NULL,
    code_version TEXT NOT NULL,
    created_at TEXT,
    request_kind TEXT NOT NULL DEFAULT 'legacy' CHECK (request_kind IN ('legacy', 'profile')),
    request_schema_version INTEGER NOT NULL DEFAULT 1
        CHECK ((request_kind = 'legacy' AND request_schema_version = 1)
            OR (request_kind = 'profile' AND request_schema_version IN (1, 2, 3)))
);
INSERT INTO experiments_v8 SELECT id, status, request_json, history_id, history_sha256,
    rankings_id, rankings_sha256, code_version, created_at, request_kind, request_schema_version
    FROM experiments;

CREATE TABLE runs_v8 (
    experiment_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    configuration_id TEXT REFERENCES configurations(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN (
        'pending', 'held', 'running', 'completed', 'cancelled', 'not_run', 'interrupted', 'failed'
    )),
    result_json TEXT,
    result_kind TEXT NOT NULL DEFAULT 'legacy' CHECK (result_kind IN ('legacy', 'profile')),
    result_schema_version INTEGER CHECK (
        (result_json IS NULL AND result_schema_version IS NULL)
        OR (result_json IS NOT NULL AND result_schema_version IS NULL)
        OR (result_json IS NOT NULL AND result_kind = 'legacy' AND result_schema_version = 1)
        OR (result_json IS NOT NULL AND result_kind = 'profile' AND result_schema_version IN (1, 2, 3))
    ),
    PRIMARY KEY (experiment_id, ordinal),
    CHECK ((status = 'completed') = (result_json IS NOT NULL))
);
INSERT INTO runs_v8 SELECT experiment_id, ordinal, configuration_id, status, result_json,
    result_kind, result_schema_version FROM runs;

-- Temporarily remove the child-table trigger whose body resolves the parent table;
-- SQLite otherwise rejects dropping/recreating that parent in the middle of the migration.
DROP TRIGGER experiment_profiles_no_delete;
DROP TABLE runs;
DROP TABLE experiments;
ALTER TABLE experiments_v8 RENAME TO experiments;
ALTER TABLE runs_v8 RENAME TO runs;
CREATE INDEX idx_experiments_created_at ON experiments (created_at, id);

CREATE TRIGGER runs_result_version_insert BEFORE INSERT ON runs
WHEN (NEW.result_json IS NOT NULL AND NEW.result_schema_version IS NULL)
BEGIN SELECT RAISE(ABORT, 'missing result schema version'); END;
CREATE TRIGGER runs_result_version_update BEFORE UPDATE ON runs
WHEN (NEW.result_json IS NOT NULL AND NEW.result_schema_version IS NULL)
BEGIN SELECT RAISE(ABORT, 'missing result schema version'); END;
CREATE TRIGGER experiment_profiles_no_delete BEFORE DELETE ON experiment_profiles
WHEN EXISTS (SELECT 1 FROM experiments WHERE id = OLD.experiment_id)
BEGIN SELECT RAISE(ABORT, 'experiment profile snapshots are immutable'); END;
