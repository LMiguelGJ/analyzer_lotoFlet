"""Shared fixtures: frozen-data paths and per-test data directories."""

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def real_data_available():
    from laboratorio.settings import Settings

    settings = Settings.from_environment()
    return settings.history_path.exists() and settings.rankings_path.exists()


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Isolated application data directory; never the user's real database."""
    target = tmp_path / "data"
    monkeypatch.setenv("LABORATORIO_DATA_DIR", str(target))
    return target


def pytest_collection_modifyitems(config, items):
    if os.environ.get("LABORATORIO_SKIP_REAL_DATA") == "1" or not real_data_available():
        skip = pytest.mark.skip(reason="frozen history/rankings not available")
        for item in items:
            if "real_data" in item.keywords:
                item.add_marker(skip)
