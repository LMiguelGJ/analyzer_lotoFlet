-- Schema versions describe the persisted wire contract. Legacy JSON has no inner
-- version field: 1 names its exact existing request/result shape, not a rewrite.
-- Existing profile requests are v1; completed profile results are also v1.
ALTER TABLE experiments ADD COLUMN request_schema_version INTEGER NOT NULL DEFAULT 1
    CHECK ((request_kind = 'legacy' AND request_schema_version = 1)
        OR (request_kind = 'profile' AND request_schema_version IN (1, 2)));
ALTER TABLE runs ADD COLUMN result_schema_version INTEGER
    CHECK ((result_json IS NULL AND result_schema_version IS NULL)
        OR (result_json IS NOT NULL AND result_schema_version IS NULL)
        OR (result_json IS NOT NULL AND result_kind = 'legacy' AND result_schema_version = 1)
        OR (result_json IS NOT NULL AND result_kind = 'profile'
            AND result_schema_version IN (1, 2)));
UPDATE runs SET result_schema_version = 1 WHERE result_json IS NOT NULL;
-- A NULL version on a completed row is only tolerated while upgrading old bytes.
-- Enforce the post-upgrade invariant for every new insert/update.
CREATE TRIGGER runs_result_version_insert BEFORE INSERT ON runs
WHEN (NEW.result_json IS NOT NULL AND NEW.result_schema_version IS NULL)
BEGIN SELECT RAISE(ABORT, 'missing result schema version'); END;
CREATE TRIGGER runs_result_version_update BEFORE UPDATE ON runs
WHEN (NEW.result_json IS NOT NULL AND NEW.result_schema_version IS NULL)
BEGIN SELECT RAISE(ABORT, 'missing result schema version'); END;
