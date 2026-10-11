"""The legacy backtest engine is retired: no route and no importable modules."""

import importlib.util
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.settings import Settings

BASE_URL = "http://localhost:8765"
ORIGIN = {"Origin": BASE_URL, "Content-Type": "application/json"}

RETIRED_MODULES = (
    "laboratorio.api.backtests",
    "laboratorio.domain.backtest",
    "laboratorio.storage.backtest_trace",
)


@pytest.mark.parametrize("module", RETIRED_MODULES)
def test_retired_modules_are_not_importable(module):
    assert importlib.util.find_spec(module) is None


def test_backtests_routes_are_gone(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    app = create_app(settings, catalog_loader=lambda _settings: lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        assert client.get("/api/v1/backtests").status_code == 404
        assert client.post("/api/v1/backtests", json={}, headers=ORIGIN).status_code == 404
