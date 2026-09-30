CREATE TABLE configurations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    strategy_json TEXT NOT NULL
);

CREATE TABLE experiments (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN (
        'pending', 'held', 'running', 'completed', 'cancelled', 'interrupted', 'failed'
    )),
    request_json TEXT NOT NULL,
    history_id TEXT NOT NULL,
    history_sha256 TEXT NOT NULL,
    rankings_id TEXT NOT NULL,
    rankings_sha256 TEXT NOT NULL,
    code_version TEXT NOT NULL
);

CREATE TABLE runs (
    experiment_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    configuration_id TEXT REFERENCES configurations(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN (
        'pending', 'running', 'completed', 'cancelled', 'not_run', 'interrupted', 'failed'
    )),
    result_json TEXT,
    PRIMARY KEY (experiment_id, ordinal),
    CHECK ((status = 'completed') = (result_json IS NOT NULL))
);
