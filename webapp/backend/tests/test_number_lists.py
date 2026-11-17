"""Selectable number lists: catalog, persisted active list, N-position parsing (S1, S6)."""

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.number_lists import CATALOG, DEFAULT_LIST_ID, get_list
from laboratorio.engine.adapter import DataError, load_history, parse_history
from laboratorio.settings import HISTORY_SHA256, REPO_ROOT, Settings
from laboratorio.storage.database import SCHEMA_VERSION, initialize_database
from laboratorio.storage.repository import Repository

BASE_URL = "http://localhost:8765"
ORIGIN = {"Origin": BASE_URL, "Content-Type": "application/json"}
LEIDSA_FILE = REPO_ROOT / "datos" / "leidsa_quiniela_history.json"

MSG_UNKNOWN = "Esa lista no existe."
MSG_MISSING = (
    "La lista «Quiniela Leidsa» no está disponible en este equipo: falta su archivo de historial."
)
MSG_BLOCKED = (
    "La lista activa es «Quiniela Leidsa» y esta función todavía solo funciona con "
    "«Loteka Chance Express». Cámbiala en Ajustes."
)


def make_app(tmp_path, lab_data, **overrides):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765, **overrides)
    return create_app(settings, catalog_loader=lambda _settings: lab_data)


def active_in_db(tmp_path):
    with closing(sqlite3.connect(tmp_path / "laboratorio.db")) as db:
        return db.execute("SELECT list_id FROM active_number_list WHERE id = 1").fetchall()


# ----------------------------------------------------------------------- catalog


def test_catalog_is_fixed_and_describes_both_lists():
    assert [item.id for item in CATALOG] == ["chance_express", "leidsa_quiniela"]
    assert DEFAULT_LIST_ID == "chance_express"
    chance = get_list("chance_express")
    assert chance is not None
    assert (chance.name, chance.positions, chance.number_range) == (
        "Loteka Chance Express",
        5,
        (0, 99),
    )
    assert chance.default_prizes == (80, 8, 4, 2, 1)
    assert chance.history_file == "datos/chance_express_history.json"
    assert chance.history_sha256 == HISTORY_SHA256
    assert chance.has_rankings is True
    leidsa = get_list("leidsa_quiniela")
    assert leidsa is not None
    assert (leidsa.name, leidsa.positions, leidsa.number_range) == (
        "Quiniela Leidsa",
        3,
        (0, 99),
    )
    assert leidsa.default_prizes == (60, 8, 4)
    assert leidsa.history_file == "datos/leidsa_quiniela_history.json"
    assert leidsa.history_sha256 is None
    assert leidsa.has_rankings is False
    assert get_list("nope") is None


# ----------------------------------------------------------------------- parsing


def test_leidsa_parses_three_positions_matching_the_file():
    history = load_history(LEIDSA_FILE, None, positions=3)
    assert history.nums.shape == (1381, 3)
    assert history.nums.dtype == np.uint8
    assert len(history.labels) == 1381
    assert history.labels[0] == "2023-01-04 20:50"
    assert history.labels[-1] == "2026-11-16 20:50"
    assert tuple(history.nums[0]) == (65, 95, 31)
    assert tuple(history.nums[-1]) == (1, 47, 51)
    assert history.minutes.shape == (1381,)


def test_leidsa_empty_days_are_not_draws():
    raw = json.dumps(
        {
            "sorteos_por_fecha": {
                "2023-04-06": [],
                "2023-04-07": [{"hora": "20:50", "numeros": ["01", "02", "03"]}],
            }
        }
    ).encode()
    history = parse_history(raw, positions=3)
    assert history.labels == ("2023-04-07 20:50",)
    assert history.nums.shape == (1, 3)
    assert parse_history(b'{"sorteos_por_fecha": {}}', positions=3).nums.shape == (0, 3)


def test_position_count_is_enforced_per_list():
    leidsa_raw = LEIDSA_FILE.read_bytes()
    with pytest.raises(DataError):
        parse_history(leidsa_raw)  # default stays five positions
    with pytest.raises(DataError):
        parse_history(leidsa_raw, positions=5)
    chance_raw = (REPO_ROOT / "datos" / "chance_express_history.json").read_bytes()
    with pytest.raises(DataError):
        parse_history(chance_raw, positions=3)


def test_chance_express_parse_is_byte_identical_to_before():
    history = load_history(Settings.from_environment().history_path, HISTORY_SHA256, positions=5)
    assert history.nums.shape == (105426, 5)
    assert history.nums.dtype == np.uint8
    assert hashlib.sha256(history.nums.tobytes()).hexdigest() == (
        "018f7ef445a32c412447097c796fa17155cb7feaddb4ac94f4e2be94d5e102bc"
    )
    assert hashlib.sha256(history.minutes.tobytes()).hexdigest() == (
        "af2e332cfed03a0fbd6eb789d9f6b2bf2cf6a72527ac69c3133c0c7a783b0164"
    )
    assert hashlib.sha256("\n".join(history.labels).encode()).hexdigest() == (
        "a984d63b27139d8c9cb075c446a7991b88ea20436b302ae7fcc72d8535834b32"
    )
    assert (
        load_history(Settings.from_environment().history_path, HISTORY_SHA256).sha256
        == history.sha256
    )


# ---------------------------------------------------------------------- migration


def test_fresh_database_has_active_list_singleton_defaulting_to_chance(tmp_path):
    assert SCHEMA_VERSION >= 21
    path = tmp_path / "lab.db"
    initialize_database(path)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT id, list_id FROM active_number_list").fetchall() == [
            (1, "chance_express")
        ]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO active_number_list (id, list_id) VALUES (2, 'x')")


def test_v20_database_upgrades_keeping_data(tmp_path):
    from laboratorio.storage import database

    path = tmp_path / "v20.db"
    with closing(sqlite3.connect(path)) as db:
        database._run_migrations(db, 0, list(range(1, 21)))
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 20
        labs_before = db.execute("SELECT count(*) FROM laboratory_definitions").fetchone()[0]
    initialize_database(path)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT list_id FROM active_number_list").fetchall() == [
            ("chance_express",)
        ]
        assert (
            db.execute("SELECT count(*) FROM laboratory_definitions").fetchone()[0] == labs_before
        )


def test_repository_active_list_round_trip(repo):
    assert repo.get_active_list_id() == "chance_express"
    repo.set_active_list_id("leidsa_quiniela")
    assert repo.get_active_list_id() == "leidsa_quiniela"
    assert Repository(repo.path).get_active_list_id() == "leidsa_quiniela"


# --------------------------------------------------------------------------- API


def test_get_lists_describes_catalog_and_marks_chance_active(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        response = client.get("/api/v1/lists")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "chance_express",
            "name": "Loteka Chance Express",
            "positions": 5,
            "draws": 105426,
            "first_label": "2025-03-05 05:05",
            "last_label": "2026-09-25 18:20",
            "active": True,
            "available": True,
        },
        {
            "id": "leidsa_quiniela",
            "name": "Quiniela Leidsa",
            "positions": 3,
            "draws": 1381,
            "first_label": "2023-01-04 20:50",
            "last_label": "2026-11-16 20:50",
            "active": False,
            "available": True,
        },
    ]


def test_put_active_switches_without_restart_and_persists_across_apps(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        response = client.put(
            "/api/v1/lists/active", json={"id": "leidsa_quiniela"}, headers=ORIGIN
        )
        assert response.status_code == 200, response.text
        listed = {item["id"]: item for item in response.json()}
        assert listed["leidsa_quiniela"]["active"] is True
        assert listed["chance_express"]["active"] is False
        again = {item["id"]: item["active"] for item in client.get("/api/v1/lists").json()}
        assert again == {"chance_express": False, "leidsa_quiniela": True}
    assert active_in_db(tmp_path) == [("leidsa_quiniela",)]

    # A brand-new app instance (new process) starts with the persisted choice.
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert client.get("/api/v1/settings").status_code == 200
        again = {item["id"]: item["active"] for item in client.get("/api/v1/lists").json()}
        assert again == {"chance_express": False, "leidsa_quiniela": True}
        back = client.put("/api/v1/lists/active", json={"id": "chance_express"}, headers=ORIGIN)
        assert back.status_code == 200
    assert active_in_db(tmp_path) == [("chance_express",)]


def test_put_unknown_list_is_rejected_and_active_unchanged(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        response = client.put("/api/v1/lists/active", json={"id": "otra"}, headers=ORIGIN)
        assert response.status_code == 422
        assert response.json() == {"detail": MSG_UNKNOWN}
        bad_body = client.put("/api/v1/lists/active", json={"nombre": "x"}, headers=ORIGIN)
        assert bad_body.status_code == 422
    assert active_in_db(tmp_path) == [("chance_express",)]


def test_missing_list_file_is_unavailable_and_put_is_rejected(tmp_path, lab_data):
    empty = tmp_path / "sin-datos"
    empty.mkdir()
    app = make_app(tmp_path / "db", lab_data, repo_root=empty)
    with TestClient(app, base_url=BASE_URL) as client:
        listed = {item["id"]: item for item in client.get("/api/v1/lists").json()}
        assert listed["leidsa_quiniela"]["available"] is False
        assert listed["leidsa_quiniela"]["draws"] is None
        assert listed["leidsa_quiniela"]["first_label"] is None
        assert listed["chance_express"]["available"] is True
        response = client.put(
            "/api/v1/lists/active", json={"id": "leidsa_quiniela"}, headers=ORIGIN
        )
        assert response.status_code == 409
        assert response.json() == {"detail": MSG_MISSING}
    assert active_in_db(tmp_path / "db") == [("chance_express",)]


def test_corrupt_list_file_is_unavailable(tmp_path, lab_data):
    datos = tmp_path / "root" / "datos"
    datos.mkdir(parents=True)
    (datos / "leidsa_quiniela_history.json").write_text("{ no es json", encoding="utf-8")
    app = make_app(tmp_path / "db", lab_data, repo_root=datos.parent)
    with TestClient(app, base_url=BASE_URL) as client:
        listed = {item["id"]: item for item in client.get("/api/v1/lists").json()}
        assert listed["leidsa_quiniela"]["available"] is False
        response = client.put(
            "/api/v1/lists/active", json={"id": "leidsa_quiniela"}, headers=ORIGIN
        )
        assert response.status_code == 409


def test_list_is_reloaded_when_its_file_changes(tmp_path, lab_data):
    datos = tmp_path / "root" / "datos"
    datos.mkdir(parents=True)
    target = datos / "leidsa_quiniela_history.json"
    one_draw = {"2024-01-01": [{"hora": "20:50", "numeros": ["01", "02", "03"]}]}
    target.write_text(json.dumps({"sorteos_por_fecha": one_draw}), encoding="utf-8")
    app = make_app(tmp_path / "db", lab_data, repo_root=datos.parent)
    with TestClient(app, base_url=BASE_URL) as client:
        first = {i["id"]: i for i in client.get("/api/v1/lists").json()}["leidsa_quiniela"]
        assert first["draws"] == 1
        target.write_text(
            json.dumps(
                {
                    "sorteos_por_fecha": {
                        "2024-01-01": [{"hora": "20:50", "numeros": ["01", "02", "03"]}],
                        "2024-01-02": [{"hora": "20:50", "numeros": ["04", "05", "06"]}],
                    }
                }
            ),
            encoding="utf-8",
        )
        second = {i["id"]: i for i in client.get("/api/v1/lists").json()}["leidsa_quiniela"]
        assert second["draws"] == 2
        assert second["last_label"] == "2024-01-02 20:50"


# ------------------------------------------------- Leidsa active: no silent Loteka data


# Laboratories and runs now work with Leidsa (tests/test_leidsa_labs.py); only the history
# import and the fixed Chance reference labs stay Loteka-only.
BLOCKED_REQUESTS = [
    ("get", "/api/v1/history", None),
    ("get", "/api/v1/reference-labs", None),
    (
        "post",
        "/api/v1/reference-labs/paridad_50_audaz/runs",
        {"required_history_sha256": HISTORY_SHA256},
    ),
]


@pytest.mark.parametrize("method,path,body", BLOCKED_REQUESTS)
def test_loteka_only_endpoints_fail_clearly_while_leidsa_is_active(
    tmp_path, lab_data, method, path, body
):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert (
            client.put(
                "/api/v1/lists/active", json={"id": "leidsa_quiniela"}, headers=ORIGIN
            ).status_code
            == 200
        )
        kwargs = {"headers": ORIGIN}
        if body is not None:
            kwargs["json"] = body
        response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": MSG_BLOCKED}


def test_loteka_endpoints_still_work_while_chance_is_active(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert client.get("/api/v1/history").status_code == 200
        assert client.get("/api/v1/runs/options").status_code == 200
        assert client.get("/api/v1/reference-labs").status_code == 200
