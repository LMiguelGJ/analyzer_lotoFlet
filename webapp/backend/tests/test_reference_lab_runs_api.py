"""HTTP contract for persisted reference-laboratory runs (create, read, page, delete).

Known limitation, disclosed on purpose: a corrupt stored record cannot be scoped or read, so
DELETE answers a controlled 409 instead of bypassing validation with a new low-level query.
Locking only coordinates callers inside one process; it is not a distributed guarantee.
"""

import asyncio
import json
import logging
import threading
import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from laboratorio.api import reference_labs as ref_api
from laboratorio.app import create_app
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256, Settings
from laboratorio.storage.database import connection
from laboratorio.storage.reference_lab_store import ReferenceLabStoreError

BASE_URL = "http://localhost:8765"
ORIGIN = {"Origin": BASE_URL, "Content-Type": "application/json"}
LAB = "transicion_1_audaz"
OTHER_LAB = "frios_1_audaz"
ROOT = "/api/v1/reference-labs"
SUMMARY_KEYS = {
    "eligible_draws",
    "gaps",
    "first",
    "last",
    "session_sha256",
    "session_count",
    "totals",
}
TOTAL_KEYS = {
    "completed",
    "incomplete",
    "goals",
    "ruins",
    "sessions_total",
    "total_wagered",
    "total_paid",
    "total_net",
    "total_steps",
    "mean_net_closed",
}
WRONG_SHA = "a" * 64


def make_app(tmp_path, lab_data, *, quota_bytes=None):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    if quota_bytes is not None:
        settings = replace(settings, quota_bytes=quota_bytes, quota_explicit=True)
    return create_app(settings, catalog_loader=lambda _settings: lab_data)


def create(client, lab_id=LAB, sha=HISTORY_SHA256):
    return client.post(
        f"{ROOT}/{lab_id}/runs", json={"required_history_sha256": sha}, headers=ORIGIN
    )


def counts(app):
    with connection(app.state.repo.path) as db:
        return (
            db.execute("SELECT count(*) FROM reference_lab_runs").fetchone()[0],
            db.execute("SELECT count(*) FROM reference_lab_sessions").fetchone()[0],
        )


def keys_anywhere(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys_anywhere(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys_anywhere(item)


@pytest.fixture(scope="module")
def served(tmp_path_factory, lab_data):
    app = make_app(tmp_path_factory.mktemp("served"), lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        response = create(client)
        assert response.status_code == 201, response.text
        yield client, app, response.json()


def test_post_returns_bounded_metadata_without_sessions_and_get_matches(served):
    client, _app, created = served
    assert set(created) == {
        "id",
        "lab_id",
        "contract_version",
        "created_at",
        "config",
        "provenance",
        "summary",
        "capabilities",
    }
    assert str(uuid.UUID(created["id"])) == created["id"]
    assert created["lab_id"] == LAB
    assert created["contract_version"] == 1
    assert created["created_at"].endswith("Z")
    assert created["capabilities"] == {"session_summary": True, "per_bet_trace": False}
    assert created["provenance"] == {
        "history_sha256": HISTORY_SHA256,
        "history_origin": "frozen",
        "rankings_sha256": RANKINGS_SHA256,
    }
    catalog = {item["lab_id"]: item for item in client.get(ROOT).json()["items"]}
    assert created["config"] == catalog[LAB]
    assert created["config"]["capital"] == 2000
    assert created["config"]["prizes"] == [80, 8, 4, 2, 1]
    assert set(created["summary"]) == SUMMARY_KEYS
    assert set(created["summary"]["totals"]) == TOTAL_KEYS
    assert created["summary"]["session_count"] == created["summary"]["totals"]["sessions_total"]
    assert "sessions" not in set(keys_anywhere(created))
    detail = client.get(f"{ROOT}/{LAB}/runs/{created['id']}")
    assert detail.status_code == 200
    assert detail.json() == created
    assert "sessions" not in set(keys_anywhere(detail.json()))


def test_list_is_thin_scoped_and_ordered(served):
    client, _app, created = served
    listing = client.get(f"{ROOT}/{LAB}/runs")
    assert listing.status_code == 200
    body = listing.json()
    assert set(body) == {"total", "offset", "limit", "items"}
    assert (body["offset"], body["limit"]) == (0, 20)
    item = next(row for row in body["items"] if row["id"] == created["id"])
    assert set(item) == {"id", "lab_id", "contract_version", "created_at", "summary"}
    assert set(item["summary"]) == {"eligible_draws", "gaps", "totals"}
    assert len(item["summary"]["totals"]) == 10
    assert item["summary"]["totals"] == created["summary"]["totals"]
    forbidden = {"config", "provenance", "sessions", "result"}
    assert not forbidden & set(keys_anywhere(body))
    assert client.get(f"{ROOT}/{OTHER_LAB}/runs").json()["total"] == 0


def test_sessions_default_page_is_stable_and_ordinal_ordered(served):
    client, _app, created = served
    base = f"{ROOT}/{LAB}/runs/{created['id']}/sessions"
    page = client.get(base).json()
    assert set(page) == {"run_id", "total", "offset", "limit", "items"}
    assert page["run_id"] == created["id"]
    assert (page["offset"], page["limit"]) == (0, 50)
    assert page["total"] == created["summary"]["session_count"]
    assert [row["ordinal"] for row in page["items"]] == list(range(50))
    assert set(page["items"][0]) == {"ordinal", "summary"}
    assert client.get(base).json() == page
    big = client.get(base, params={"limit": 100}).json()
    assert [row["ordinal"] for row in big["items"]] == list(range(100))
    tail = client.get(base, params={"offset": page["total"] - 1, "limit": 100}).json()
    assert [row["ordinal"] for row in tail["items"]] == [page["total"] - 1]
    assert client.get(base, params={"offset": 2**63 - 1}).json()["items"] == []


@pytest.mark.parametrize(
    "query",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": "x"},
        {"offset": -1},
        {"offset": 2**63},
        {"offset": "1.5"},
    ],
)
def test_paging_bounds_are_422(served, query):
    client, _app, created = served
    assert client.get(f"{ROOT}/{LAB}/runs", params=query).status_code == 422
    sessions = f"{ROOT}/{LAB}/runs/{created['id']}/sessions"
    assert client.get(sessions, params=query).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"required_history_sha256": None},
        {"required_history_sha256": 12},
        {"required_history_sha256": HISTORY_SHA256.upper()},
        {"required_history_sha256": HISTORY_SHA256 + "\n"},
        {"required_history_sha256": HISTORY_SHA256[:63]},
        {"required_history_sha256": HISTORY_SHA256 + "0"},
        {"required_history_sha256": HISTORY_SHA256, "name": "x"},
        {"required_history_sha256": HISTORY_SHA256, "request_id": "x"},
        [HISTORY_SHA256],
    ],
)
def test_body_validation_is_422_and_writes_nothing(tmp_path, lab_data, body):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        assert client.post(f"{ROOT}/{LAB}/runs", json=body, headers=ORIGIN).status_code == 422
        # FastAPI validates the body before the handler resolves the laboratory.
        assert client.post(f"{ROOT}/nope/runs", json=body, headers=ORIGIN).status_code == 422
    assert counts(app) == (0, 0)


def test_malformed_json_and_trailing_newline_are_422(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        url = f"{ROOT}/{LAB}/runs"
        assert client.post(url, content=b"{not json", headers=ORIGIN).status_code == 422
        sha = HISTORY_SHA256
        raw = ('{"required_history_sha256":"' + sha + '\\n"}').encode()
        assert client.post(url, content=raw, headers=ORIGIN).status_code == 422
    assert counts(app) == (0, 0)


def test_unknown_lab_is_404_for_every_route_before_any_mutation(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    run_id = str(uuid.uuid4())
    with TestClient(app, base_url=BASE_URL) as client:
        assert create(client, "not-a-lab").status_code == 404
        assert client.get(f"{ROOT}/not-a-lab/runs").status_code == 404
        assert client.get(f"{ROOT}/not-a-lab/runs/{run_id}").status_code == 404
        assert client.get(f"{ROOT}/not-a-lab/runs/{run_id}/sessions").status_code == 404
        assert client.delete(f"{ROOT}/not-a-lab/runs/{run_id}", headers=ORIGIN).status_code == 404
    assert counts(app) == (0, 0)


def test_unknown_or_noncanonical_run_ids_are_404_and_preserve_records(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        created = create(client).json()
        run_id = created["id"]
        bad_ids = [
            str(uuid.uuid4()),
            "not-a-uuid",
            run_id.upper(),
            run_id.replace("-", ""),
            "{" + run_id + "}",
            "urn:uuid:" + run_id,
        ]
        for bad in bad_ids:
            base = f"{ROOT}/{LAB}/runs/{bad}"
            assert client.get(base).status_code == 404, bad
            assert client.get(base + "/sessions").status_code == 404, bad
            assert client.delete(base, headers=ORIGIN).status_code == 404, bad
        assert client.get(f"{ROOT}/{LAB}/runs/{run_id}").status_code == 200
    assert counts(app)[0] == 1


def test_cross_lab_uuid_is_404_and_never_deletes(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        run_id = create(client).json()["id"]
        wrong = f"{ROOT}/{OTHER_LAB}/runs/{run_id}"
        assert client.get(wrong).status_code == 404
        assert client.get(wrong + "/sessions").status_code == 404
        assert client.delete(wrong, headers=ORIGIN).status_code == 404
        assert client.get(f"{ROOT}/{LAB}/runs/{run_id}").status_code == 200
    assert counts(app)[0] == 1


def test_wrong_history_is_409_before_votes_or_replay(tmp_path, lab_data, monkeypatch):
    from laboratorio.engine import reference_lab_service
    from laboratorio.engine.adapter import LabData

    def forbidden(*_args, **_kwargs):
        raise AssertionError("votes or replay ran before the source check")

    monkeypatch.setattr(LabData, "parity_votes", forbidden)
    monkeypatch.setattr(reference_lab_service, "run_reference_lab", forbidden)
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        for lab_id in ("paridad_50_audaz", LAB):
            response = create(client, lab_id, WRONG_SHA)
            assert response.status_code == 409, response.text
    assert counts(app) == (0, 0)


def test_unpinned_loaded_source_is_409_without_replay(tmp_path):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("replay ran against an unpinned source")

    fake = SimpleNamespace(
        history=SimpleNamespace(sha256="b" * 64, labels=()),
        rankings=SimpleNamespace(row_ids=()),
        parity_votes=forbidden,
    )
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    app = create_app(settings, catalog_loader=lambda _settings: fake)
    with TestClient(app, base_url=BASE_URL) as client:
        assert create(client, "paridad_50_audaz", "b" * 64).status_code == 409
    assert counts(app) == (0, 0)


def test_quota_denial_is_409_and_leaves_no_rows(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data, quota_bytes=1)
    with TestClient(app, base_url=BASE_URL) as client:
        response = create(client)
        assert response.status_code == 409
        assert "cuota" in response.json()["detail"]
        assert client.get(f"{ROOT}/{LAB}/runs").json()["total"] == 0
    assert counts(app) == (0, 0)


def test_internal_store_error_on_create_is_generic_500(tmp_path, lab_data, monkeypatch, caplog):
    def failing(*_args, **_kwargs):
        raise ReferenceLabStoreError("secret internal detail")

    monkeypatch.setattr(ref_api, "create_reference_lab_run", failing)
    app = make_app(tmp_path, lab_data)
    with caplog.at_level(logging.ERROR):
        with TestClient(app, base_url=BASE_URL) as client:
            response = create(client)
    assert response.status_code == 500
    assert "secret" not in response.text
    assert "secret" not in caplog.text
    assert counts(app) == (0, 0)


def test_mutations_require_same_origin_local_host(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    body = {"required_history_sha256": HISTORY_SHA256}
    url = f"{ROOT}/{LAB}/runs"
    with TestClient(app, base_url=BASE_URL) as client:
        created = create(client).json()
        target = f"{url}/{created['id']}"
        assert client.post(url, json=body).status_code == 403
        assert client.delete(target).status_code == 403
        external = {**ORIGIN, "Host": "example.com"}
        assert client.post(url, json=body, headers=external).status_code == 403
        assert client.delete(target, headers=external).status_code == 403
        cross = {**ORIGIN, "Sec-Fetch-Site": "cross-site"}
        assert client.post(url, json=body, headers=cross).status_code == 403
        assert client.delete(target, headers=cross).status_code == 403
        foreign = {**ORIGIN, "Origin": "http://evil.example"}
        assert client.post(url, json=body, headers=foreign).status_code == 403
        assert client.delete(target, headers=foreign).status_code == 403
        assert client.get(target).status_code == 200
    assert counts(app)[0] == 1


def test_body_cap_is_64kib_for_headers_and_streamed_bytes(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    url = f"{ROOT}/{LAB}/runs"
    head = ('{"required_history_sha256":"' + WRONG_SHA + '"}').encode()

    def padded(size):
        return head + b" " * (size - len(head))

    with TestClient(app, base_url=BASE_URL) as client:
        assert client.post(url, content=padded(65536), headers=ORIGIN).status_code == 409
        assert client.post(url, content=padded(65537), headers=ORIGIN).status_code == 413
        declared = {**ORIGIN, "Content-Length": "65537"}
        assert client.post(url, content=b"{}", headers=declared).status_code == 413
        junk = {**ORIGIN, "Content-Length": "abc"}
        assert client.post(url, content=b"{}", headers=junk).status_code == 413
        small_header = {**ORIGIN, "Content-Length": "2"}
        assert client.post(url, content=padded(70000), headers=small_header).status_code == 413
        chunks = (piece for piece in (b"{" + b" " * 40000, b" " * 40000, b"}"))
        assert client.post(url, content=chunks, headers=ORIGIN).status_code == 413
        duplicate = [
            ("origin", BASE_URL),
            ("content-type", "application/json"),
            ("content-length", "2"),
            ("content-length", "2"),
        ]
        assert client.post(url, content=b"{}", headers=duplicate).status_code == 413
    assert counts(app) == (0, 0)


def test_cumulative_chunks_over_64kib_are_413_via_raw_asgi(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "path": f"{ROOT}/{LAB}/runs",
        "raw_path": f"{ROOT}/{LAB}/runs".encode(),
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "headers": [
            (b"host", b"localhost:8765"),
            (b"origin", BASE_URL.encode()),
            (b"content-type", b"application/json"),
        ],
        "server": ("localhost", 8765),
        "client": ("127.0.0.1", 50000),
        "state": {},
    }
    pieces = [b" " * 30000, b" " * 30000, b" " * 30000]
    sent = []

    async def drive():
        queue = list(pieces)

        async def receive():
            body = queue.pop(0) if queue else b""
            return {"type": "http.request", "body": body, "more_body": bool(queue)}

        async def send(message):
            sent.append(message)

        await app(scope, receive, send)

    asyncio.run(drive())
    assert sent[0]["status"] == 413


def _corrupt(app, sql, params=()):
    with connection(app.state.repo.path) as db:
        db.execute(sql, params)
        db.commit()


def test_corrupt_result_json_is_controlled_409_everywhere_and_delete_keeps_record(
    tmp_path, lab_data
):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        run_id = create(client).json()["id"]
        _corrupt(app, "UPDATE reference_lab_runs SET result_json='{bad' WHERE id=?", (run_id,))
        base = f"{ROOT}/{LAB}/runs/{run_id}"
        for response in (
            client.get(base),
            client.get(base + "/sessions"),
            client.get(f"{ROOT}/{LAB}/runs"),
            client.delete(base, headers=ORIGIN),
        ):
            assert response.status_code == 409, response.text
            assert "detail" in response.json()
    assert counts(app)[0] == 1


def test_corrupt_session_row_blocks_detail_sessions_and_delete_but_not_thin_list(
    tmp_path, lab_data
):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        run_id = create(client).json()["id"]
        _corrupt(
            app,
            "UPDATE reference_lab_sessions SET session_json='{}' WHERE run_id=? AND ordinal=0",
            (run_id,),
        )
        base = f"{ROOT}/{LAB}/runs/{run_id}"
        assert client.get(base).status_code == 409
        assert client.get(base + "/sessions").status_code == 409
        assert client.delete(base, headers=ORIGIN).status_code == 409
        assert client.get(f"{ROOT}/{LAB}/runs").status_code == 200
    assert counts(app)[0] == 1


def test_detail_returns_stored_config_not_current_catalog_defaults(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        run_id = create(client).json()["id"]
        with connection(app.state.repo.path) as db:
            raw = db.execute(
                "SELECT metadata_json FROM reference_lab_runs WHERE id=?", (run_id,)
            ).fetchone()[0]
            metadata = json.loads(raw)
            metadata["config"]["coverage"] = 777
            db.execute(
                "UPDATE reference_lab_runs SET metadata_json=? WHERE id=?",
                (json.dumps(metadata), run_id),
            )
            db.commit()
        detail = client.get(f"{ROOT}/{LAB}/runs/{run_id}").json()
    assert detail["config"]["coverage"] == 777


def test_delete_is_204_empty_cascades_and_then_404(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        run_id = create(client).json()["id"]
        assert counts(app)[1] > 0
        base = f"{ROOT}/{LAB}/runs/{run_id}"
        deleted = client.delete(base, headers=ORIGIN)
        assert deleted.status_code == 204
        assert deleted.content == b""
        assert counts(app) == (0, 0)
        assert client.get(base).status_code == 404
        assert client.get(base + "/sessions").status_code == 404
        assert client.delete(base, headers=ORIGIN).status_code == 404


def _start(target, results, name):
    def run():
        results[name] = target()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_delete_waits_for_a_paused_read_instead_of_corrupting_it(tmp_path, lab_data, monkeypatch):
    app = make_app(tmp_path, lab_data)
    entered, release = threading.Event(), threading.Event()
    original = ref_api.get_reference_lab_run
    calls = []

    def paused(repo, run_id):
        calls.append(run_id)
        if len(calls) == 1:
            entered.set()
            assert release.wait(10)
        return original(repo, run_id)

    with TestClient(app, base_url=BASE_URL) as client:
        run_id = create(client).json()["id"]
        base = f"{ROOT}/{LAB}/runs/{run_id}"
        monkeypatch.setattr(ref_api, "get_reference_lab_run", paused)
        results = {}
        reader = _start(lambda: client.get(base + "/sessions").status_code, results, "read")
        try:
            assert entered.wait(10)
            deleter = _start(
                lambda: client.delete(base, headers=ORIGIN).status_code, results, "delete"
            )
            deleter.join(0.5)
            assert deleter.is_alive(), "delete must wait for the reference-lab lock"
        finally:
            release.set()
        reader.join(15)
        deleter.join(15)
        assert results == {"read": 200, "delete": 204}
        assert client.get(base).status_code == 404


def test_read_waits_for_a_paused_delete_and_sees_clean_404(tmp_path, lab_data, monkeypatch):
    app = make_app(tmp_path, lab_data)
    entered, release = threading.Event(), threading.Event()
    original = ref_api.delete_reference_lab_run

    def paused(repo, run_id):
        entered.set()
        assert release.wait(10)
        return original(repo, run_id)

    with TestClient(app, base_url=BASE_URL) as client:
        run_id = create(client).json()["id"]
        base = f"{ROOT}/{LAB}/runs/{run_id}"
        monkeypatch.setattr(ref_api, "delete_reference_lab_run", paused)
        results = {}
        deleter = _start(lambda: client.delete(base, headers=ORIGIN).status_code, results, "d")
        try:
            assert entered.wait(10)
            reader = _start(lambda: client.get(base).status_code, results, "r")
            reader.join(0.5)
            assert reader.is_alive(), "read must wait for the reference-lab lock"
        finally:
            release.set()
        deleter.join(15)
        reader.join(15)
        assert results == {"d": 204, "r": 404}


def test_create_takes_rankings_lock_while_event_loop_stays_free(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        assert isinstance(app.state.reference_lab_lock, type(threading.RLock()))
        results = {}
        app.state.rankings_lock.acquire()
        try:
            writer = _start(lambda: create(client, LAB, WRONG_SHA).status_code, results, "post")
            writer.join(0.5)
            assert writer.is_alive(), "create must also hold the shared rankings lock"
            # Reads of stored runs wait on the reference-lab lock that create holds, but the
            # event loop and the lock-free catalog stay responsive.
            assert client.get(ROOT).status_code == 200
        finally:
            app.state.rankings_lock.release()
        writer.join(15)
        assert results == {"post": 409}
