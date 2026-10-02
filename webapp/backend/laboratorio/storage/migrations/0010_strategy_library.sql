CREATE TABLE strategies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    protected INTEGER NOT NULL CHECK (protected IN (0, 1)),
    preset_explanation TEXT NOT NULL,
    latest_revision INTEGER NOT NULL CHECK (latest_revision >= 1)
);
CREATE TABLE strategy_revisions (
    strategy_id TEXT NOT NULL REFERENCES strategies(id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    definition_version INTEGER NOT NULL CHECK (definition_version = 1),
    definition_sha256 TEXT NOT NULL CHECK (length(definition_sha256) = 64),
    definition_json TEXT NOT NULL CHECK (json_valid(definition_json)),
    created_at TEXT NOT NULL,
    PRIMARY KEY (strategy_id, revision)
);
CREATE TRIGGER strategy_protected_revision_insert BEFORE INSERT ON strategy_revisions
WHEN NEW.revision > 1 AND EXISTS (
    SELECT 1 FROM strategies WHERE id = NEW.strategy_id AND protected = 1
)
BEGIN SELECT RAISE(ABORT, 'protected strategy cannot be revised'); END;
CREATE TRIGGER strategy_revisions_no_replace BEFORE INSERT ON strategy_revisions
WHEN EXISTS (SELECT 1 FROM strategy_revisions
             WHERE strategy_id = NEW.strategy_id AND revision = NEW.revision)
BEGIN SELECT RAISE(ABORT, 'strategy revision is immutable'); END;
CREATE TRIGGER strategy_revisions_no_update BEFORE UPDATE ON strategy_revisions
BEGIN SELECT RAISE(ABORT, 'strategy revision is immutable'); END;
CREATE TRIGGER strategy_revisions_no_delete BEFORE DELETE ON strategy_revisions
BEGIN SELECT RAISE(ABORT, 'strategy revision is immutable'); END;
CREATE TRIGGER strategies_no_delete BEFORE DELETE ON strategies
BEGIN SELECT RAISE(ABORT, 'strategies are immutable'); END;
CREATE TRIGGER strategies_no_replace BEFORE INSERT ON strategies
WHEN EXISTS (SELECT 1 FROM strategies WHERE id = NEW.id)
BEGIN SELECT RAISE(ABORT, 'strategy identity is immutable'); END;
CREATE TRIGGER strategies_protected_update BEFORE UPDATE ON strategies
WHEN OLD.protected = 1 AND (
    NEW.name != OLD.name OR NEW.created_at != OLD.created_at
    OR NEW.preset_explanation != OLD.preset_explanation
    OR NEW.protected != OLD.protected OR NEW.latest_revision != OLD.latest_revision
)
BEGIN SELECT RAISE(ABORT, 'protected strategy is immutable'); END;
