-- Discriminators are additive: legacy request/result JSON remains byte-for-byte intact.
ALTER TABLE experiments ADD COLUMN request_kind TEXT NOT NULL DEFAULT 'legacy'
    CHECK (request_kind IN ('legacy', 'profile'));
ALTER TABLE runs ADD COLUMN result_kind TEXT NOT NULL DEFAULT 'legacy'
    CHECK (result_kind IN ('legacy', 'profile'));
