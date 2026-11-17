"""Editable prize table per number list (S4) without touching Loteka's defaults (S6)."""

import sqlite3
from contextlib import closing
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.settings import Settings
from laboratorio.storage.database import SCHEMA_VERSION, initialize_database

BASE_URL = "http://localhost:8765"
ORIGIN = {"Origin": BASE_URL, "Content-Type": "application/json"}
CHANCE = "chance_express"
LEIDSA = "leidsa_quiniela"
MSG_UNKNOWN = "Esa lista no existe."
MSG_VALUE = "Cada premio debe ser un número entero mayor que 0 y como máximo 10000."
MSG_LEIDSA_LEN = "La lista «Quiniela Leidsa» necesita 3 premios, uno por posición."
MSG_CHANCE_LEN = "La lista «Loteka Chance Express» necesita 5 premios, uno por posición."


def make_app(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    return create_app(settings, catalog_loader=lambda _settings: lab_data)


def client_for(tmp_path, lab_data):
    return TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL)


def by_id(response):
    assert response.status_code == 200, response.text
    return {item["id"]: item for item in response.json()}


def saved_rows(tmp_path):
    with closing(sqlite3.connect(tmp_path / "laboratorio.db")) as db:
        return db.execute("SELECT list_id, prizes_json FROM list_prizes ORDER BY 1").fetchall()


def put_prizes(client, list_id, prizes):
    return client.put(f"/api/v1/lists/{list_id}/prizes", json={"prizes": prizes}, headers=ORIGIN)


def activate(client, list_id):
    response = client.put("/api/v1/lists/active", json={"id": list_id}, headers=ORIGIN)
    assert response.status_code == 200


# ------------------------------------------------------------------ migration


def test_schema_is_22_with_empty_list_prizes_table(tmp_path):
    assert SCHEMA_VERSION == 22
    path = tmp_path / "lab.db"
    initialize_database(path)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 22
        assert db.execute("SELECT count(*) FROM list_prizes").fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO list_prizes (list_id, prizes_json) VALUES ('a', NULL)")


def test_v21_database_upgrades_keeping_active_list(tmp_path):
    from laboratorio.storage import database

    path = tmp_path / "v21.db"
    with closing(sqlite3.connect(path)) as db:
        database._run_migrations(db, 0, list(range(1, 22)))
        db.execute("UPDATE active_number_list SET list_id = 'leidsa_quiniela'")
        db.commit()
    initialize_database(path)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT list_id FROM active_number_list").fetchall() == [(LEIDSA,)]
        assert db.execute("SELECT count(*) FROM list_prizes").fetchone()[0] == 0


# ---------------------------------------------------------------------- GET


def test_get_lists_shows_default_prizes_and_keeps_existing_fields(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        listed = by_id(client.get("/api/v1/lists"))
    assert listed[CHANCE]["prizes"] == [80, 8, 4, 2, 1]
    assert listed[CHANCE]["default_prizes"] == [80, 8, 4, 2, 1]
    assert listed[LEIDSA]["prizes"] == [60, 8, 4]
    assert listed[LEIDSA]["default_prizes"] == [60, 8, 4]
    for item in listed.values():
        assert {"id", "name", "positions", "draws", "first_label", "last_label"} <= item.keys()
        assert {"active", "available"} <= item.keys()


# ---------------------------------------------------------------------- PUT


def test_put_saves_returns_full_list_and_persists_across_apps(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        response = put_prizes(client, LEIDSA, [70, 9, 5])
        listed = by_id(response)
        assert listed[LEIDSA]["prizes"] == [70, 9, 5]
        assert listed[LEIDSA]["default_prizes"] == [60, 8, 4]
        assert listed[CHANCE]["prizes"] == [80, 8, 4, 2, 1]
        assert set(listed) == {CHANCE, LEIDSA}
        assert by_id(client.get("/api/v1/lists"))[LEIDSA]["prizes"] == [70, 9, 5]
    assert len(saved_rows(tmp_path)) == 1

    with client_for(tmp_path, lab_data) as client:
        assert client.get("/api/v1/settings").status_code == 200
        listed = by_id(client.get("/api/v1/lists"))
        assert listed[LEIDSA]["prizes"] == [70, 9, 5]
        assert listed[LEIDSA]["default_prizes"] == [60, 8, 4]


def test_put_accepts_whole_prizes_at_the_limits(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        listed = by_id(put_prizes(client, LEIDSA, [10000, 1, 12]))
        assert listed[LEIDSA]["prizes"] == [10000, 1, 12]
        listed = by_id(put_prizes(client, LEIDSA, [60.0, 8, 4]))
        assert listed[LEIDSA]["prizes"] == [60, 8, 4]


def test_put_replaces_the_saved_table(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        put_prizes(client, LEIDSA, [70, 9, 5])
        listed = by_id(put_prizes(client, LEIDSA, [65, 7, 3]))
        assert listed[LEIDSA]["prizes"] == [65, 7, 3]
    assert len(saved_rows(tmp_path)) == 1


def test_options_defaults_follow_saved_prizes_of_the_active_list(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        activate(client, LEIDSA)
        assert client.get("/api/v1/laboratories/options").json()["prizes"] == [60, 8, 4]
        assert client.get("/api/v1/runs/options").json()["defaults"]["rules"]["prizes"] == [
            60,
            8,
            4,
        ]
        put_prizes(client, LEIDSA, [70, 9, 5])
        assert client.get("/api/v1/laboratories/options").json()["prizes"] == [70, 9, 5]
        runs = client.get("/api/v1/runs/options").json()
        assert runs["defaults"]["rules"] == {
            "positions": 3,
            "prizes": [70, 9, 5],
            "minimum_stake": 1,
        }
        # Prizes saved for the other (inactive) list do not leak into this one.
        put_prizes(client, CHANCE, [90, 9, 5, 3, 2])
        assert client.get("/api/v1/laboratories/options").json()["prizes"] == [70, 9, 5]
        activate(client, CHANCE)
        assert client.get("/api/v1/laboratories/options").json()["prizes"] == [90, 9, 5, 3, 2]
        assert client.get("/api/v1/runs/options").json()["defaults"]["rules"]["prizes"] == [
            90,
            9,
            5,
        ]


def test_existing_labs_and_runs_keep_their_prizes(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        before = client.get("/api/v1/laboratories").json()
        put_prizes(client, CHANCE, [90, 9, 5, 3, 2])
        assert client.get("/api/v1/laboratories").json() == before


@pytest.mark.parametrize(
    ("list_id", "prizes", "message"),
    [
        ("otra", [1, 2, 3], MSG_UNKNOWN),
        (LEIDSA, [60, 8], MSG_LEIDSA_LEN),
        (LEIDSA, [60, 8, 4, 2], MSG_LEIDSA_LEN),
        (LEIDSA, [], MSG_LEIDSA_LEN),
        (CHANCE, [60, 8, 4], MSG_CHANCE_LEN),
        (LEIDSA, [0, 8, 4], MSG_VALUE),
        (LEIDSA, [-1, 8, 4], MSG_VALUE),
        (LEIDSA, [60, 8, 10000.01], MSG_VALUE),
        (LEIDSA, [60, 8, 10001], MSG_VALUE),
        (LEIDSA, [60, 8, 4.123], MSG_VALUE),
        (LEIDSA, [60, 8, 5.5], MSG_VALUE),
        (LEIDSA, [60, 8, 0.001], MSG_VALUE),
        (LEIDSA, [60, 8, "4"], MSG_VALUE),
        (LEIDSA, [60, 8, None], MSG_VALUE),
        (LEIDSA, [60, 8, True], MSG_VALUE),
        (LEIDSA, "60,8,4", MSG_LEIDSA_LEN),
    ],
)
def test_rejections_use_exact_message_and_save_nothing(
    tmp_path, lab_data, list_id, prizes, message
):
    with client_for(tmp_path, lab_data) as client:
        put_prizes(client, LEIDSA, [61, 9, 5])
        before = saved_rows(tmp_path)
        response = put_prizes(client, list_id, prizes)
        assert response.status_code == 422, response.text
        assert response.json() == {"detail": message}
        assert saved_rows(tmp_path) == before
        assert by_id(client.get("/api/v1/lists"))[LEIDSA]["prizes"] == [61, 9, 5]


def test_rejections_on_a_fresh_database_leave_the_table_empty(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        assert put_prizes(client, LEIDSA, [0, 1, 1]).status_code == 422
        assert put_prizes(client, "otra", [1, 1, 1]).status_code == 422
        assert saved_rows(tmp_path) == []


def test_malformed_body_is_rejected_without_saving(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        for body in ({}, {"prizes": [60, 8, 4], "extra": 1}):
            response = client.put(f"/api/v1/lists/{LEIDSA}/prizes", json=body, headers=ORIGIN)
            assert response.status_code == 422
        assert saved_rows(tmp_path) == []


def test_null_restores_the_default_and_deletes_the_row(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        put_prizes(client, LEIDSA, [70, 9, 5])
        put_prizes(client, CHANCE, [90, 9, 5, 3, 2])
        listed = by_id(put_prizes(client, LEIDSA, None))
        assert listed[LEIDSA]["prizes"] == [60, 8, 4]
        assert listed[CHANCE]["prizes"] == [90, 9, 5, 3, 2]
        assert [row[0] for row in saved_rows(tmp_path)] == [CHANCE]
        # Restoring when nothing is saved is a harmless no-op.
        assert by_id(put_prizes(client, LEIDSA, None))[LEIDSA]["prizes"] == [60, 8, 4]
        assert put_prizes(client, "otra", None).status_code == 422


def test_chance_responses_are_unchanged_when_nothing_is_saved(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        lab_options = client.get("/api/v1/laboratories/options")
        run_options = client.get("/api/v1/runs/options")
        assert lab_options.json()["prizes"] == [80, 8, 4, 2, 1]
        assert run_options.json()["defaults"]["rules"] == {
            "positions": 3,
            "prizes": [60, 10, 5],
            "minimum_stake": 1,
        }
        baseline = (lab_options.content, run_options.content)
        # Saving then restoring the default returns the very same bytes.
        put_prizes(client, CHANCE, [90, 9, 5, 3, 2])
        put_prizes(client, CHANCE, None)
        assert client.get("/api/v1/laboratories/options").content == baseline[0]
        assert client.get("/api/v1/runs/options").content == baseline[1]


def test_non_finite_number_in_raw_json_is_rejected_without_saving(tmp_path, lab_data):
    with client_for(tmp_path, lab_data) as client:
        for raw in ('{"prizes": [60, 8, 1e999]}', '{"prizes": [60, 8, NaN]}'):
            response = client.put(f"/api/v1/lists/{LEIDSA}/prizes", content=raw, headers=ORIGIN)
            assert response.status_code == 422, response.text
            assert response.json() == {"detail": MSG_VALUE}
        assert saved_rows(tmp_path) == []
