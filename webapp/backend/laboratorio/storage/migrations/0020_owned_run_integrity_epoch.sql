-- Operational invalidation marker for cached owned-run integrity certificates.
CREATE TABLE owned_run_integrity_epoch (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    epoch INTEGER NOT NULL CHECK (typeof(epoch) = 'integer' AND epoch >= 0)
);

INSERT INTO owned_run_integrity_epoch (singleton, epoch) VALUES (1, 0);

CREATE TRIGGER owned_run_integrity_epoch_runs_insert
AFTER INSERT ON reference_lab_runs
BEGIN
    UPDATE owned_run_integrity_epoch SET epoch = epoch + 1 WHERE singleton = 1;
END;

CREATE TRIGGER owned_run_integrity_epoch_runs_update
AFTER UPDATE ON reference_lab_runs
BEGIN
    UPDATE owned_run_integrity_epoch SET epoch = epoch + 1 WHERE singleton = 1;
END;

CREATE TRIGGER owned_run_integrity_epoch_runs_delete
AFTER DELETE ON reference_lab_runs
BEGIN
    UPDATE owned_run_integrity_epoch SET epoch = epoch + 1 WHERE singleton = 1;
END;

CREATE TRIGGER owned_run_integrity_epoch_sessions_insert
AFTER INSERT ON reference_lab_sessions
BEGIN
    UPDATE owned_run_integrity_epoch SET epoch = epoch + 1 WHERE singleton = 1;
END;

CREATE TRIGGER owned_run_integrity_epoch_sessions_update
AFTER UPDATE ON reference_lab_sessions
BEGIN
    UPDATE owned_run_integrity_epoch SET epoch = epoch + 1 WHERE singleton = 1;
END;

CREATE TRIGGER owned_run_integrity_epoch_sessions_delete
AFTER DELETE ON reference_lab_sessions
BEGIN
    UPDATE owned_run_integrity_epoch SET epoch = epoch + 1 WHERE singleton = 1;
END;
