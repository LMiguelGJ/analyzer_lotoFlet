-- Extend request/result storage without changing any serialized v1-v4 row.
CREATE TABLE experiments_v11 (
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
            OR (request_kind = 'profile' AND request_schema_version IN (1, 2, 3, 4, 5)))
);
INSERT INTO experiments_v11 SELECT * FROM experiments;

CREATE TABLE runs_v11 (
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
        OR (result_json IS NOT NULL AND result_kind = 'profile' AND result_schema_version IN (1, 2, 3, 4, 5))
    ),
    PRIMARY KEY (experiment_id, ordinal),
    CHECK ((status = 'completed') = (result_json IS NOT NULL))
);
INSERT INTO runs_v11 SELECT * FROM runs;

DROP TRIGGER experiment_profiles_no_delete;
DROP TABLE runs;
DROP TABLE experiments;
ALTER TABLE experiments_v11 RENAME TO experiments;
ALTER TABLE runs_v11 RENAME TO runs;
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

CREATE TABLE execution_policy (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    max_strategies_per_batch INTEGER NOT NULL CHECK (max_strategies_per_batch BETWEEN 1 AND 3),
    worker_count INTEGER NOT NULL CHECK (worker_count = 1),
    max_pending_runs INTEGER NOT NULL CHECK (max_pending_runs BETWEEN 1 AND 100),
    max_bet_draws INTEGER NOT NULL CHECK (max_bet_draws BETWEEN 1 AND 10000),
    max_elapsed_draws INTEGER NOT NULL CHECK (max_elapsed_draws BETWEEN 1 AND 10000),
    run_timeout_seconds INTEGER NOT NULL CHECK (run_timeout_seconds BETWEEN 1 AND 3600)
);
INSERT INTO execution_policy VALUES (1, 1, 3, 1, 10, 1000, 10000, 120);

CREATE TABLE profile_batch_admissions (
    experiment_id TEXT PRIMARY KEY REFERENCES experiments(id) ON DELETE CASCADE,
    client_request_id TEXT NOT NULL UNIQUE CHECK (length(client_request_id) BETWEEN 1 AND 128),
    request_sha256 TEXT NOT NULL CHECK (length(request_sha256) = 64),
    strategy_refs_json TEXT NOT NULL CHECK (json_valid(strategy_refs_json)),
    requested_constraints_json TEXT NOT NULL CHECK (json_valid(requested_constraints_json)),
    effective_constraints_json TEXT NOT NULL CHECK (json_valid(effective_constraints_json)),
    policy_revision INTEGER NOT NULL CHECK (policy_revision >= 1),
    policy_json TEXT NOT NULL CHECK (json_valid(policy_json)),
    source_identity_json TEXT NOT NULL CHECK (json_valid(source_identity_json))
);
CREATE TRIGGER profile_batch_admissions_no_update BEFORE UPDATE ON profile_batch_admissions
BEGIN SELECT RAISE(ABORT, 'profile batch admission snapshot is immutable'); END;
CREATE TRIGGER profile_batch_request_no_update BEFORE UPDATE ON experiments
WHEN OLD.request_kind = 'profile' AND OLD.request_schema_version = 5 AND (
    NEW.request_json != OLD.request_json OR NEW.request_kind != OLD.request_kind
    OR NEW.request_schema_version != OLD.request_schema_version
    OR NEW.history_id != OLD.history_id OR NEW.history_sha256 != OLD.history_sha256
    OR NEW.rankings_id != OLD.rankings_id OR NEW.rankings_sha256 != OLD.rankings_sha256
    OR NEW.code_version != OLD.code_version
)
BEGIN SELECT RAISE(ABORT, 'profile batch request snapshot is immutable'); END;
