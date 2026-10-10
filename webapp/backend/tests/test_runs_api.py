import json
from dataclasses import asdict, replace

from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.contracts import SYSTEMS
from laboratorio.domain.runs import RunConfig, run_sessions
from laboratorio.engine.run_data import RunStrategy, RunWindow, build_run_rows
from laboratorio.settings import Settings

BASE_URL = "http://localhost:8765"
ORIGIN = {"Origin": BASE_URL, "Content-Type": "application/json"}


def make_app(tmp_path, lab_data, *, quota_bytes=None):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    if quota_bytes is not None:
        settings = replace(settings, quota_bytes=quota_bytes, quota_explicit=True)
    return create_app(settings, catalog_loader=lambda _settings: lab_data)


def payload(**updates):
    body = {
        "name": None,
        "rules": {"positions": 3, "prizes": [60, 10, 5], "minimum_stake": 1},
        "strategy": {
            "kind": "mix",
            "components": [
                {"system": "transition", "percent": 60},
                {"system": "cold", "percent": 40},
            ],
            "coverage": 10,
        },
        "conditions": {"capital": 2000, "goal": 2800, "max_draws": 12},
        "window": {"start_date": "2025-09-02", "end_date": "2025-09-02"},
        "history_sha256": None,
    }
    body.update(updates)
    return body


def create(client, body=None):
    response = client.post("/api/v1/runs", json=body or payload(), headers=ORIGIN)
    assert response.status_code == 201, response.text
    return response.json()


def test_options_route_is_registered_before_run_identifier_and_matches_history(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        history = client.get("/api/v1/history").json()["active"]
        response = client.get("/api/v1/runs/options")

    assert response.status_code == 200
    options = response.json()
    assert options["history"] == history
    assert options["systems"] == [{"id": key, "label": label} for key, label in SYSTEMS.items()]
    assert options["defaults"] == {
        "name": None,
        "rules": {"positions": 3, "prizes": [60, 10, 5], "minimum_stake": 1},
        "strategy": {
            "kind": "mix",
            "components": [
                {"system": "transition", "percent": 60},
                {"system": "cold", "percent": 40},
            ],
            "coverage": 10,
        },
        "conditions": {"capital": 2000, "goal": 2800, "max_draws": None},
        "window": {"start_date": None, "end_date": None},
        "history_sha256": None,
    }
    assert options["limits"] == {
        "coverage": {"min": 1, "max": 50},
        "positions": {"min": 1, "max": 5},
        "name": 80,
        "detail": {"sessions": 50000, "bets": 250000, "bytes": 33554432},
    }


def test_default_mix_three_positions_matches_direct_engine_totals(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        report = create(client, payload(window={"start_date": None, "end_date": None}))
        storage = client.get("/api/v1/settings").json()["storage"]
        assert int(storage["run_artifact_bytes_exact"]) > 0
        catalog = app.state.history
        strategy = RunStrategy("mix", (("transition", 60), ("cold", 40)), 10)
        rows = build_run_rows(
            catalog.active().source,
            catalog._lab.rankings,
            strategy,
            RunWindow(None, None),
            parity_votes=None,
            ranked_only=False,
            cache={},
        )
        direct = run_sessions(RunConfig(2000, 2800, 10, 3, (60, 10, 5), 1, 12), rows.rows)

    assert report["summary"]["totals"] == asdict(direct.totals)
    assert report["config"]["rules"] == {
        "positions": 3,
        "prizes": [60, 10, 5],
        "minimum_stake": 1,
    }
    assert report["config"]["strategy"]["components"] == [
        {"system": "transition", "percent": 60},
        {"system": "cold", "percent": 40},
    ]
    assert report["config"]["conditions"]["max_draws"] == 12


def test_parity_windows_repeat_and_distinct_ids(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        body = payload(
            strategy={"kind": "parity", "components": [], "coverage": 10},
            window={"start_date": "2025-09-02", "end_date": "2025-09-02"},
        )
        first = create(client, body)
        second = create(client, body)
        later = create(
            client,
            payload(
                strategy={"kind": "parity", "components": [], "coverage": 10},
                window={"start_date": "2025-09-03", "end_date": "2025-09-03"},
            ),
        )

    assert first["id"] != second["id"]
    assert first["summary"]["totals"] == second["summary"]["totals"]
    assert later["id"] != first["id"]
    assert later["config"]["window"]["start_date"] == "2025-09-03"


def test_listing_detail_sessions_bets_paging_delete_and_missing_resources(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        report = create(client)
        run_id = report["id"]
        listing = client.get("/api/v1/runs?offset=0&limit=1").json()
        assert listing["total"] == 1
        assert listing["items"] == [report]
        assert client.get(f"/api/v1/runs/{run_id}").json() == report

        first_page = client.get(f"/api/v1/runs/{run_id}/sessions?limit=2").json()
        second_page = client.get(f"/api/v1/runs/{run_id}/sessions?offset=2&limit=2").json()
        assert first_page["total"] == report["summary"]["totals"]["sessions"]
        assert len(first_page["items"]) <= 2
        assert not (
            {item["ordinal"] for item in first_page["items"]}
            & {item["ordinal"] for item in second_page["items"]}
        )
        limited = client.get(f"/api/v1/runs/{run_id}/sessions?outcome=limit&limit=2").json()
        assert all(item["outcome"] == "limit" for item in limited["items"])

        ordinal = first_page["items"][0]["ordinal"]
        bets = client.get(f"/api/v1/runs/{run_id}/sessions/{ordinal}/bets?offset=0&limit=1").json()
        assert bets["session"]["ordinal"] == ordinal
        assert len(bets["items"]) <= 1
        if bets["detail_available"] and bets["total"] > 1:
            next_page = client.get(
                f"/api/v1/runs/{run_id}/sessions/{ordinal}/bets?offset=1&limit=1"
            ).json()
            assert next_page["items"][0]["index"] == bets["items"][0]["index"] + 1

        assert client.get(f"/api/v1/runs/{run_id}/sessions/0/bets").status_code == 422
        assert client.get(f"/api/v1/runs/{run_id}/sessions?limit=201").status_code == 422
        assert client.get("/api/v1/runs?limit=101").status_code == 422
        assert client.get(f"/api/v1/runs/{run_id}/sessions/999999/bets").status_code == 404
        assert client.delete(f"/api/v1/runs/{run_id}", headers=ORIGIN).status_code == 204
        assert client.get(f"/api/v1/runs/{run_id}").status_code == 404
        assert client.get(f"/api/v1/runs/{run_id}/sessions").status_code == 404
        assert client.delete(f"/api/v1/runs/{run_id}", headers=ORIGIN).status_code == 404


def test_run_persists_across_app_restart_and_pins_selected_history(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        frozen_sha = client.get("/api/v1/history").json()["active"]["sha256"]
        imported = client.post(
            "/api/v1/history",
            json={
                "sorteos_por_fecha": {
                    "2026-09-26": [{"hora": "10:00", "numeros": ["01", "02", "03", "04", "05"]}]
                }
            },
            headers=ORIGIN,
        )
        assert imported.status_code == 201, imported.text
        report = create(client, payload(history_sha256=frozen_sha))

    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as restarted:
        assert restarted.get(f"/api/v1/runs/{report['id']}").json() == report
        assert restarted.get("/api/v1/runs").json()["items"] == [report]
        active_sha = imported.json()["active"]["sha256"]
        assert restarted.get("/api/v1/runs/options").json()["history"]["sha256"] == active_sha
        assert report["config"]["history"]["sha256"] == frozen_sha


def test_strict_nested_body_types_and_unknown_fields(tmp_path, lab_data):
    invalid = []
    for path, value in [
        ((), {"unexpected": 1}),
        (("rules",), {"extra": 1}),
        (("strategy",), {"extra": 1}),
        (("conditions",), {"extra": 1}),
        (("window",), {"extra": 1}),
        (("strategy", "components", 0), {"extra": 1}),
    ]:
        body = payload()
        target = body
        for part in path:
            target = target[part]
        target.update(value)
        invalid.append(body)
    for path, value in [
        (("rules", "positions"), True),
        (("rules", "positions"), "3"),
        (("rules", "positions"), 3.0),
        (("rules", "prizes"), [60, "10", 5]),
        (("rules", "minimum_stake"), False),
        (("strategy", "coverage"), 10.0),
        (("strategy", "components", 0, "percent"), "60"),
        (("conditions", "capital"), True),
        (("conditions", "max_draws"), 1.5),
        (("window", "start_date"), 20250902),
        (("history_sha256",), "invalid"),
    ]:
        body = payload()
        target = body
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        invalid.append(body)

    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        for body in invalid:
            response = client.post("/api/v1/runs", json=body, headers=ORIGIN)
            assert response.status_code == 422, (body, response.text)


def test_semantic_errors_unknown_history_quota_and_corrupt_report(tmp_path, lab_data):
    from laboratorio.storage.database import connection

    app = make_app(tmp_path / "normal", lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        bad_goal = payload(conditions={"capital": 2000, "goal": 2000, "max_draws": 12})
        assert client.post("/api/v1/runs", json=bad_goal, headers=ORIGIN).status_code == 422
        missing_history = payload(history_sha256="a" * 64)
        assert client.post("/api/v1/runs", json=missing_history, headers=ORIGIN).status_code == 404
        report = create(client)
        with connection(app.state.repo.path) as db:
            db.execute("UPDATE saved_runs SET summary_json=? WHERE id=?", ("{}", report["id"]))
            db.commit()
        assert client.get(f"/api/v1/runs/{report['id']}").status_code == 409

    tiny_app = make_app(tmp_path / "tiny", lab_data, quota_bytes=1)
    with TestClient(tiny_app, base_url=BASE_URL) as client:
        response = client.post("/api/v1/runs", json=payload(), headers=ORIGIN)
        assert response.status_code == 409
        assert "cuota" in response.json()["detail"]


def test_unavailable_detail_returns_empty_page_without_fabricating_bets(tmp_path, lab_data):
    from laboratorio.storage.database import connection

    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        report = create(client)
        with connection(app.state.repo.path) as db:
            row = db.execute(
                "SELECT summary_json FROM saved_runs WHERE id=?", (report["id"],)
            ).fetchone()
            summary = json.loads(row[0])
            summary["detail"]["status"] = "partial"
            summary["detail"]["stored_bets"] = 0
            db.execute(
                "UPDATE saved_run_sessions SET bets_json=NULL WHERE run_id=?", (report["id"],)
            )
            db.execute(
                "UPDATE saved_runs SET summary_json=? WHERE id=?",
                (json.dumps(summary), report["id"]),
            )
            db.commit()

        session = client.get(f"/api/v1/runs/{report['id']}/sessions?limit=1").json()["items"][0]
        assert session["detail_available"] is False
        bet_response = client.get(f"/api/v1/runs/{report['id']}/sessions/{session['ordinal']}/bets")
        assert bet_response.status_code == 200
        bets = bet_response.json()
        assert bets["detail_available"] is False
        assert bets["items"] == []


def test_local_origin_policy_and_request_size_limit(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert client.post("/api/v1/runs", json=payload()).status_code == 403
        assert (
            client.post(
                "/api/v1/runs", json=payload(), headers={**ORIGIN, "Host": "example.com"}
            ).status_code
            == 403
        )
        too_large = client.post(
            "/api/v1/runs",
            content=b"{}",
            headers={**ORIGIN, "Content-Length": str(64 * 1024 + 1)},
        )
        assert too_large.status_code == 413
        streamed = client.post(
            "/api/v1/runs", content=iter((b"x" * (64 * 1024 + 1),)), headers=ORIGIN
        )
        assert streamed.status_code == 413
        storage = client.get("/api/v1/settings").json()["storage"]
        assert storage["run_artifact_bytes"] == 0
        assert storage["run_artifact_bytes_exact"] == "0"


def test_session_and_bet_page_defaults_and_limits_match_repository(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    failures = []
    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as client:
        report = create(client)
        run_id = report["id"]
        session_page = client.get(f"/api/v1/runs/{run_id}/sessions?limit=1").json()
        ordinal = session_page["items"][0]["ordinal"]
        session_path = f"/api/v1/runs/{run_id}/sessions"
        bets_path = f"{session_path}/{ordinal}/bets"

        default_sessions = client.get(f"/api/v1/runs/{run_id}/sessions")
        default_bets = client.get(bets_path)
        if default_sessions.json()["limit"] != 50:
            failures.append("sessions default must be 50")
        if default_bets.json()["limit"] != 20:
            failures.append("bets default must be 20")
        for path in (session_path, bets_path):
            accepted = client.get(f"{path}?limit=100")
            if accepted.status_code != 200:
                failures.append(f"{path} must accept limit=100, got {accepted.status_code}")
            for limit in (101, 200, 0, -1):
                rejected = client.get(f"{path}?limit={limit}")
                if rejected.status_code != 422:
                    failures.append(
                        f"{path} limit={limit} must be rejected with 422, "
                        f"got {rejected.status_code}"
                    )

    assert not failures, "; ".join(failures)
