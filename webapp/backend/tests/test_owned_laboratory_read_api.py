import hashlib
import json
import sqlite3
from dataclasses import make_dataclass, replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.laboratories import initial_laboratory_definitions
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.settings import Settings

ROOT = "/api/v1/laboratories"
ORIGIN = {"Origin": "http://localhost:8765"}
RUN_ID = "00000000-0000-4000-8000-000000000002"


def _valid_result(definition, session_count=1):
    sessions = [
        {
            "outcome": "goal",
            "start_index": index,
            "end_index": index,
            "draws": 1,
            "final_balance": definition.config.capital + 10,
            "wagered": 1,
            "paid": 11,
        }
        for index in range(session_count)
    ]
    values = [
        [
            session[key]
            for key in (
                "outcome",
                "start_index",
                "end_index",
                "draws",
                "final_balance",
                "wagered",
                "paid",
            )
        ]
        for session in sessions
    ]
    return {
        "lab_id": definition.id,
        "sessions": sessions,
        "totals": {
            "completed": session_count,
            "incomplete": 0,
            "goals": session_count,
            "ruins": 0,
            "sessions_total": session_count,
            "total_wagered": session_count,
            "total_paid": 11 * session_count,
            "total_net": 10 * session_count,
            "total_steps": session_count,
            "mean_net_closed": 10.0 if session_count else None,
        },
        "eligible_draws": session_count,
        "gaps": 0,
        "first": "draw-1" if session_count else None,
        "last": f"draw-{session_count}" if session_count else None,
        "session_sha256": hashlib.sha256(
            json.dumps(values, separators=(",", ":")).encode()
        ).hexdigest(),
    }


@pytest.fixture
def owned_api(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    app = create_app(settings, catalog_loader=lambda _settings: lab_data)
    with TestClient(app, base_url="http://localhost:8765", raise_server_exceptions=False) as client:
        definition = app.state.repo.create_laboratory_definition(
            "Read API",
            initial_laboratory_definitions()[0].config,
            quota_bytes=10**9,
            quota_explicit=True,
        )
        app.state.repo.create_owned_laboratory_run(
            RUN_ID,
            definition.id,
            OwnedLaboratoryRunSnapshot(definition, "a" * 64, "b" * 64),
            _valid_result(definition),
            quota_bytes=10**9,
            quota_explicit=True,
        )
        yield client, app, definition


def test_public_detail_exposes_certified_wallet_on_cold_and_warm_reads(owned_api):
    client, _app, definition = owned_api
    path = f"{ROOT}/{definition.id}/runs/{RUN_ID}"

    cold = client.get(path)
    warm = client.get(path)

    assert cold.status_code == warm.status_code == 200
    expected = {
        "policy": "retain-gains-top-up-v1",
        "out_of_pocket": definition.config.capital,
        "final_wealth": definition.config.capital + 10,
    }
    assert cold.json()["summary"]["wallet"] == expected
    assert warm.json()["summary"]["wallet"] == expected


def test_post_and_cold_warm_get_preserve_wallet_and_existing_projection(owned_api, monkeypatch):
    client, _app, definition = owned_api
    snapshot = OwnedLaboratoryRunSnapshot(definition, "c" * 64, "d" * 64)
    result = _valid_result(definition)
    result_type = make_dataclass("ExecutionResult", [(key, object) for key in result])
    execution = SimpleNamespace(snapshot=snapshot, result=result_type(**result))
    monkeypatch.setattr(
        "laboratorio.api.laboratory_runs.execute_owned_laboratory",
        lambda *_args: execution,
    )

    created = client.post(
        f"{ROOT}/{definition.id}/runs",
        json={"required_history_sha256": "e" * 64},
        headers=ORIGIN,
    )
    assert created.status_code == 201
    run_id = created.json()["id"]
    path = f"{ROOT}/{definition.id}/runs/{run_id}"
    cold = client.get(path)
    warm = client.get(path)

    expected_wallet = {
        "policy": "retain-gains-top-up-v1",
        "out_of_pocket": definition.config.capital,
        "final_wealth": definition.config.capital + 10,
    }
    assert cold.status_code == warm.status_code == 200
    assert created.json()["summary"]["wallet"] == expected_wallet
    assert cold.json()["summary"]["wallet"] == warm.json()["summary"]["wallet"]
    assert cold.json() == warm.json()
    assert created.json()["snapshot"] == snapshot.to_mapping()
    for key in (
        "eligible_draws",
        "gaps",
        "first",
        "last",
        "session_sha256",
        "session_count",
        "totals",
    ):
        assert created.json()["summary"][key] == cold.json()["summary"][key]
    assert created.json()["summary"]["session_sha256"] == result["session_sha256"]
    assert created.json()["summary"]["totals"] == result["totals"]


def test_public_get_preserves_owner_errors_and_does_not_change_storage_or_quota(owned_api):
    client, app, definition = owned_api
    other = app.state.repo.create_laboratory_definition(
        "Other owner", definition.config, quota_bytes=10**9, quota_explicit=True
    )
    detail_path = f"{ROOT}/{definition.id}/runs/{RUN_ID}"
    quota_before = app.state.repo.quota_status(quota_bytes=10**9, quota_explicit=True)
    counts_before = app.state.repo.get_laboratory_owned_counts(definition.id)
    from laboratorio.storage.database import connection

    with connection(app.state.repo.path) as db:
        runs_before = db.execute(
            "SELECT id,metadata_json,result_json FROM reference_lab_runs ORDER BY id"
        ).fetchall()
        sessions_before = db.execute(
            "SELECT run_id,ordinal,session_json FROM reference_lab_sessions ORDER BY run_id,ordinal"
        ).fetchall()

    wrong_owner = client.get(f"{ROOT}/{other.id}/runs/{RUN_ID}")
    assert wrong_owner.status_code == 404
    assert wrong_owner.json()["detail"] == "La corrida no existe."
    response = client.get(detail_path)
    assert response.status_code == 200

    with connection(app.state.repo.path) as db:
        assert (
            db.execute(
                "SELECT id,metadata_json,result_json FROM reference_lab_runs ORDER BY id"
            ).fetchall()
            == runs_before
        )
        assert (
            db.execute(
                "SELECT run_id,ordinal,session_json FROM reference_lab_sessions ORDER BY run_id,ordinal"
            ).fetchall()
            == sessions_before
        )
    assert app.state.repo.quota_status(quota_bytes=10**9, quota_explicit=True) == quota_before
    assert app.state.repo.get_laboratory_owned_counts(definition.id) == counts_before
    assert response.json()["summary"]["session_count"] == 1


def test_wallet_is_independent_of_paged_session_visibility(owned_api):
    client, app, definition = owned_api
    run_id = "00000000-0000-4000-8000-000000000099"
    snapshot = OwnedLaboratoryRunSnapshot(definition, "f" * 64, "0" * 64)
    app.state.repo.create_owned_laboratory_run(
        run_id,
        definition.id,
        snapshot,
        _valid_result(definition, session_count=51),
        quota_bytes=10**9,
        quota_explicit=True,
    )
    detail_path = f"{ROOT}/{definition.id}/runs/{run_id}"
    detail_before = client.get(detail_path)
    first_page = client.get(f"{detail_path}/sessions?offset=0&limit=50")
    last_page = client.get(f"{detail_path}/sessions?offset=50&limit=50")
    detail_after = client.get(detail_path)

    assert detail_before.status_code == detail_after.status_code == 200
    assert first_page.status_code == last_page.status_code == 200
    assert len(first_page.json()["items"]) == 50
    assert len(last_page.json()["items"]) == 1
    assert detail_before.json()["summary"]["wallet"] == {
        "policy": "retain-gains-top-up-v1",
        "out_of_pocket": definition.config.capital,
        "final_wealth": definition.config.capital + 510,
    }
    assert detail_after.json()["summary"]["wallet"] == detail_before.json()["summary"]["wallet"]


def test_corrupt_public_detail_keeps_existing_409_message(owned_api):
    client, app, definition = owned_api
    from laboratorio.storage.database import connection

    with connection(app.state.repo.path) as db:
        db.execute("UPDATE reference_lab_runs SET result_json='broken' WHERE id=?", (RUN_ID,))
        db.commit()

    response = client.get(f"{ROOT}/{definition.id}/runs/{RUN_ID}")
    assert response.status_code == 409
    assert response.json()["detail"] == "Una corrida guardada está dañada y no se puede mostrar."


def test_warm_public_list_and_sessions_do_not_fetch_full_result_rows(owned_api, monkeypatch):
    client, _app, definition = owned_api
    traces = []
    connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        db = connect(*args, **kwargs)
        db.set_trace_callback(traces.append)
        return db

    monkeypatch.setattr(sqlite3, "connect", traced_connect)
    path = f"{ROOT}/{definition.id}/runs"
    cold = client.get(path)
    assert cold.status_code == 200
    traces.clear()
    warm = client.get(path)
    assert warm.status_code == 200 and warm.json() == cold.json()
    assert not any("SELECT" in sql.upper() and "RESULT_JSON" in sql.upper() for sql in traces)

    # Detail warms the same certificate; sessions must issue an ordinal-bounded query.
    client.get(f"{path}/{RUN_ID}")
    traces.clear()
    sessions = client.get(f"{path}/{RUN_ID}/sessions?offset=0&limit=1")
    assert sessions.status_code == 200
    reads = [sql.upper() for sql in traces if "REFERENCE_LAB_SESSIONS" in sql.upper()]
    assert any("LIMIT 1 OFFSET 0" in sql for sql in reads)
    assert not any("RESULT_JSON" in sql for sql in traces)
