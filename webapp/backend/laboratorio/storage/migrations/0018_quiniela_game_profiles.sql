-- Add immutable v2 quiniela profiles without changing any v1 profile or result.
CREATE TABLE quiniela_game_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_key TEXT NOT NULL UNIQUE,
    profile_json TEXT NOT NULL,
    profile_bytes INTEGER NOT NULL CHECK(profile_bytes > 0),
    profile_sha256 TEXT NOT NULL CHECK(
        length(profile_sha256) = 64 AND profile_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    created_at TEXT NOT NULL,
    UNIQUE(id, profile_sha256)
);
CREATE INDEX quiniela_game_profiles_created ON quiniela_game_profiles(created_at DESC, id DESC);
