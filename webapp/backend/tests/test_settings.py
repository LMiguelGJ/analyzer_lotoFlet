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
