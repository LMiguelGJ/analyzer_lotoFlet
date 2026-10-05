"""All 14 reference scenarios of docs/resumen_resultados_quiniela.md, through the real API."""

import pytest
from fastapi.testclient import TestClient

from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256, Settings

# (system or "parity", coverage, staking, reached, completed, goal_rate, quiebres, neto_medio)
SCENARIOS = [
    ("transition", 1, "bold", 681, 963, 70.7, 282, 10.3),
    ("cold", 1, "bold", 684, 974, 70.2, 290, -3.4),
    ("select_interpretable", 1, "bold", 663, 946, 70.1, 283, -8.2),
    ("mix", 1, "bold", 676, 968, 69.8, 292, -15.6),
    ("ensemble", 5, "bold", 3226, 4720, 68.3, 1494, -51.2),
    ("ensemble", 10, "bold", 6140, 9061, 67.8, 2921, -56.9),
    ("ensemble", 20, "bold", 10785, 16086, 67.0, 5301, -59.2),
    ("cold", 25, "ladder", 677, 1105, 61.3, 428, -162.2),
    ("mix", 50, "bold", 12845, 20605, 62.3, 7760, -117.0),
    ("transition", 50, "bold", 12890, 20682, 62.3, 7792, -116.0),
    ("parity", 50, "bold", 12698, 20404, 62.2, 7706, -120.8),
    ("cold", 50, "ladder", 1429, 3502, 40.8, 2073, -98.7),
    ("parity", 50, "ladder", 1368, 3496, 39.1, 2128, -124.4),
    ("parity", 50, "flat", 13, 91, 14.3, 78, -1572.8),
]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from dataclasses import replace

    from laboratorio.app import create_app

    data_dir = tmp_path_factory.mktemp("golden") / "data"
    settings = replace(Settings.from_environment(), data_dir=data_dir, port=8765)
    with TestClient(create_app(settings), base_url="http://localhost:8765") as test_client:
        yield test_client


def _payload(system, coverage, staking):
    parity = system == "parity"
    return {
        "name": f"golden {system}/{coverage}/{staking}",
        "strategy": {
            "name": system,
            "selector": "parity" if parity else "system",
            "system": None if parity else system,
            "coverage": coverage,
            "staking": staking,
        },
        "game": {"numbers": 100, "positions": 5, "prizes": [80, 8, 4, 2, 1], "min_stake": 1},
        "conditions": {"capital": 2000, "goal": 2800},
        "inputs": {"history_sha256": HISTORY_SHA256, "rankings_sha256": RANKINGS_SHA256},
    }


@pytest.mark.golden
@pytest.mark.real_data
@pytest.mark.parametrize(
    ("system", "coverage", "staking", "reached", "completed", "rate", "quiebres", "neto"),
    SCENARIOS,
    ids=[f"row{i}-{s[0]}-{s[1]}-{s[2]}" for i, s in enumerate(SCENARIOS, start=1)],
)
def test_reference_scenario_matches_summary_table(
    client, system, coverage, staking, reached, completed, rate, quiebres, neto
):
    response = client.post(
        "/api/v1/backtests",
        json=_payload(system, coverage, staking),
        headers={"Origin": "http://localhost:8765"},
    )
    assert response.status_code == 201, response.text
    report = response.json()["report"]
    assert (
        report["reached_goal"],
        report["completed"],
        round(report["goal_rate"], 1),
        report["quiebres"],
        round(report["neto_medio"], 1),
    ) == (reached, completed, rate, quiebres, neto)
