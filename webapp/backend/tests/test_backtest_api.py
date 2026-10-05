from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256, Settings


class TinyRankings:
    row_ids = (0, 1, 2)

    def family(self, system):
        return ((0, 1, 2, 3),) * 3


class TinyData:
    def __init__(self):
        self.history = SimpleNamespace(
            labels=("2025-01-01 05:10", "2025-01-01 05:15", "2025-01-01 05:20"),
            nums=((0, 1, 2, 3, 4), (9, 8, 7, 6, 5), (0, 9, 8, 7, 6)),
            minutes=(1, 2, 3),
            sha256=HISTORY_SHA256,
        )
        self.rankings = TinyRankings()
        self._cache = {}

    def parity_votes(self):
        return (0, 0, 0)


@pytest.fixture
def setup(tmp_path):
    from laboratorio.app import create_app

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    app = create_app(settings, catalog_loader=lambda _: TinyData())
    with TestClient(app, base_url="http://localhost:8765") as client:
        yield client


def post(client, path, body):
    return client.post(path, json=body, headers={"Origin": "http://localhost:8765"})


def payload(**changes):
    request = {
        "name": "Tiny backtest",
        "strategy": {
            "name": "Transition",
            "selector": "system",
            "system": "transition",
            "coverage": 1,
            "staking": "flat",
        },
        "game": {"numbers": 10, "positions": 5, "prizes": [80, 8, 4, 2, 1], "min_stake": 1},
        "conditions": {"capital": 10, "goal": 20},
        "inputs": {"history_sha256": HISTORY_SHA256, "rankings_sha256": RANKINGS_SHA256},
    }
    request.update(changes)
    return request


def test_create_report_and_list_persist_configuration(setup):
    created = post(setup, "/api/v1/backtests", payload())
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    report = setup.get(f"/api/v1/backtests/{identifier}").json()
    assert report["config"]["strategy"]["selector"] == "system"
    expected = {
        "reached_goal",
        "completed",
        "goal_rate",
        "quiebres",
        "neto_medio",
        "incomplete",
        "window",
    }
    assert expected <= report.keys()
    assert {"bets", "wagered", "paid", "sessions", "incomplete"} <= report["window"].keys()
    page = setup.get("/api/v1/backtests?offset=0&limit=5").json()
    assert (page["total"], page["offset"], page["limit"]) == (1, 0, 5)
    assert page["items"][0]["id"] == identifier
    assert setup.get("/api/v1/backtests/not-found").status_code == 404


def test_create_rejects_invalid_coverage_hashes_and_prizes(setup):
    bad_coverage = payload(
        strategy={
            "name": "Transition",
            "selector": "system",
            "system": "transition",
            "coverage": 11,
            "staking": "flat",
        }
    )
    assert post(setup, "/api/v1/backtests", bad_coverage).status_code == 422
    bad_hash = payload(inputs={"history_sha256": "0" * 64, "rankings_sha256": RANKINGS_SHA256})
    assert post(setup, "/api/v1/backtests", bad_hash).status_code == 409
    bad_prizes = payload(game={"numbers": 10, "positions": 5, "prizes": [80, 8], "min_stake": 1})
    assert post(setup, "/api/v1/backtests", bad_prizes).status_code == 422


@pytest.mark.golden
@pytest.mark.real_data
def test_api_golden_parity_fifty_flat(setup):
    from laboratorio.engine.adapter import open_lab_data

    settings = Settings.from_environment()
    data = open_lab_data(settings)
    setup.app.state.data = data
    response = post(
        setup,
        "/api/v1/backtests",
        {
            "name": "Parity 50 flat golden",
            "strategy": {"name": "Parity", "selector": "parity", "coverage": 50, "staking": "flat"},
            "game": {"numbers": 100, "positions": 5, "prizes": [80, 8, 4, 2, 1], "min_stake": 1},
            "conditions": {"capital": 2000, "goal": 2800},
            "inputs": {"history_sha256": HISTORY_SHA256, "rankings_sha256": RANKINGS_SHA256},
        },
    )
    assert response.status_code == 201, response.text
    result = setup.get(f"/api/v1/backtests/{response.json()['id']}").json()
    assert (
        result["reached_goal"],
        result["completed"],
        result["goal_rate"],
        result["quiebres"],
        result["neto_medio"],
    ) == (13, 91, 14.3, 78, -1572.8)
