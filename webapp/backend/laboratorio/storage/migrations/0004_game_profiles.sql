-- Profile documents are inert: only the frozen legacy request can execute today.
CREATE TABLE game_profiles (
    profile_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    profile_json TEXT NOT NULL CHECK (json_valid(profile_json)),
    PRIMARY KEY (profile_id, revision)
);

CREATE TRIGGER game_profiles_no_replace BEFORE INSERT ON game_profiles
WHEN EXISTS (SELECT 1 FROM game_profiles
             WHERE profile_id = NEW.profile_id AND revision = NEW.revision)
BEGIN SELECT RAISE(ABORT, 'game profile versions are append-only'); END;
CREATE TRIGGER game_profiles_no_update BEFORE UPDATE ON game_profiles
BEGIN SELECT RAISE(ABORT, 'game profile versions are immutable'); END;
CREATE TRIGGER game_profiles_no_delete BEFORE DELETE ON game_profiles
BEGIN SELECT RAISE(ABORT, 'game profile versions are append-only'); END;

CREATE TABLE experiment_profiles (
    experiment_id TEXT PRIMARY KEY REFERENCES experiments(id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    profile_json TEXT NOT NULL CHECK (json_valid(profile_json)),
    FOREIGN KEY (profile_id, revision) REFERENCES game_profiles(profile_id, revision)
);

CREATE TRIGGER experiment_profiles_no_replace BEFORE INSERT ON experiment_profiles
WHEN EXISTS (SELECT 1 FROM experiment_profiles WHERE experiment_id = NEW.experiment_id)
BEGIN SELECT RAISE(ABORT, 'experiment profile snapshots are immutable'); END;
CREATE TRIGGER experiment_profiles_no_update BEFORE UPDATE ON experiment_profiles
BEGIN SELECT RAISE(ABORT, 'experiment profile snapshots are immutable'); END;
CREATE TRIGGER experiment_profiles_no_delete BEFORE DELETE ON experiment_profiles
WHEN EXISTS (SELECT 1 FROM experiments WHERE id = OLD.experiment_id)
BEGIN SELECT RAISE(ABORT, 'experiment profile snapshots are immutable'); END;
CREATE TRIGGER experiment_profiles_check_insert BEFORE INSERT ON experiment_profiles
WHEN NEW.profile_json != (SELECT profile_json FROM game_profiles
                         WHERE profile_id = NEW.profile_id AND revision = NEW.revision)
BEGIN SELECT RAISE(ABORT, 'experiment profile differs from its version'); END;
