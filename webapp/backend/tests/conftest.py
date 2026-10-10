"""Shared fixtures."""

from dataclasses import replace

import pytest


@pytest.fixture(scope="session")
def lab_data(tmp_path_factory):
    from laboratorio.engine.adapter import open_lab_data
    from laboratorio.settings import Settings

    data_dir = tmp_path_factory.mktemp("lab-data")
    return open_lab_data(replace(Settings.from_environment(), data_dir=data_dir))


@pytest.fixture
def repo(tmp_path):
    from laboratorio.storage.database import initialize_database
    from laboratorio.storage.repository import Repository

    path = tmp_path / "lab.db"
    initialize_database(path)
    return Repository(path)


@pytest.fixture
def run_environment(repo, lab_data, tmp_path):
    from dataclasses import replace

    from laboratorio.engine.active_history import HistoryCatalog
    from laboratorio.settings import Settings

    settings = replace(Settings.from_environment(), data_dir=tmp_path)
    return HistoryCatalog(repo, lab_data, settings), settings
