-- Empty singleton: absence means the user has not set a preference.
CREATE TABLE settings_quota (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    quota_bytes INTEGER NOT NULL CHECK (quota_bytes BETWEEN 1 AND 9223372036854775807)
);
