-- One immutable artifact per canonical identity. The original upload and canonical
-- UTF-8 representation are each stored once; no mutable source pointer exists.
CREATE TABLE datasets (
    dataset_sha256 TEXT PRIMARY KEY CHECK (length(dataset_sha256) = 64),
    source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64),
    canonical_json TEXT NOT NULL CHECK (json_valid(canonical_json)),
    raw_bytes BLOB NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TRIGGER datasets_no_replace BEFORE INSERT ON datasets
WHEN EXISTS (SELECT 1 FROM datasets WHERE dataset_sha256 = NEW.dataset_sha256)
BEGIN SELECT RAISE(ABORT, 'dataset is immutable'); END;
CREATE TRIGGER datasets_no_update BEFORE UPDATE ON datasets
BEGIN SELECT RAISE(ABORT, 'dataset is immutable'); END;
CREATE TRIGGER datasets_no_delete BEFORE DELETE ON datasets
BEGIN SELECT RAISE(ABORT, 'dataset is immutable'); END;
