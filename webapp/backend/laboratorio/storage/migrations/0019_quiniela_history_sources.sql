-- Immutable profile-bound v2 histories; legacy active history remains untouched.
CREATE TABLE quiniela_history_sources (
    id TEXT PRIMARY KEY NOT NULL CHECK(length(id) = 36),
    profile_id TEXT NOT NULL,
    profile_sha256 TEXT NOT NULL CHECK(length(profile_sha256) = 64 AND profile_sha256 NOT GLOB '*[^0-9a-f]*'),
    origin TEXT NOT NULL CHECK(origin IN ('included', 'imported')),
    name TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL CHECK(length(raw_sha256) = 64 AND raw_sha256 NOT GLOB '*[^0-9a-f]*'),
    canonical_sha256 TEXT NOT NULL CHECK(length(canonical_sha256) = 64 AND canonical_sha256 NOT GLOB '*[^0-9a-f]*'),
    preview_sha256 TEXT NOT NULL CHECK(length(preview_sha256) = 64 AND preview_sha256 NOT GLOB '*[^0-9a-f]*'),
    raw_bytes BLOB NOT NULL,
    canonical_json TEXT NOT NULL,
    source_bytes INTEGER NOT NULL CHECK(source_bytes = length(raw_bytes) + length(CAST(canonical_json AS BLOB))),
    timezone TEXT NOT NULL,
    timezone_confirmed INTEGER NOT NULL CHECK(timezone_confirmed IN (0, 1)),
    draws INTEGER NOT NULL CHECK(draws >= 0),
    duplicates INTEGER NOT NULL CHECK(duplicates >= 0),
    first_timestamp TEXT,
    last_timestamp TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(profile_id, profile_sha256)
        REFERENCES quiniela_game_profiles(id, profile_sha256),
    UNIQUE(preview_sha256),
    UNIQUE(id, profile_sha256, origin, raw_sha256, canonical_sha256)
);
CREATE INDEX quiniela_history_sources_created
    ON quiniela_history_sources(created_at DESC, id DESC);
CREATE INDEX quiniela_history_sources_profile
    ON quiniela_history_sources(profile_id, created_at DESC, id DESC);
