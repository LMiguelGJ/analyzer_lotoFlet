import importlib
import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.laboratories import LaboratoryDefinition, initial_laboratory_definitions
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256, Settings

BASE = "http://localhost:8765"
ORIGIN = {"Origin": BASE}
ROOT = "/api/v1/laboratories"


@pytest.fixture
def owned_http(tmp_path, lab_data):
    config = initial_laboratory_definitions()[0].config
    label = next(
        lab_data.history.labels[int(index)]
        for index in lab_data.rankings.row_ids
        if config.window_start <= lab_data.history.labels[int(index)] <= config.window_end
    )
    config = replace(config, window_start=label, window_end=label)
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    app = create_app(settings, catalog_loader=lambda _: lab_data)
    with TestClient(app, base_url=BASE, raise_server_exceptions=False) as client:
        response = client.post(
            ROOT,
            json={"name": "Manual HTTP execution", "config": config.to_mapping()},
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        yield client, app, response.json()


def _post(client, definition, **kwargs):
    return client.post(
        f"{ROOT}/{definition['id']}/runs",
        json={"required_history_sha256": HISTORY_SHA256},
        headers=ORIGIN,
        **kwargs,
    )


def _counts(client, identifier):
    response = client.get(f"{ROOT}/{identifier}")
    assert response.status_code == 200
    body = response.json()
    return body["owned_run_count"], body["owned_session_count"]


def test_owned_post_executes_manual_uuid_config_and_returns_bounded_retrievable_snapshot(
    owned_http,
):
    client, _app, definition = owned_http
    assert definition["reference_id"] is None
    assert _counts(client, definition["id"]) == (0, 0)
    response = _post(client, definition)
    assert response.status_code == 201, response.text
    run = response.json()
    assert set(run) == {
        "id",
        "owner_laboratory_id",
        "lab_id",
        "contract_version",
        "created_at",
        "snapshot",
        "summary",
        "capabilities",
    }
    assert str(uuid.UUID(run["id"])) == run["id"]
    assert uuid.UUID(run["id"]).version == 4
    assert run["owner_laboratory_id"] == run["lab_id"] == definition["id"]
    assert (
        run["snapshot"]
        == OwnedLaboratoryRunSnapshot(
            LaboratoryDefinition.from_mapping(definition), HISTORY_SHA256, RANKINGS_SHA256
        ).to_mapping()
    )
    assert run["contract_version"] == 1 and run["created_at"].endswith("Z")
    assert run["capabilities"] == {"session_summary": True, "per_bet_trace": False}
    summary = run["summary"]
    assert summary["eligible_draws"] == summary["session_count"] == 1
    assert summary["gaps"] == 0
    assert summary["first"] == summary["last"] == definition["config"]["window_start"]
    assert len(summary["session_sha256"]) == 64
    assert _counts(client, definition["id"]) == (1, 1)
    path = f"{ROOT}/{definition['id']}/runs"
    assert client.get(f"{path}/{run['id']}").json() == run
    page = client.get(path)
    assert page.status_code == 200
    assert page.json() == {
        "total": 1,
        "offset": 0,
        "limit": 20,
        "items": [
            {
                **{
                    key: run[key]
                    for key in (
                        "id",
                        "owner_laboratory_id",
                        "lab_id",
                        "contract_version",
                        "created_at",
                    )
                },
                "summary": {key: summary[key] for key in ("eligible_draws", "gaps", "totals")},
            }
        ],
    }
    sessions = client.get(f"{path}/{run['id']}/sessions")
    assert sessions.status_code == 200
    body = sessions.json()
    assert set(body) == {"run_id", "total", "offset", "limit", "items"}
    assert (body["run_id"], body["total"], body["offset"], body["limit"]) == (run["id"], 1, 0, 50)
    assert [item["ordinal"] for item in body["items"]] == [0]
    assert set(body["items"][0]) == {"ordinal", "summary"}
    assert "sessions" not in run and "result" not in run
    assert client.get(f"{path}/{run['id']}/sessions?offset=1&limit=100").json() == {
        "run_id": run["id"],
        "total": 1,
        "offset": 1,
        "limit": 100,
        "items": [],
    }
    other = client.post(
        ROOT, json={"name": "Other HTTP owner", "config": definition["config"]}, headers=ORIGIN
    ).json()
    assert client.get(f"{ROOT}/{other['id']}/runs").json()["total"] == 0
    assert client.get(f"{ROOT}/{other['id']}/runs/{run['id']}").status_code == 404
    assert client.get(f"{ROOT}/{other['id']}/runs/{run['id']}/sessions").status_code == 404
    assert client.get(f"{path}/not-a-uuid").status_code == 404


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({}, 422),
        ({"required_history_sha256": False}, 422),
        ({"required_history_sha256": "A" * 64}, 422),
        ({"required_history_sha256": "a" * 64}, 409),
        ({"required_history_sha256": HISTORY_SHA256, "extra": 1}, 422),
    ],
)
def test_owned_post_rejects_invalid_or_conflicting_body_without_changing_counts(
    owned_http, body, status
):
    client, _app, definition = owned_http
    before = _counts(client, definition["id"])
    response = client.post(f"{ROOT}/{definition['id']}/runs", json=body, headers=ORIGIN)
    assert response.status_code == status, response.text
    assert _counts(client, definition["id"]) == before
    assert client.get(f"{ROOT}/{definition['id']}/runs").json()["total"] == 0


@pytest.mark.parametrize("failure", ["quota", "replay", "deleted", "source"])
def test_owned_execution_failure_saves_no_partial_run(owned_http, monkeypatch, failure):
    client, app, definition = owned_http
    api = importlib.import_module("laboratorio.api.laboratory_runs")
    if failure == "quota":
        app.state.settings = replace(app.state.settings, quota_bytes=1, quota_explicit=True)
        status = 409
    elif failure == "source":
        app.state.data = replace(
            app.state.data, history=replace(app.state.data.history, sha256="a" * 64)
        )
        status = 409
    else:
        original = api.execute_owned_laboratory

        def injected(*args):
            if failure == "replay":
                raise RuntimeError("controlled replay failure")
            execution = original(*args)
            app.state.repo.delete_laboratory_definition(definition["id"], confirmed_run_count=0)
            return execution

        monkeypatch.setattr(api, "execute_owned_laboratory", injected)
        status = 500 if failure == "replay" else 409
    response = _post(client, definition)
    assert response.status_code == status, response.text
    if failure == "deleted":
        assert client.get(f"{ROOT}/{definition['id']}").status_code == 404
        assert app.state.repo.list_owned_laboratory_runs(definition["id"])["total"] == 0
    else:
        assert _counts(client, definition["id"]) == (0, 0)
        assert client.get(f"{ROOT}/{definition['id']}/runs").json()["total"] == 0


@pytest.mark.parametrize(
    "suffix", ["?limit=0", "?limit=101", "?offset=-1", "?offset=9223372036854775808"]
)
def test_owned_list_rejects_out_of_range_paging_without_writes(owned_http, suffix):
    client, _app, definition = owned_http
    response = client.get(f"{ROOT}/{definition['id']}/runs{suffix}")
    assert response.status_code == 422
    assert _counts(client, definition["id"]) == (0, 0)


@pytest.mark.parametrize(
    "legacy", ["/api/v1/runs", "/api/v1/reference-labs/transicion_1_audaz/runs", ROOT]
)
def test_owned_and_existing_posts_preserve_body_and_origin_guards(owned_http, legacy):
    client, _app, definition = owned_http
    owned = f"{ROOT}/{definition['id']}/runs"
    for path in (owned, legacy):
        response = client.post(path, content=b"x" * (64 * 1024 + 1), headers=ORIGIN)
        assert response.status_code == 413, response.text
        assert response.json() == {"detail": "La solicitud supera el límite de 64 KiB."}
    assert client.post(owned, json={"required_history_sha256": HISTORY_SHA256}).status_code == 403
    assert (
        client.post(
            owned,
            json={"required_history_sha256": HISTORY_SHA256},
            headers={"Origin": "https://outside.invalid"},
        ).status_code
        == 403
    )
    assert _counts(client, definition["id"]) == (0, 0)
