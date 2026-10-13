"""Public isolated API contracts for immutable v2 quiniela profiles."""

import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.settings import Settings
from laboratorio.storage import database
from laboratorio.storage.repository import Repository

BASE_URL = "http://localhost:8765"
HEADERS = {"Origin": BASE_URL, "Content-Type": "application/json"}
ROOT = "/api/v2/game-profiles"
LIMIT_ERROR = "La solicitud supera el límite de 64 KiB."
CONFLICT_ERROR = "No se pudo crear el perfil por un conflicto o límite de cuota."


def rules(*, numbers=100, positions=5):
    payouts = [80, 8, 4, 2, 1] if positions == 5 else [1] * positions
    return {
        "schema_version": 2,
        "universe": list(range(numbers)),
        "display_width": len(str(numbers - 1)),
        "positions": positions,
        "played_positions": list(range(positions)),
        "order_matters": True,
        "allows_repeats": True,
        "multipliers": [{"numerator": value, "denominator": 1} for value in payouts],
        "payout_mode": "all",
        "currency": "DOP",
        "scale": 0,
        "minimum_stake": 10,
        "stake_increment": 10,
        "maximum_stake": 10_000,
        "max_coverage": numbers,
        "max_exposure": 1_000_000,
    }


def make_app(tmp_path, lab_data, *, quota_bytes=None):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    if quota_bytes is not None:
        settings = replace(settings, quota_bytes=quota_bytes, quota_explicit=True)
    return create_app(settings, catalog_loader=lambda _settings: lab_data)


def post(client, name="Quiniela configurable", game_rules=None, **extra):
    return client.post(
        ROOT,
        json={"name": name, "rules": rules() if game_rules is None else game_rules, **extra},
        headers=HEADERS,
    )


def public_state(client):
    storage = client.get("/api/v1/settings").json()["storage"]
    return {
        "profiles": client.get(ROOT).json(),
        "laboratories": client.get("/api/v1/laboratories").json(),
        "counters": {
            key: storage[key]
            for key in (
                "logical_used_bytes_exact",
                "profile_artifact_bytes_exact",
                "admission_logical_bytes_exact",
            )
        },
    }


@pytest.mark.parametrize("numbers,positions", [(100, 5), (4, 2), (1000, 16)])
def test_create_reopen_and_page_profiles_outside_legacy_shape(
    tmp_path, lab_data, numbers, positions
):
    app = make_app(tmp_path, lab_data)
    payload = rules(numbers=numbers, positions=positions)
    original = deepcopy(payload)
    with TestClient(app, base_url=BASE_URL) as client:
        response = post(client, " Otro juego ", payload)
        assert response.status_code == 201, response.text
        record = response.json()
        assert set(record) == {"profile", "sha256", "created_at"}
        profile = record["profile"]
        assert set(profile) == {"schema_version", "id", "name", "rules"}
        assert profile["schema_version"] == 2
        assert str(uuid.UUID(profile["id"])) == profile["id"]
        assert uuid.UUID(profile["id"]).version == 4
        assert profile["name"] == "Otro juego"
        assert profile["rules"] == payload == original
        canonical = json.dumps(
            profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        assert record["sha256"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert client.get(f"{ROOT}/{profile['id']}").json() == record
        assert client.get(ROOT).json() == {"items": [record], "total": 1, "offset": 0, "limit": 20}
        assert client.get(ROOT, params={"offset": 1, "limit": 1}).json() == {
            "items": [],
            "total": 1,
            "offset": 1,
            "limit": 1,
        }
        assert client.get("/api/v1/laboratories").json()["total"] == 14
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert client.get(f"{ROOT}/{profile['id']}").json() == record
        assert client.get(ROOT).json()["total"] == 1


@pytest.mark.parametrize(
    "replacement",
    [
        {"schema_version": True},
        {"schema_version": 2.0},
        {"schema_version": "2"},
        {"universe": [0, True]},
        {"universe": [0, 1.0]},
        {"universe": [0, "1"]},
        {"universe": [0, 0]},
        {"universe": [2, 1]},
        {"universe": [0]},
        {"universe": list(range(1001))},
        {"positions": 0},
        {"positions": 17},
        {"played_positions": [0, 0]},
        {"played_positions": [5]},
        {"allows_repeats": "true"},
        {"order_matters": 1},
        {"minimum_stake": 1.0},
        {"minimum_stake": True},
        {"minimum_stake": 0},
        {"maximum_stake": 5},
        {"max_coverage": 101},
        {"max_exposure": 1},
        {"scale": 7},
        {"currency": "dop"},
        {"payout_mode": "first-match/v0"},
        {"multipliers": [{"numerator": 1, "denominator": 3}] * 5},
        {"multipliers": [{"numerator": 1, "denominator": 1, "code": "x"}] * 5},
        {"multipliers": [{"numerator": True, "denominator": 1}] * 5},
        {"order_matters": False},
        {"unexpected": "plugin"},
    ],
)
def test_invalid_rules_are_422_and_leave_public_data_and_counters_unchanged(
    tmp_path, lab_data, replacement
):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        before = public_state(client)
        response = post(client, game_rules=rules() | replacement)
        assert response.status_code == 422, response.text
        assert "detail" in response.json()
        assert public_state(client) == before


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "x"},
        {"name": "", "rules": rules()},
        {"name": "é" * 61, "rules": rules()},
        {"name": True, "rules": rules()},
        {"name": "x", "rules": rules(), "id": str(uuid.uuid4())},
        {"name": "x", "rules": rules(), "executable": True},
    ],
)
def test_invalid_envelope_does_not_admit_profile(tmp_path, lab_data, body):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        before = public_state(client)
        response = client.post(ROOT, json=body, headers=HEADERS)
        assert response.status_code == 422, response.text
        assert public_state(client) == before


@pytest.mark.parametrize(
    "query",
    [
        {"offset": -1},
        {"offset": 2**53},
        {"offset": "1.5"},
        {"limit": 0},
        {"limit": 101},
        {"limit": "x"},
    ],
)
def test_profile_paging_rejects_invalid_bounds(tmp_path, lab_data, query):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        before = public_state(client)
        assert client.get(ROOT, params=query).status_code == 422
        assert public_state(client) == before


def test_missing_and_invalid_identity_are_distinct_without_mutation(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        before = public_state(client)
        missing = client.get(f"{ROOT}/{uuid.uuid4()}")
        assert missing.status_code == 404
        assert missing.json() == {"detail": "El perfil de quiniela no existe."}
        assert client.get(f"{ROOT}/not-a-uuid").status_code == 422
        assert public_state(client) == before


def test_duplicate_and_quota_are_atomic_conflicts(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert post(client, "Duplicado").status_code == 201
        before = public_state(client)
        response = post(client, "DUPLICADO")
        assert response.status_code == 409
        assert response.json() == {"detail": CONFLICT_ERROR}
        assert public_state(client) == before
    with TestClient(
        make_app(tmp_path / "quota", lab_data, quota_bytes=1), base_url=BASE_URL
    ) as client:
        before = public_state(client)
        response = post(client)
        assert response.status_code == 409
        assert response.json() == {"detail": CONFLICT_ERROR}
        assert public_state(client) == before


def test_concurrent_duplicate_is_admitted_once(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _index: post(client, "Único"), range(2)))
        assert sorted(response.status_code for response in responses) == [201, 409]
        page = client.get(ROOT).json()
        assert page["total"] == 1
        assert page["items"][0]["profile"]["name"] == "Único"


def test_new_profiles_are_counted_by_existing_public_quota(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        before = public_state(client)
        response = post(client)
        assert response.status_code == 201
        profile = response.json()["profile"]
        serialized = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        expected = len(serialized.encode("utf-8"))
        after = public_state(client)
        assert int(after["counters"]["profile_artifact_bytes_exact"]) == (
            int(before["counters"]["profile_artifact_bytes_exact"]) + expected
        )
        assert int(after["counters"]["admission_logical_bytes_exact"]) == (
            int(before["counters"]["admission_logical_bytes_exact"]) + expected
        )
        assert after["laboratories"] == before["laboratories"]


def test_v17_upgrade_does_not_reseed_deleted_laboratories(tmp_path, lab_data, monkeypatch):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    with monkeypatch.context() as old:
        old.setattr(database, "SCHEMA_VERSION", 17)
        database.initialize_database(settings.database_path)
        repository = Repository(settings.database_path)
        for definition in repository.list_laboratory_definitions()["items"]:
            repository.delete_laboratory_definition(definition.id, confirmed_run_count=0)
        assert repository.list_laboratory_definitions()["total"] == 0
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert client.get("/api/v1/laboratories").json()["total"] == 0
        assert client.get(ROOT).json() == {"items": [], "total": 0, "offset": 0, "limit": 20}
        assert post(client).status_code == 201
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert client.get("/api/v1/laboratories").json()["total"] == 0
        assert client.get(ROOT).json()["total"] == 1


@pytest.mark.parametrize(
    "headers,expected,detail",
    [
        ({"Content-Type": "application/json"}, 403, "Origin required for mutation"),
        (HEADERS | {"Origin": "http://elsewhere.invalid"}, 403, "same-origin required"),
        (HEADERS | {"Host": "elsewhere.invalid"}, 403, "local Host required"),
        (HEADERS | {"Sec-Fetch-Site": "cross-site"}, 403, "cross-site requests denied"),
        (HEADERS | {"Content-Length": "9" * 4301}, 413, LIMIT_ERROR),
    ],
)
def test_profile_posts_keep_local_guards_and_bounded_headers(
    tmp_path, lab_data, headers, expected, detail
):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        before = public_state(client)
        response = client.post(ROOT, json={"name": "x", "rules": rules()}, headers=headers)
        assert response.status_code == expected
        assert response.json() == {"detail": detail}
        assert public_state(client) == before


def test_profile_body_actual_bytes_and_duplicate_keys_are_guarded(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        before = public_state(client)
        response = client.post(ROOT, content=b"x" * (64 * 1024 + 1), headers=HEADERS)
        assert response.status_code == 413
        assert response.json() == {"detail": LIMIT_ERROR}
        payload = '{"name":"one","name":"two","rules":' + json.dumps(rules()) + "}"
        response = client.post(ROOT, content=payload, headers=HEADERS)
        assert response.status_code == 422
        assert response.json() == {"detail": "La solicitud contiene claves JSON duplicadas."}
        assert public_state(client) == before


@pytest.mark.parametrize("stored_json", ["{", "[]", '{"x":1,"x":2}'])
def test_corrupt_stored_json_is_rejected_without_repair(tmp_path, lab_data, stored_json):
    # Fault injection is fixture preparation only, inside this test-owned DB.
    # Observable outcomes/counters are asserted exclusively through the API.
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        response = post(client)
        assert response.status_code == 201
        identifier = response.json()["profile"]["id"]
        with database.connection(app.state.repo.path) as db:
            db.execute(
                "UPDATE quiniela_game_profiles SET profile_json=? WHERE id=?",
                (stored_json, identifier),
            )
            db.commit()
        before = public_state(client)
        expected = {"detail": "Un perfil guardado está dañado y no se puede mostrar."}
        for path in (ROOT, f"{ROOT}/{identifier}"):
            response = client.get(path)
            assert response.status_code == 409
            assert response.json() == expected
        assert public_state(client) == before
