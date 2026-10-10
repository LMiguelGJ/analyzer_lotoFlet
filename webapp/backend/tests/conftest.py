"""Shared fixtures."""

from dataclasses import replace

import pytest


@pytest.fixture(scope="session")
def lab_data(tmp_path_factory):
    from laboratorio.engine.adapter import open_lab_data
    from laboratorio.settings import Settings

    data_dir = tmp_path_factory.mktemp("lab-data")
    return open_lab_data(replace(Settings.from_environment(), data_dir=data_dir))
