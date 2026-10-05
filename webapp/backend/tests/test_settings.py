"""Settings provenance and active-game configuration contracts."""

import os
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import pytest_collection_modifyitems

from laboratorio.domain import contracts
from laboratorio.settings import DEFAULT_QUOTA_BYTES, Settings

GAME_VARS = (
    "LABORATORIO_GAME_NAME",
    "LABORATORIO_GAME_NUMBERS",
    "LABORATORIO_GAME_POSITIONS",
    "LABORATORIO_GAME_PRIZES",
    "LABORATORIO_GAME_REPEATS",
    "LABORATORIO_GAME_MINIMUM_STAKE",
)


@pytest.fixture
def clean_game(monkeypatch):
    """Keep tests independent despite Settings applying rules to a shared object."""
    original = contracts.GAME.__class__(
        contracts.GAME.name,
        contracts.GAME.numbers,
        contracts.GAME.positions,
        contracts.GAME.prizes,
        contracts.GAME.allows_repeats,
        contracts.GAME.minimum_stake,
    )
    for name in GAME_VARS:
        monkeypatch.delenv(name, raising=False)
    yield
    contracts.configure_game(original)


def test_explicit_default_environment_quota_is_still_read_only(tmp_path, monkeypatch):
    """B-SET-001: explicit provenance survives dataclasses.replace."""
    monkeypatch.setenv("LABORATORIO_QUOTA_BYTES", str(DEFAULT_QUOTA_BYTES))
    settings = Settings.from_environment()
    assert settings.quota_bytes == DEFAULT_QUOTA_BYTES
    assert settings.is_quota_explicit is True
    assert replace(settings, data_dir=tmp_path).is_quota_explicit is True


def test_manual_quota_provenance_is_legacy_compatible_and_validated(tmp_path):
    """B-SET-002: explicit quota can be opted into or out of."""
    settings = Settings(tmp_path, tmp_path / "history", tmp_path / "ranks", tmp_path)
    assert settings.is_quota_explicit is False
    assert replace(settings, quota_bytes=123).is_quota_explicit is True
    assert replace(settings, quota_explicit=False, quota_bytes=123).is_quota_explicit is False
    with pytest.raises(ValueError, match="quota_explicit"):
        replace(settings, quota_explicit=1)


def test_defaults_produce_the_quiniela_80_game(clean_game):
    """B-SET-003: defaults configure the legacy game globally."""
    settings = Settings.from_environment()
    assert settings.game.name == "Quiniela 80"
    assert (contracts.GAME.numbers, contracts.GAME.positions) == (100, 5)
    assert contracts.GAME.prizes == (80, 8, 4, 2, 1)
    assert contracts.GAME.allows_repeats is True
    assert contracts.GAME.minimum_stake == 1


def test_environment_configures_three_position_game(clean_game, monkeypatch):
    """B-SET-004: all game environment fields configure the active rules."""
    values = {
        "LABORATORIO_GAME_NAME": "Tres",
        "LABORATORIO_GAME_NUMBERS": "50",
        "LABORATORIO_GAME_POSITIONS": "3",
        "LABORATORIO_GAME_PRIZES": "60, 10,5",
        "LABORATORIO_GAME_REPEATS": "false",
        "LABORATORIO_GAME_MINIMUM_STAKE": "5",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    settings = Settings.from_environment()
    assert (settings.game.name, contracts.GAME.numbers, contracts.GAME.positions) == (
        "Tres",
        50,
        3,
    )
    assert contracts.GAME.prizes == (60, 10, 5)
    assert contracts.GAME.allows_repeats is False
    assert contracts.GAME.minimum_stake == 5


@pytest.mark.parametrize(("value", "expected"), [("1", True), ("TRUE", True), ("0", False)])
def test_environment_repeats_flag_spellings(clean_game, monkeypatch, value, expected):
    """B-SET-005: accepted boolean flag spellings are stable."""
    monkeypatch.setenv("LABORATORIO_GAME_REPEATS", value)
    Settings.from_environment()
    assert contracts.GAME.allows_repeats is expected


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("LABORATORIO_GAME_NUMBERS", "abc", "LABORATORIO_GAME_NUMBERS"),
        ("LABORATORIO_GAME_POSITIONS", "1.5", "LABORATORIO_GAME_POSITIONS"),
        ("LABORATORIO_GAME_PRIZES", "60,x", "LABORATORIO_GAME_PRIZES"),
        ("LABORATORIO_GAME_REPEATS", "maybe", "LABORATORIO_GAME_REPEATS"),
        ("LABORATORIO_GAME_MINIMUM_STAKE", "0", "minimum_stake"),
        ("LABORATORIO_GAME_PRIZES", "60,10", "one prize"),
    ],
)
def test_invalid_game_environment_names_the_invalid_rule(
    clean_game, monkeypatch, name, value, message
):
    """B-SET-006: malformed game settings fail with a useful rule/variable."""
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=message):
        Settings.from_environment()


def test_replace_preserves_configured_game(clean_game, tmp_path):
    """B-SET-007: replacing unrelated settings retains the selected game."""
    settings = Settings(
        tmp_path, tmp_path, tmp_path, tmp_path, game_positions=3, game_prizes=(60, 10, 5)
    )
    assert replace(settings, port=9000).game.prizes == (60, 10, 5)



# --- Game rules editor: persistence, API and resolution order -----------------------
# --- Game rules editor: persistence, API and resolution order ---------------------------

from types import SimpleNamespace  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from laboratorio.app import create_app  # noqa: E402
from laboratorio.storage.database import connection, initialize_database  # noqa: E402
from laboratorio.storage.repository import Repository  # noqa: E402

ORIGIN = {"Origin": "http://localhost:8765"}
THREE = {
    "name": "Tres",
    "numbers": 50,
    "positions": 3,
    "prizes": [30, 6, 2],
    "allows_repeats": False,
    "minimum_stake": 5,
}


class _Catalog:
    history = SimpleNamespace(labels=("2025-01-01 05:10",), sha256="a" * 64)
    rankings = SimpleNamespace(row_ids=(0,), path="rankings.npz")


def _settings(tmp_path):
    return Settings(tmp_path / "data", tmp_path / "h.json", tmp_path / "r.npz", tmp_path)


@pytest.fixture
def game_client(tmp_path):
    app = create_app(_settings(tmp_path), catalog_loader=lambda _: _Catalog())
    with TestClient(app, base_url="http://localhost:8765") as client:
        yield client, tmp_path


def test_game_defaults_are_reported_as_default(game_client):
    client, _ = game_client
    body = client.get("/api/v1/settings/game").json()
    assert body == {
        "name": "Quiniela 80",
        "numbers": 100,
        "positions": 5,
        "prizes": [80, 8, 4, 2, 1],
        "allows_repeats": True,
        "minimum_stake": 1,
        "source": "default",
    }


def test_game_put_get_roundtrip_adopts_rules_in_the_running_app(game_client):
    client, _ = game_client
    put = client.put("/api/v1/settings/game", json=THREE, headers=ORIGIN)
    assert put.status_code == 200
    assert put.json() == {**THREE, "source": "stored"}
    assert client.get("/api/v1/settings/game").json() == {**THREE, "source": "stored"}
    assert contracts.GAME.positions == 3 and contracts.GAME.prizes == (30, 6, 2)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"numbers": 1}, "numbers must be at least 2"),
        ({"positions": 0, "prizes": []}, "positions must be at least 1"),
        ({"numbers": 2, "positions": 3, "prizes": [3, 2, 1]}, "positions exceed numbers"),
        ({"prizes": [30, 6]}, "exactly one prize is required per position"),
        ({"prizes": [30, 0, 2]}, "every prize must be at least 1"),
        ({"minimum_stake": 0}, "minimum_stake must be at least 1"),
        ({"name": "  "}, "name must have between 1 and 80 characters"),
        ({"numbers": 1001}, "numbers must be at most 1000"),
        ({"positions": 17, "prizes": [1] * 17}, "positions must be at most 16"),
    ],
)
def test_game_put_rejects_invalid_rules_with_the_reason(game_client, change, reason):
    client, _ = game_client
    response = client.put("/api/v1/settings/game", json={**THREE, **change}, headers=ORIGIN)
    assert response.status_code == 422
    assert reason in response.json()["detail"]
    assert client.get("/api/v1/settings/game").json()["source"] == "default"


def test_game_put_requires_origin_like_other_mutations(game_client):
    client, _ = game_client
    assert client.put("/api/v1/settings/game", json=THREE).status_code == 403


def test_stored_game_survives_a_restart(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(
        create_app(settings, catalog_loader=lambda _: _Catalog()), base_url="http://localhost:8765"
    ) as client:
        client.put("/api/v1/settings/game", json=THREE, headers=ORIGIN)
    Settings(*(Path("."),) * 4)  # a fresh process starts from the default rules
    assert contracts.GAME.positions == 5
    assert Repository(settings.database_path).get_game_settings().prizes == (30, 6, 2)
    with TestClient(
        create_app(settings, catalog_loader=lambda _: _Catalog()), base_url="http://localhost:8765"
    ) as client:
        assert client.get("/api/v1/settings/game").json() == {**THREE, "source": "stored"}
        assert contracts.GAME.numbers == 50


def test_resolution_order_is_stored_then_environment_then_default(tmp_path, monkeypatch):
    base = _settings(tmp_path)
    assert base.game_source == "default"
    monkeypatch.setenv("LABORATORIO_GAME_NUMBERS", "60")
    from_env = Settings.from_environment()
    assert from_env.game_source == "environment" and from_env.game.numbers == 60
    app = create_app(
        replace(from_env, data_dir=tmp_path / "data"), catalog_loader=lambda _: _Catalog()
    )
    with TestClient(app, base_url="http://localhost:8765") as client:
        env_view = client.get("/api/v1/settings/game").json()
        assert (env_view["numbers"], env_view["source"]) == (60, "environment")
        client.put("/api/v1/settings/game", json=THREE, headers=ORIGIN)
    # A restart with the environment still set: the stored value wins.
    stored = Repository(from_env_path := tmp_path / "data" / "laboratorio.db").get_game_settings()
    assert from_env_path.is_file()
    assert Settings.from_stored_game(from_env, stored).game.numbers == 50
    assert Settings.from_stored_game(from_env, None).game.numbers == 60
    app = create_app(
        replace(from_env, data_dir=tmp_path / "data"), catalog_loader=lambda _: _Catalog()
    )
    with TestClient(app, base_url="http://localhost:8765") as client:
        assert client.get("/api/v1/settings/game").json()["numbers"] == 50
        assert contracts.GAME.numbers == 50


def test_saving_rules_does_not_rewrite_existing_experiment_profiles(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_path)
    with connection(settings.database_path) as db:
        before = db.execute("SELECT * FROM game_profiles ORDER BY profile_id, revision").fetchall()
    assert before, "the legacy Quiniela 80 profile is seeded"
    app = create_app(settings, catalog_loader=lambda _: _Catalog())
    with TestClient(app, base_url="http://localhost:8765") as client:
        client.put("/api/v1/settings/game", json=THREE, headers=ORIGIN)
    with connection(settings.database_path) as db:
        after = db.execute("SELECT * FROM game_profiles ORDER BY profile_id, revision").fetchall()
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert after == before and "settings_game" in tables

# --- Settings construction, data dir isolation and quota validation ---------------
def test_settings_construction_applies_rules_and_fixture_restores_global(clean_game, tmp_path):
    """B-SET-008: game mutation is isolated and reset after the test."""
    Settings(
        tmp_path,
        tmp_path,
        tmp_path,
        tmp_path,
        game_name="Temporary",
        game_positions=3,
        game_prizes=(60, 10, 5),
    )
    assert contracts.GAME.name == "Temporary"
    assert contracts.GAME.positions == 3


def test_data_directory_and_real_data_skip_are_isolated(data_dir, monkeypatch):
    """B-SET-009: fixtures isolate writes and honor the real-data skip switch."""
    assert data_dir.is_absolute()
    assert Path(os.environ["LABORATORIO_DATA_DIR"]) == data_dir
    monkeypatch.setenv("LABORATORIO_SKIP_REAL_DATA", "1")
    class Item:
        def __init__(self):
            self.keywords = {"real_data"}
            self.markers = []

        def add_marker(self, marker):
            self.markers.append(marker)

    item = Item()
    pytest_collection_modifyitems(None, [item])
    assert item.markers


def test_quota_default_and_environment_validation(clean_game, monkeypatch, tmp_path):
    """B-SET-010: quota defaults to 5 GiB and accepts only valid configured bytes."""
    assert Settings.from_environment().quota_bytes == 5 * 1024**3
    for invalid in ("0", "-1", "true", "1.0", str(2**63)):
        monkeypatch.setenv("LABORATORIO_QUOTA_BYTES", invalid)
        with pytest.raises(ValueError, match=r"quota|QUOTA"):
            Settings.from_environment()
    for invalid in (0, -1, True, 1.0, "1", 2**63):
        with pytest.raises(ValueError, match="quota"):
            Settings(tmp_path, tmp_path, tmp_path, tmp_path, quota_bytes=invalid)
    monkeypatch.setenv("LABORATORIO_QUOTA_BYTES", "2147483648")
    assert Settings.from_environment().quota_bytes == 2_147_483_648
    monkeypatch.setenv("LABORATORIO_QUOTA_BYTES", "invalid")
    with pytest.raises(ValueError, match="LABORATORIO_QUOTA_BYTES"):
        Settings.from_environment()
