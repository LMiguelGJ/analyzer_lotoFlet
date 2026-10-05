"""Active-game ceilings and the persistent local game-rules editor."""

import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain import contracts
from laboratorio.domain.contracts import make_game
from laboratorio.settings import Settings


def test_game_rule_ceilings_preserve_supported_games():
    """B-NEW-001: reject allocations beyond the published ceilings."""
    assert make_game("Quiniela 80", 100, 5, (80, 8, 4, 2, 1), True).numbers == 100
    assert make_game("Tres", 60, 3, (60, 10, 5), True).positions == 3
    for args in (
        ("Too many numbers", 1001, 5, (80, 8, 4, 2, 1), True),
        ("Too many positions", 100, 17, (80,) * 17, True),
    ):
        with pytest.raises(ValueError):
            make_game(*args)


def _editor_client(settings):
    def catalog(_):
        return SimpleNamespace(
            history=SimpleNamespace(labels=("2025-01-01 05:10",), sha256="a" * 64),
            rankings=SimpleNamespace(row_ids=(0,), path="rankings.npz"),
        )

    return TestClient(
        create_app(settings, catalog_loader=catalog),
        base_url=f"http://127.0.0.1:{settings.port}",
    )


def test_game_rules_editor_persists_and_is_loaded_on_restart(tmp_path, monkeypatch):
    """B-NEW-002: validate, persist, and adopt game rules for future app sessions."""
    monkeypatch.setenv("LABORATORIO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LABORATORIO_GAME_NAME", "Environment")
    monkeypatch.setenv("LABORATORIO_GAME_NUMBERS", "70")
    settings = Settings.from_environment()
    updated = {
        "name": "Tres persistente",
        "numbers": 60,
        "positions": 3,
        "prizes": [60, 10, 5],
        "allows_repeats": True,
        "minimum_stake": 2,
    }
    with _editor_client(settings) as client:
        before = client.get("/api/v1/settings/game")
        assert before.status_code == 200
        response = client.put("/api/v1/settings/game", json=updated)
        assert response.status_code == 200
        persisted = client.get("/api/v1/settings/game")
        assert persisted.status_code == 200
        assert persisted.json() == response.json()

    with sqlite3.connect(settings.database_path) as database:
        row = database.execute("SELECT id FROM settings_game WHERE id = 1").fetchone()
    assert row == (1,)

    # Startup precedence includes the stored rules over the environment/default.
    restarted = Settings.from_environment()
    with _editor_client(restarted) as client:
        assert client.get("/api/v1/settings/game").json() == persisted.json()
        assert (contracts.GAME.name, contracts.GAME.numbers, contracts.GAME.positions) == (
            "Tres persistente",
            60,
            3,
        )


def test_game_rules_editor_guards_mutation_and_validates_rules(tmp_path):
    """B-NEW-002: Origin and make_game validation are enforced at the route."""
    settings = Settings(
        tmp_path / "data",
        tmp_path / "history.json",
        tmp_path / "rankings.npz",
        tmp_path / "frontend",
    )
    with _editor_client(settings) as client:
        body = {
            "name": "Invalid",
            "numbers": 1001,
            "positions": 5,
            "prizes": [80, 8, 4, 2, 1],
            "allows_repeats": True,
            "minimum_stake": 1,
        }
        denied = client.put("/api/v1/settings/game", json=body)
        assert denied.status_code == 403
        invalid = client.put(
            "/api/v1/settings/game",
            json=body,
            headers={"Origin": "http://127.0.0.1:8765"},
        )
        assert invalid.status_code == 422
        assert "numbers" in invalid.text.lower()
