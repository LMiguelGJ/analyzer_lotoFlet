"""Quota provenance from environment and manually constructed settings."""

from dataclasses import replace
from pathlib import Path

import pytest

from laboratorio.domain import contracts
from laboratorio.settings import DEFAULT_QUOTA_BYTES, Settings


def test_explicit_default_environment_quota_is_still_read_only(tmp_path, monkeypatch):
    monkeypatch.setenv("LABORATORIO_QUOTA_BYTES", str(DEFAULT_QUOTA_BYTES))
    settings = Settings.from_environment()
    assert settings.quota_bytes == DEFAULT_QUOTA_BYTES
    assert settings.is_quota_explicit is True
    assert replace(settings, data_dir=tmp_path).is_quota_explicit is True


def test_manual_settings_preserve_legacy_override_and_can_opt_into_default(tmp_path):
    settings = Settings(tmp_path, tmp_path / "history", tmp_path / "ranks", tmp_path)
    assert settings.is_quota_explicit is False
    assert replace(settings, quota_bytes=123).is_quota_explicit is True
    assert replace(settings, quota_explicit=False, quota_bytes=123).is_quota_explicit is False
    with pytest.raises(ValueError, match="quota_explicit"):
        replace(settings, quota_explicit=1)


GAME_VARS = (
    "LABORATORIO_GAME_NAME",
    "LABORATORIO_GAME_NUMBERS",
    "LABORATORIO_GAME_POSITIONS",
    "LABORATORIO_GAME_PRIZES",
    "LABORATORIO_GAME_REPEATS",
    "LABORATORIO_GAME_MINIMUM_STAKE",
)


@pytest.fixture(autouse=True)
def clean_game(monkeypatch):
    for name in GAME_VARS:
        monkeypatch.delenv(name, raising=False)
    yield
    # Settings construction applies the game, so default settings restore Quiniela 80.
    monkeypatch.undo()
    Settings(*(Path("."),) * 4)


def test_defaults_produce_the_quiniela_80_game():
    settings = Settings.from_environment()
    assert settings.game.name == "Quiniela 80"
    assert (contracts.GAME.numbers, contracts.GAME.positions) == (100, 5)
    assert contracts.GAME.prizes == (80, 8, 4, 2, 1)
    assert contracts.GAME.allows_repeats is True
    assert contracts.GAME.minimum_stake == 1


def test_environment_configures_a_three_position_game(monkeypatch):
    monkeypatch.setenv("LABORATORIO_GAME_NAME", "Tres")
    monkeypatch.setenv("LABORATORIO_GAME_NUMBERS", "50")
    monkeypatch.setenv("LABORATORIO_GAME_POSITIONS", "3")
    monkeypatch.setenv("LABORATORIO_GAME_PRIZES", "60, 10,5")
    monkeypatch.setenv("LABORATORIO_GAME_REPEATS", "false")
    monkeypatch.setenv("LABORATORIO_GAME_MINIMUM_STAKE", "5")
    Settings.from_environment()
    game = contracts.GAME
    assert (game.name, game.numbers, game.positions) == ("Tres", 50, 3)
    assert game.prizes == (60, 10, 5)
    assert game.allows_repeats is False
    assert game.minimum_stake == 5


@pytest.mark.parametrize(("value", "expected"), [("1", True), ("TRUE", True), ("0", False)])
def test_repeats_accepts_flag_spellings(monkeypatch, value, expected):
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
def test_bad_game_environment_is_rejected(monkeypatch, name, value, message):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=message):
        Settings.from_environment()


def test_replace_keeps_the_configured_game(tmp_path):
    settings = Settings(
        tmp_path, tmp_path, tmp_path, tmp_path, game_positions=3, game_prizes=(60, 10, 5)
    )
    assert replace(settings, port=9000).game.prizes == (60, 10, 5)
