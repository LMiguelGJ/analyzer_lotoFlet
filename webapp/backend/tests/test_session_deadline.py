"""Optional per-session deadline (``max_session_draws``): config, engine, storage and API."""

from dataclasses import asdict, replace
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.laboratories import LaboratoryConfig
from laboratorio.domain.reference_labs import ReferenceLab
from laboratorio.engine.reference_labs import DeadlineReferenceTotals, run_reference_lab
from laboratorio.settings import Settings
from laboratorio.storage.reference_lab_store import _validate_result

BASE = "http://localhost:8765"
ORIGIN = {"Origin": BASE, "Content-Type": "application/json"}
LEIDSA = "leidsa_quiniela"

CHANCE_CONFIG = {
    "schema_version": 1,
    "system": "cold",
    "coverage": 10,
    "stake_style": "flat",
    "capital": 2000,
    "goal": 2800,
    "prizes": [80, 8, 4, 2, 1],
    "window_start": "2025-09-02 05:10",
    "window_end": "2026-09-25 18:20",
}
LEIDSA_CONFIG = {
    **CHANCE_CONFIG,
    "prizes": [60, 8, 4],
    "window_start": "2023-01-04 20:50",
    "window_end": "2026-11-16 20:50",
}

MISS = [1, 91, 92, 93, 94]  # the parity pick for coverage 1 is number 0: never wins
HIT = [0, 91, 92, 93, 94]  # first prize on number 0


# ------------------------------------------------------------------------ config


def test_config_without_the_field_keeps_the_exact_mapping():
    config = LaboratoryConfig.from_mapping(CHANCE_CONFIG)
    assert config.max_session_draws is None
    assert config.to_mapping() == CHANCE_CONFIG
    assert "max_session_draws" not in config.to_mapping()


def test_config_with_the_field_round_trips():
    config = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_session_draws": 30})
    assert config.max_session_draws == 30
    assert config.to_mapping() == {**CHANCE_CONFIG, "max_session_draws": 30}
    assert LaboratoryConfig.from_mapping(config.to_mapping()) == config


def test_explicit_null_means_unlimited_and_is_not_emitted():
    config = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_session_draws": None})
    assert config.max_session_draws is None
    assert config.to_mapping() == CHANCE_CONFIG


@pytest.mark.parametrize("value", [1, 30, 10000])
def test_bounds_are_accepted(value):
    config = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_session_draws": value})
    assert config.max_session_draws == value


@pytest.mark.parametrize("value", [0, -1, 10001, True, False, 1.5, "30", [30]])
def test_invalid_values_are_refused_in_spanish(value):
    with pytest.raises(ValueError, match="máximo de días por sesión"):
        LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_session_draws": value})


def test_leidsa_config_keeps_list_id_and_gains_the_field():
    config = LaboratoryConfig.from_mapping(
        {**LEIDSA_CONFIG, "list_id": LEIDSA, "max_session_draws": 30}
    )
    assert config.to_mapping() == {**LEIDSA_CONFIG, "list_id": LEIDSA, "max_session_draws": 30}


def test_unknown_keys_are_still_refused():
    with pytest.raises(ValueError):
        LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_days": 30})


def test_reference_lab_adapter_carries_the_cap():
    from laboratorio.domain.laboratories import LaboratoryDefinition

    config = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_session_draws": 30})
    definition = LaboratoryDefinition("6f1b0c1e-0b5c-4b57-9a54-0d9c7d6f4a11", "x", config)
    assert definition.to_reference_lab().max_session_draws == 30
    plain = LaboratoryDefinition(
        "6f1b0c1e-0b5c-4b57-9a54-0d9c7d6f4a11", "x", LaboratoryConfig.from_mapping(CHANCE_CONFIG)
    )
    assert plain.to_reference_lab().max_session_draws is None


# ------------------------------------------------------------------------ engine


def replay(rows, **lab_changes):
    base = {
        "lab_id": "synthetic",
        "system": "parity",
        "coverage": 1,
        "stake_style": "flat",
        "selection_kind": "parity",
    }
    lab = ReferenceLab(**(base | lab_changes))
    count = len(rows)
    labels = tuple(f"2025-10-{day + 1:02d} 05:10" for day in range(count))
    history = SimpleNamespace(labels=labels, nums=np.asarray(rows, dtype=np.uint8))
    rankings = SimpleNamespace(row_ids=np.arange(count, dtype=np.int64))
    votes = np.zeros(count, dtype=np.int8)
    return run_reference_lab(lab, history, rankings, parity_votes=votes)


def deadline_totals(result):
    assert isinstance(result.totals, DeadlineReferenceTotals)
    return result.totals


def shape(result):
    return [
        (s.outcome, s.start_index, s.end_index, s.draws, s.final_balance) for s in result.sessions
    ]


def test_a_slow_session_ends_as_timeout_keeping_its_balance_and_the_next_one_restarts():
    result = replay([MISS] * 7, max_session_draws=3)
    assert shape(result) == [
        ("timeout", 0, 2, 3, 1997),
        ("timeout", 3, 5, 3, 1997),
        ("incomplete", 6, 6, 1, 1999),
    ]
    totals = deadline_totals(result)
    assert (totals.timeouts, totals.goals, totals.ruins, totals.incomplete) == (2, 0, 0, 1)
    assert totals.completed == 2 and totals.sessions_total == 3
    assert totals.total_net == -7 and totals.total_steps == 7
    assert totals.mean_net_closed == -3.0
    assert (totals.timeout_net, totals.goal_draws) == (-6, 0)


def test_without_the_cap_the_same_history_is_one_incomplete_session():
    result = replay([MISS] * 7)
    assert shape(result) == [("incomplete", 0, 6, 7, 1993)]
    assert not hasattr(result.totals, "timeouts")


def test_reaching_the_goal_on_the_last_allowed_draw_is_a_goal_not_a_timeout():
    # Two misses then a first-prize hit: 2000 -> 1998 -> 2077 >= 2050 on draw 3.
    result = replay([MISS, MISS, HIT, MISS], goal=2050, max_session_draws=3)
    assert shape(result) == [("goal", 0, 2, 3, 2077), ("incomplete", 3, 3, 1, 1999)]
    totals = deadline_totals(result)
    assert totals.timeouts == 0
    assert totals.goals == 1
    assert (totals.timeout_net, totals.goal_draws) == (0, 3)


def test_a_goal_one_draw_too_late_is_a_timeout():
    result = replay([MISS, MISS, MISS, HIT], goal=2050, max_session_draws=3)
    assert shape(result)[0] == ("timeout", 0, 2, 3, 1997)
    assert shape(result)[1][0] == "goal"  # the hit still wins, but as a fresh session


def test_ruin_before_the_cap_is_unchanged():
    result = replay([MISS] * 5, capital=2, goal=10, max_session_draws=4)
    assert shape(result) == [
        ("ruin", 0, 1, 2, 0),
        ("ruin", 2, 3, 2, 0),
        ("incomplete", 4, 4, 1, 1),
    ]
    assert deadline_totals(result).timeouts == 0 and result.totals.ruins == 2


def test_cap_larger_than_every_session_changes_nothing_but_the_count():
    with_cap = replay([HIT, MISS, MISS], max_session_draws=500)
    without = replay([HIT, MISS, MISS])
    assert shape(with_cap) == shape(without)
    assert with_cap.session_sha256 == without.session_sha256


def test_mapping_omits_timeouts_unless_the_cap_is_set():
    plain = asdict(replay([MISS] * 2))
    assert not {"timeouts", "timeout_net", "goal_draws"} & set(plain["totals"])
    assert plain == asdict(replay([MISS] * 2)) | {"totals": plain["totals"]}
    capped = asdict(replay([MISS] * 2, max_session_draws=2))
    assert capped["totals"]["timeouts"] == 1
    assert capped["totals"]["timeout_net"] == -2 and capped["totals"]["goal_draws"] == 0


# ------------------------------------------------------------------------ storage


def stored_result(rows, **lab_changes):
    return asdict(replay(rows, **lab_changes))


def test_store_accepts_timeouts_only_when_the_lab_has_a_cap():
    result = stored_result([MISS] * 7, max_session_draws=3)
    _validate_result("synthetic", 2000, result, max_session_draws=3)
    with pytest.raises(ValueError):
        _validate_result("synthetic", 2000, result)  # no cap: timeouts are not allowed
    with pytest.raises(ValueError):
        _validate_result("synthetic", 2000, result, max_session_draws=4)  # wrong deadline


def test_store_requires_the_timeout_count_to_match_the_sessions():
    result = stored_result([MISS] * 7, max_session_draws=3)
    result["totals"]["timeouts"] = 1
    with pytest.raises(ValueError):
        _validate_result("synthetic", 2000, result, max_session_draws=3)
    del result["totals"]["timeouts"]
    with pytest.raises(ValueError):
        _validate_result("synthetic", 2000, result, max_session_draws=3)


def test_store_checks_the_deadline_money_and_days_against_the_sessions():
    for key in ("timeout_net", "goal_draws"):
        result = stored_result([MISS] * 7, max_session_draws=3)
        result["totals"][key] += 1
        with pytest.raises(ValueError):
            _validate_result("synthetic", 2000, result, max_session_draws=3)


def test_store_still_validates_plain_results_unchanged():
    result = stored_result([HIT, MISS, MISS], goal=2050)
    assert "timeouts" not in result["totals"]
    _validate_result("synthetic", 2000, result)
    result["totals"]["timeouts"] = 0
    with pytest.raises(ValueError):
        _validate_result("synthetic", 2000, result)


# ------------------------------------------------------------------------ API


@pytest.fixture
def client(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    app = create_app(settings, catalog_loader=lambda _settings: lab_data)
    with TestClient(app, base_url=BASE, raise_server_exceptions=False) as http:
        yield http


def activate_leidsa(client):
    response = client.put("/api/v1/lists/active", json={"id": LEIDSA}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return client.get("/api/v1/runs/options").json()["history"]["sha256"]


def create_lab(client, name, config):
    return client.post(
        "/api/v1/laboratories", json={"name": name, "config": config}, headers=ORIGIN
    )


def run_lab(client, lab, sha):
    return client.post(
        f"/api/v1/laboratories/{lab['id']}/runs",
        json={"required_history_sha256": sha},
        headers=ORIGIN,
    )


def test_api_creates_and_runs_a_leidsa_lab_with_a_deadline(client):
    sha = activate_leidsa(client)
    created = create_lab(client, "con plazo", {**LEIDSA_CONFIG, "max_session_draws": 30})
    assert created.status_code == 201, created.text
    lab = created.json()
    assert lab["config"]["max_session_draws"] == 30
    run = run_lab(client, lab, sha)
    assert run.status_code == 201, run.text
    body = run.json()
    assert body["snapshot"]["definition"]["config"]["max_session_draws"] == 30
    totals = body["summary"]["totals"]
    assert totals["timeouts"] >= 1
    assert totals["completed"] == totals["goals"] + totals["ruins"] + totals["timeouts"]
    sessions = client.get(
        f"/api/v1/laboratories/{lab['id']}/runs/{body['id']}/sessions?limit=500"
    ).json()
    assert sessions["total"] == totals["sessions_total"]
    rows = [item["summary"] for item in sessions["items"]]
    assert all(row["draws"] <= 30 for row in rows)
    assert sum(row["outcome"] == "timeout" for row in rows) == totals["timeouts"]
    assert all(row["draws"] == 30 for row in rows if row["outcome"] == "timeout")
    assert totals["timeout_net"] == sum(
        row["final_balance"] - 2000 for row in rows if row["outcome"] == "timeout"
    )
    assert totals["goal_draws"] == sum(row["draws"] for row in rows if row["outcome"] == "goal")
    assert client.get(f"/api/v1/laboratories/{lab['id']}/runs/{body['id']}").json() == run.json()
    listed = client.get(f"/api/v1/laboratories/{lab['id']}/runs").json()
    assert listed["items"][0]["summary"]["totals"]["timeouts"] == totals["timeouts"]


def test_api_lab_without_the_field_has_no_timeouts_key_anywhere(client):
    sha = activate_leidsa(client)
    created = create_lab(client, "sin plazo", LEIDSA_CONFIG)
    assert created.status_code == 201, created.text
    lab = created.json()
    assert "max_session_draws" not in lab["config"]
    body = run_lab(client, lab, sha).json()
    assert not {"timeouts", "timeout_net", "goal_draws"} & set(body["summary"]["totals"])
    assert "max_session_draws" not in body["snapshot"]["definition"]["config"]


def test_api_null_deadline_is_stored_as_absent(client):
    activate_leidsa(client)
    created = create_lab(client, "nulo", {**LEIDSA_CONFIG, "max_session_draws": None})
    assert created.status_code == 201, created.text
    assert "max_session_draws" not in created.json()["config"]


@pytest.mark.parametrize("value", [0, -5, 10001, 2.5, "30", True])
def test_api_refuses_a_bad_deadline_with_a_spanish_422(client, value):
    activate_leidsa(client)
    before = client.get("/api/v1/laboratories").json()["total"]
    response = create_lab(client, "malo", {**LEIDSA_CONFIG, "max_session_draws": value})
    assert response.status_code == 422, response.text
    assert "máximo de días por sesión" in response.json()["detail"]
    assert client.get("/api/v1/laboratories").json()["total"] == before
