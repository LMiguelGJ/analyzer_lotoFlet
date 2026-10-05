-- Empty singleton: absence means the user has not edited the game rules.
-- prizes is a comma-separated list of positive integers, one per position.
CREATE TABLE settings_game (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    numbers INTEGER NOT NULL,
    positions INTEGER NOT NULL,
    prizes TEXT NOT NULL,
    allows_repeats INTEGER NOT NULL CHECK (allows_repeats IN (0, 1)),
    minimum_stake INTEGER NOT NULL
);
