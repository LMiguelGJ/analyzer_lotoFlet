"""S3/S5: result by year of a saved owned-laboratory run, computed when it is read."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.settings import Settings

BASE = "http://localhost:8765"
ORIGIN = {"Origin": BASE, "Content-Type": "application/json"}
LEIDSA = "leidsa_quiniela"
KEYS = {"year", "net", "goals", "ruins", "timeouts", "sessions_closed", "return_pct"}
SUMMARY_KEYS = {
    "eligible_draws",
    "gaps",
    "first",
    "last",
    "session_sha256",
    "session_count",
    "totals",
    "wallet",
}
KNOWN_NETS = {
    2019: 379,
    2020: 394,
    2021: 461,
    2022: 656,
    2023: 425,
    2024: 480,
    2025: 1080,
    2026: 373,
}


@pytest.fixture
def client(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    app = create_app(settings, catalog_loader=lambda _settings: lab_data)
    with TestClient(app, base_url=BASE, raise_server_exceptions=False) as http:
        yield http


def _session(outcome, start, end, balance):
    return {
        "outcome": outcome,
        "start_index": start,
        "end_index": end,
        "draws": end - start + 1,
        "final_balance": balance,
        "wagered": 0,
        "paid": 0,
    }


def _labels(*days):
    return [f"{day} 20:50" for day in days]


# ------------------------------------------------------------------ pure computation


def test_net_goes_to_the_year_where_the_session_closes_and_open_session_to_its_last_draw():
    from laboratorio.engine.yearly_results import results_by_year

    labels = _labels("2023-12-30", "2023-12-31", "2024-01-01", "2024-01-02", "2024-01-03")
    sessions = [
        _session("goal", 0, 2, 110),  # starts in 2023, closes in 2024
        _session("ruin", 3, 3, 0),
        _session("incomplete", 4, 4, 95),  # open: counted in the year of its last draw
    ]
    rows = results_by_year(
        sessions, labels, capital=100, eligible_draws=5, first=labels[0], last=labels[-1]
    )
    assert rows == [
        {
            "year": 2024,
            "net": 10 - 100 - 5,
            "goals": 1,
            "ruins": 1,
            "timeouts": 0,
            "sessions_closed": 2,
            "return_pct": -95.0,
        }
    ]


def test_years_are_ascending_and_timeouts_count_as_closed():
    from laboratorio.engine.yearly_results import results_by_year

    labels = _labels("2022-05-01", "2022-05-02", "2023-02-01", "2023-02-02")
    sessions = [
        _session("goal", 0, 0, 125),
        _session("timeout", 1, 2, 90),
        _session("goal", 3, 3, 110),
    ]
    rows = results_by_year(
        sessions, labels, capital=100, eligible_draws=4, first=labels[0], last=labels[-1]
    )
    assert rows is not None
    assert [row["year"] for row in rows] == [2022, 2023]
    assert all(set(row) == KEYS for row in rows)
    assert rows[0] == {
        "year": 2022,
        "net": 25,
        "goals": 1,
        "ruins": 0,
        "timeouts": 0,
        "sessions_closed": 1,
        "return_pct": 25.0,
    }
    assert rows[1] == {
        "year": 2023,
        "net": 0,
        "goals": 1,
        "ruins": 0,
        "timeouts": 1,
        "sessions_closed": 2,
        "return_pct": 0.0,
    }


def test_return_is_expressed_in_percentage_points_of_the_capital():
    from laboratorio.engine.yearly_results import results_by_year

    labels = _labels("2020-01-01")
    rows = results_by_year(
        [_session("goal", 0, 0, 5379)],
        labels,
        capital=5000,
        eligible_draws=1,
        first=labels[0],
        last=labels[0],
    )
    assert rows is not None
    assert rows[0]["net"] == 379 and rows[0]["return_pct"] == 7.58


@pytest.mark.parametrize(
    "eligible_draws,first,last",
    [(4, "2023-12-30 20:50", "2024-01-03 20:50"), (5, "2023-12-31 20:50", "2024-01-03 20:50")],
)
def test_labels_that_do_not_match_the_stored_run_give_null(eligible_draws, first, last):
    from laboratorio.engine.yearly_results import results_by_year

    labels = _labels("2023-12-30", "2023-12-31", "2024-01-01", "2024-01-02", "2024-01-03")
    sessions = [_session("goal", 0, 4, 110)]
    assert (
        results_by_year(
            sessions, labels, capital=100, eligible_draws=eligible_draws, first=first, last=last
        )
        is None
    )


def test_a_session_past_the_resolved_draws_gives_null():
    from laboratorio.engine.yearly_results import results_by_year

    labels = _labels("2023-12-30", "2023-12-31")
    assert (
        results_by_year(
            [_session("goal", 0, 2, 110)],
            labels,
            capital=100,
            eligible_draws=2,
            first=labels[0],
            last=labels[-1],
        )
        is None
    )


def test_eligible_labels_follow_the_ranked_rows_inside_the_window():
    from laboratorio.engine.yearly_results import eligible_labels

    labels = tuple(_labels("2019-12-31", "2020-01-01", "2020-01-02", "2021-01-01"))
    history = SimpleNamespace(labels=labels)
    rankings = SimpleNamespace(row_ids=np.array([0, 1, 3], dtype=np.int64))
    assert eligible_labels(history, rankings, "2020-01-01 00:00", "2020-12-31 23:59") == [labels[1]]


# ------------------------------------------------------------------------ HTTP / known case


def _activate_leidsa(client):
    response = client.put("/api/v1/lists/active", json={"id": LEIDSA}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return client.get("/api/v1/runs/options").json()["history"]["sha256"]


def _known_lab(client):
    config = {
        "schema_version": 1,
        "system": "freq_recent",
        "coverage": 1,
        "stake_style": "bold",
        "capital": 5000,
        "goal": 5100,
        "prizes": [60, 8, 4],
        "window_start": "2019-01-01 00:00",
        "window_end": "2026-12-31 23:59",
    }
    lab = client.post(
        "/api/v1/laboratories", json={"name": "Por año", "config": config}, headers=ORIGIN
    )
    assert lab.status_code == 201, lab.text
    return lab.json()


def _run(client, lab, sha):
    response = client.post(
        f"/api/v1/laboratories/{lab['id']}/runs",
        json={"required_history_sha256": sha},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _stored_sessions(client, lab, run):
    items = []
    while True:
        page = client.get(
            f"/api/v1/laboratories/{lab['id']}/runs/{run['id']}/sessions"
            f"?offset={len(items)}&limit=500"
        ).json()
        items += [item["summary"] for item in page["items"]]
        if len(items) >= page["total"]:
            return items


def test_known_leidsa_case_gives_the_validated_net_per_year(client):
    sha = _activate_leidsa(client)
    lab = _known_lab(client)
    run = _run(client, lab, sha)
    by_year = run["summary"]["by_year"]
    assert by_year is not None
    assert [row["year"] for row in by_year] == sorted(KNOWN_NETS)
    assert all(set(row) == KEYS for row in by_year)
    nets = {row["year"]: row["net"] for row in by_year}
    # Years 2019 to 2025 are closed; 2026 keeps growing while the history file does.
    assert {year: nets[year] for year in range(2019, 2026)} == {
        year: net for year, net in KNOWN_NETS.items() if year < 2026
    }
    assert sum(nets.values()) == run["summary"]["totals"]["total_net"]
    if run["summary"]["last"] == "2026-11-24 20:50":  # the history the +4248 was validated on
        assert nets == KNOWN_NETS and sum(nets.values()) == 4248
    for row in by_year:
        assert row["return_pct"] == round(row["net"] * 100 / 5000, 2)
        assert row["goals"] + row["ruins"] + row["timeouts"] == row["sessions_closed"]
    # the same figures on every later read, from the sessions actually stored
    stored = client.get(f"/api/v1/laboratories/{lab['id']}/runs/{run['id']}").json()
    assert stored == run
    sessions = _stored_sessions(client, lab, run)
    assert sum(1 for s in sessions if s["outcome"] != "incomplete") == sum(
        row["sessions_closed"] for row in by_year
    )


def test_by_year_is_additive_and_does_not_touch_stored_results(client):
    sha = _activate_leidsa(client)
    lab = _known_lab(client)
    run = _run(client, lab, sha)
    summary = dict(run["summary"])
    assert summary.pop("by_year") is not None
    assert set(summary) == SUMMARY_KEYS
    page = client.get(f"/api/v1/laboratories/{lab['id']}/runs").json()
    assert set(page["items"][0]["summary"]) == {"totals", "eligible_draws", "gaps"}
    sessions = client.get(f"/api/v1/laboratories/{lab['id']}/runs/{run['id']}/sessions").json()
    assert set(sessions["items"][0]["summary"]) == {
        "outcome",
        "start_index",
        "end_index",
        "draws",
        "final_balance",
        "wagered",
        "paid",
    }


def test_history_that_no_longer_matches_the_run_gives_null_without_error(client):
    sha = _activate_leidsa(client)
    lab = _known_lab(client)
    run = _run(client, lab, sha)
    lists = client.app.state.lists
    real = lists.lab_data(LEIDSA)
    changed = replace(real, history=replace(real.history, sha256="f" * 64))
    lists.lab_data = lambda list_id: changed if list_id == LEIDSA else real
    response = client.get(f"/api/v1/laboratories/{lab['id']}/runs/{run['id']}")
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert "by_year" in summary and summary["by_year"] is None
    assert summary["totals"] == run["summary"]["totals"]


def test_unreadable_list_history_gives_null_without_error(client):
    from laboratorio.engine.list_catalog import ListError

    sha = _activate_leidsa(client)
    lab = _known_lab(client)
    run = _run(client, lab, sha)

    def unavailable(_list_id):
        raise ListError("unavailable", "no disponible")

    client.app.state.lists.lab_data = unavailable
    response = client.get(f"/api/v1/laboratories/{lab['id']}/runs/{run['id']}")
    assert response.status_code == 200 and response.json()["summary"]["by_year"] is None


def test_chance_laboratory_keeps_its_payload_and_gets_the_same_additive_field(client):
    options = client.get("/api/v1/laboratories/options").json()
    config = {
        "schema_version": 1,
        "system": "cold",
        "coverage": 1,
        "stake_style": "flat",
        "capital": 100,
        "goal": 110,
        "prizes": options["prizes"],
        "window_start": options["window"]["start"],
        "window_end": options["window"]["start"],
    }
    lab = client.post(
        "/api/v1/laboratories", json={"name": "Chance", "config": config}, headers=ORIGIN
    ).json()
    created = client.post(
        f"/api/v1/laboratories/{lab['id']}/runs",
        json={"required_history_sha256": options["history_sha256"]},
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    run = created.json()
    summary = dict(run["summary"])
    rows = summary.pop("by_year")
    assert set(summary) == SUMMARY_KEYS
    assert rows is not None and sum(row["net"] for row in rows) == summary["totals"]["total_net"]
    assert client.get(f"/api/v1/laboratories/{lab['id']}/runs/{run['id']}").json() == run
