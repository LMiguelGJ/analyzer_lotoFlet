import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.laboratories import initial_laboratory_definitions
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.settings import Settings

ROOT = "/api/v1/laboratories"
RUN_ID = "00000000-0000-4000-8000-000000000002"


def _valid_result(definition):
    session = {
        "outcome": "goal",
        "start_index": 0,
        "end_index": 0,
        "draws": 1,
        "final_balance": definition.config.capital + 10,
        "wagered": 1,
        "paid": 11,
    }
    values = [
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
    return {
        "lab_id": definition.id,
        "sessions": [session],
        "totals": {
            "completed": 1,
            "incomplete": 0,
            "goals": 1,
            "ruins": 0,
            "sessions_total": 1,
            "total_wagered": 1,
            "total_paid": 11,
            "total_net": 10,
            "total_steps": 1,
            "mean_net_closed": 10.0,
        },
        "eligible_draws": 1,
        "gaps": 0,
        "first": "draw-1",
        "last": "draw-1",
        "session_sha256": hashlib.sha256(
            json.dumps([values], separators=(",", ":")).encode()
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
