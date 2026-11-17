-- Singleton: which number list (see domain/number_lists.py) the app works with.
CREATE TABLE active_number_list (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    list_id TEXT NOT NULL CHECK (typeof(list_id) = 'text' AND length(list_id) BETWEEN 1 AND 64)
);

INSERT INTO active_number_list (id, list_id) VALUES (1, 'chance_express');
