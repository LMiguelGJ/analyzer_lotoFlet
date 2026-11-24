"""The laboratory list carries each laboratory's most recent saved run result (additive)."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.laboratories import initial_laboratory_definitions
from laboratorio.settings import HISTORY_SHA256, Settings
from laboratorio.storage.database import connection

BASE = "http://localhost:8765"
ORIGIN = {"Origin": BASE}
ROOT = "/api/v1/laboratories"
DEFINITION_KEYS = {"schema_version", "id", "name", "reference_id", "config"}


@pytest.fixture
def labs(tmp_path, lab_data):
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
            json={"name": "Con corridas", "config": config.to_mapping()},
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        yield client, app, response.json()


def _run(client, definition):
    response = client.post(
        f"{ROOT}/{definition['id']}/runs",
        json={"required_history_sha256": HISTORY_SHA256},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _item(client, identifier):
    page = client.get(ROOT, params={"limit": 100}).json()
    return next(item for item in page["items"] if item["id"] == identifier)


def _expected(run):
    totals = run["summary"]["totals"]
    return {
        "id": run["id"],
        "created_at": run["created_at"],
        "total_net": totals["total_net"],
        "total_wagered": totals["total_wagered"],
        "total_paid": totals["total_paid"],
    }


def _delete_run(app, run_id):
    with connection(app.state.repo.path) as db, db:
        db.execute("DELETE FROM reference_lab_sessions WHERE run_id=?", (run_id,))
        db.execute("DELETE FROM reference_lab_runs WHERE id=?", (run_id,))


def test_every_item_has_last_run_and_it_is_null_without_runs(labs):
    client, _app, definition = labs
    items = client.get(ROOT, params={"limit": 100}).json()["items"]
    assert items
    assert all("last_run" in item for item in items)
    assert all(item["last_run"] is None for item in items)
    assert _item(client, definition["id"])["last_run"] is None


def test_last_run_is_the_latest_saved_run_with_its_totals(labs):
    client, _app, definition = labs
    first = _run(client, definition)
    assert _item(client, definition["id"])["last_run"] == _expected(first)
    second = _run(client, definition)
    listed = client.get(f"{ROOT}/{definition['id']}/runs").json()["items"]
    newest = second if listed[0]["id"] == second["id"] else first
    last_run = _item(client, definition["id"])["last_run"]
    assert last_run == _expected(newest)
    assert set(last_run) == {"id", "created_at", "total_net", "total_wagered", "total_paid"}
    assert all(type(last_run[key]) is int for key in ("total_net", "total_wagered", "total_paid"))
    # A different laboratory is not affected by this one's runs.
    others = [
        item
        for item in client.get(ROOT, params={"limit": 100}).json()["items"]
        if item["id"] != definition["id"]
    ]
    assert others and all(item["last_run"] is None for item in others)


def test_deleting_the_latest_run_falls_back_to_the_previous_one(labs):
    client, app, definition = labs
    first = _run(client, definition)
    second = _run(client, definition)
    listed = client.get(f"{ROOT}/{definition['id']}/runs").json()["items"]
    latest_id, previous = (
        (second["id"], first) if listed[0]["id"] == second["id"] else (first["id"], second)
    )
    assert _item(client, definition["id"])["last_run"]["id"] == latest_id
    _delete_run(app, latest_id)
    assert _item(client, definition["id"])["last_run"] == _expected(previous)
    _delete_run(app, previous["id"])
    assert _item(client, definition["id"])["last_run"] is None


def test_existing_list_fields_are_unchanged_and_paging_still_applies(labs):
    client, _app, definition = labs
    _run(client, definition)
    page = client.get(ROOT, params={"limit": 3}).json()
    assert set(page) == {"total", "offset", "limit", "items"}
    assert (page["offset"], page["limit"], len(page["items"])) == (0, 3, 3)
    for item in page["items"]:
        assert set(item) == DEFINITION_KEYS | {"last_run"}
    stripped = {key: value for key, value in page["items"][0].items() if key != "last_run"}
    detail = client.get(f"{ROOT}/{page['items'][0]['id']}").json()
    assert stripped == detail["definition"]


def test_list_reads_last_runs_with_a_single_query_for_the_page(labs, monkeypatch):
    client, _app, definition = labs
    _run(client, definition)
    statements = []
    original = connection

    def traced(path):
        from contextlib import contextmanager

        @contextmanager
        def wrapper():
            with original(path) as db:
                db.set_trace_callback(statements.append)
                yield db

        return wrapper()

    monkeypatch.setattr("laboratorio.storage.laboratory_store.connection", traced)
    assert client.get(ROOT, params={"limit": 100}).status_code == 200
    run_reads = [sql for sql in statements if "reference_lab_runs" in sql]
    assert len(run_reads) == 1
