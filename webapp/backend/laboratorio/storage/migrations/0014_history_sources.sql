CREATE TABLE history_sources (
    sha256 TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    draws INTEGER NOT NULL CHECK(draws > 0),
    added_draws INTEGER NOT NULL CHECK(added_draws >= 0),
    first_label TEXT NOT NULL,
    last_label TEXT NOT NULL,
    raw_bytes BLOB NOT NULL
);

CREATE TABLE history_active (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    sha256 TEXT NOT NULL REFERENCES history_sources(sha256)
);
