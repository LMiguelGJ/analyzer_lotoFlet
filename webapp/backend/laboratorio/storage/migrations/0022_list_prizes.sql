-- Prize table the user saved for a number list (see domain/number_lists.py).
-- No row means the catalog default applies. Add-only: existing data is untouched.
CREATE TABLE list_prizes (
    list_id TEXT PRIMARY KEY CHECK (typeof(list_id) = 'text' AND length(list_id) BETWEEN 1 AND 64),
    prizes_json TEXT NOT NULL CHECK (typeof(prizes_json) = 'text')
);
