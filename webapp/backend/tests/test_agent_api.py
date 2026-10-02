import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import httpx
import pytest
from fastapi.testclient import TestClient
from test_api import CatalogStub
from test_history_import import document, history_headers
from test_import_records import profile
from test_profile_batch_api import _capture_enqueue, _submission_body

from laboratorio.agent_credentials import load_or_create_token
from laboratorio.app import create_app
from laboratorio.domain.profile_session_v5 import run_profile_batch_v5
from laboratorio.importing.history import MAX_HISTORY_BYTES
from laboratorio.settings import Settings

ORIGIN = "http://localhost:8765"


def _app(tmp_path):
    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    return create_app(settings, catalog_loader=lambda _: CatalogStub())


def _credential(client):
    response = client.post("/api/v1/settings/agent-credential", json={}, headers={"Origin": ORIGIN})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_agent_facade_auth_allowlist_delegation_and_local_credential(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        token = _credential(client)
        assert len(token) >= 40
        headers = {"Authorization": f"Bearer {token}"}

        for authorization in (None, "Bearer malformed", "Bearer " + "0" * 64):
            request_headers = {} if authorization is None else {"Authorization": authorization}
            response = client.get("/api/agent/v1/catalog", headers=request_headers)
            assert response.status_code == 401
            assert token not in response.text
            post_headers = {**request_headers, "Origin": ORIGIN}
            write_response = client.post(
                "/api/agent/v1/profile-batches/validate", content=b"", headers=post_headers
            )
            assert write_response.status_code == 401
            assert token not in write_response.text

        catalog = client.get("/api/agent/v1/catalog", headers=headers)
        assert catalog.status_code == 200
        assert catalog.json()["game"]["name"]
        strategy_page = client.get("/api/agent/v1/strategies", headers=headers)
        assert strategy_page.status_code == 200
        preset = strategy_page.json()["items"][0]
        exact_revision = client.get(
            f"/api/agent/v1/strategies/{preset['id']}/revisions/{preset['revision']}",
            headers=headers,
        )
        assert exact_revision.status_code == 200
        assert exact_revision.json()["definition_sha256"] == preset["definition_sha256"]
        assert client.get("/api/agent/v1/execution-policy", headers=headers).status_code == 404
        assert (
            client.delete("/api/agent/v1/experiments/not-real", headers=headers).status_code == 403
        )
        assert (
            client.delete(
                "/api/agent/v1/experiments/not-real",
                headers={**headers, "Origin": ORIGIN},
            ).status_code
            == 405
        )
        assert client.post(
            "/api/agent/v1/catalog", json={}, headers={**headers, "Origin": ORIGIN}
        ).status_code in (404, 405)
        assert client.get("/api/v1/catalog").status_code == 200


def test_agent_origin_guards_and_credential_stable_across_restart(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        token = _credential(client)
        headers = {"Authorization": f"Bearer {token}"}
        assert (
            client.get(
                "/api/agent/v1/catalog", headers={**headers, "Origin": "http://evil.example"}
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/agent/v1/catalog", headers={**headers, "Sec-Fetch-Site": "cross-site"}
            ).status_code
            == 403
        )
        duplicate_host = client.get(
            "/api/agent/v1/catalog",
            headers=[
                ("Authorization", f"Bearer {token}"),
                ("Host", "localhost:8765"),
                ("Host", "localhost:8765"),
            ],
        )
        duplicate_origin = client.get(
            "/api/agent/v1/catalog",
            headers=[
                ("Authorization", f"Bearer {token}"),
                ("Origin", ORIGIN),
                ("Origin", ORIGIN),
            ],
        )
        assert duplicate_host.status_code == duplicate_origin.status_code == 403
        assert (
            client.post(
                "/api/v1/settings/agent-credential", json={}, headers={"Origin": ORIGIN}
            ).json()["token"]
            == token
        )

    app = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        assert _credential(client) == token
        assert token not in client.get("/api/v1/settings").text


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        ((), True),
        (("conditions",), True),
        ((), 1.0),
        (("conditions",), 1.0),
        ((), "1"),
        (("conditions",), "1"),
    ],
)
@pytest.mark.parametrize("suffix", ["/validate", ""])
def test_agent_batch_schema_versions_reject_coercible_values(tmp_path, field_path, value, suffix):
    app = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        token = _credential(client)
        headers = {"Authorization": f"Bearer {token}", "Origin": ORIGIN}
        body = _submission_body(app)
        target = body
        for key in field_path:
            target = target[key]
        target["schema_version"] = value
        response = client.post(f"/api/agent/v1/profile-batches{suffix}", json=body, headers=headers)
        assert response.status_code == 422, response.text


def test_agent_batch_facade_reuses_native_admission_and_safe_links(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        token = _credential(client)
        headers = {"Authorization": f"Bearer {token}", "Origin": ORIGIN}
        enqueued = _capture_enqueue(app)
        body = _submission_body(app, request_id="agent/replay-safe")

        validated = client.post(
            "/api/agent/v1/profile-batches/validate", json=body, headers=headers
        )
        assert validated.status_code == 200, validated.text
        assert validated.json()["valid"] is True

        created = client.post("/api/agent/v1/profile-batches", json=body, headers=headers)
        assert created.status_code == 201, created.text
        value = created.json()
        assert value["created"] is True
        assert (
            value["batch_admission"]["effective_constraints"]
            == validated.json()["effective_constraints"]
        )
        assert value["links"]["self"] == f"/api/agent/v1/experiments/{value['id']}"
        assert "/api/v1/" not in str(value["links"])
        assert enqueued == [value["id"]]

        retried = client.post("/api/agent/v1/profile-batches", json=body, headers=headers)
        assert retried.status_code == 200
        assert retried.json()["id"] == value["id"]
        lookup = client.get(
            "/api/agent/v1/profile-batches/by-client-request/agent/replay-safe",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert lookup.status_code == 200
        assert lookup.json()["id"] == value["id"]
        assert lookup.json()["status"] == "pending"

        detail = client.get(f"/api/agent/v1/experiments/{value['id']}", headers=headers)
        compare = client.get(f"/api/agent/v1/experiments/{value['id']}/compare", headers=headers)
        assert detail.status_code == compare.status_code == 200
        assert detail.json()["id"] == compare.json()["id"] == value["id"]
        assert compare.json()["requested"] == 1

        saved = app.state.repo.get_experiment(value["id"])
        dataset = app.state.repo.get_dataset(saved.request.dataset_sha256)
        app.state.repo.start_run(saved.id, 0)
        result = run_profile_batch_v5(
            saved.request,
            saved.profile,
            dataset,
            None,
            operation_budget=saved.request.max_draws,
        )
        app.state.repo.complete_profile_batch_run(saved.id, 0, result, settings=app.state.settings)
        app.state.repo.complete_experiment(saved.id)
        replay = client.get(
            f"/api/agent/v1/experiments/{value['id']}/runs/0/replay", headers=headers
        )
        trajectory = client.get(
            f"/api/agent/v1/experiments/{value['id']}/runs/0/trajectory", headers=headers
        )
        assert replay.status_code == trajectory.status_code == 200
        assert replay.json()["result_kind"] == "profile"
        assert trajectory.json()["result_kind"] == "profile"
        native_base = f"/api/v1/experiments/{value['id']}"
        agent_base = f"/api/agent/v1/experiments/{value['id']}"
        for suffix in (
            "",
            "/compare",
            "/runs/0/replay",
            "/runs/0/trajectory",
        ):
            native = client.get(native_base + suffix)
            facade = client.get(agent_base + suffix, headers=headers)
            assert native.status_code == facade.status_code == 200
            assert facade.json() == native.json()
        detail = client.get(agent_base, headers=headers).json()
        compare = client.get(agent_base + "/compare", headers=headers).json()
        for projection in (detail["runs"][0]["result"], compare["runs"][0]["result"]):
            assert projection["metric_scope"] == "saved_individual_run"
            assert {"delta", "net", "return_per_wagered", "roi", "max_drawdown"} <= set(projection)
        completed_retry = client.post("/api/agent/v1/profile-batches", json=body, headers=headers)
        assert completed_retry.status_code == 200
        assert completed_retry.json()["status"] == "completed"

        cancel_body = _submission_body(app, request_id="agent/cancelled")
        cancel_created = client.post(
            "/api/agent/v1/profile-batches", json=cancel_body, headers=headers
        )
        assert cancel_created.status_code == 201
        app.state.repo.recover_jobs()
        cancelled = client.post(
            f"/api/agent/v1/experiments/{cancel_created.json()['id']}/cancel", headers=headers
        )
        assert cancelled.status_code == 200
        cancelled_retry = client.post(
            "/api/agent/v1/profile-batches", json=cancel_body, headers=headers
        )
        assert cancelled_retry.status_code == 200
        assert cancelled_retry.json()["status"] == "cancelled"

        changed = {**body, "max_draws": body["max_draws"] - 1}
        conflict = client.post("/api/agent/v1/profile-batches", json=changed, headers=headers)
        assert conflict.status_code == 409
        assert enqueued == [value["id"], cancel_created.json()["id"]]


@pytest.mark.parametrize("corruption", ["dataset", "admission"])
def test_corrupt_saved_batch_is_opaque_conflict_on_native_and_agent_facades(tmp_path, corruption):
    app = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        token = _credential(client)
        headers = {"Authorization": f"Bearer {token}", "Origin": ORIGIN}
        _capture_enqueue(app)
        body = _submission_body(app, request_id=f"corrupt-{corruption}")
        created = client.post("/api/agent/v1/profile-batches", json=body, headers=headers)
        assert created.status_code == 201
        identifier = created.json()["id"]
        saved = app.state.repo.get_experiment(identifier)
        dataset = app.state.repo.get_dataset(saved.request.dataset_sha256)
        app.state.repo.start_run(identifier, 0)
        result = run_profile_batch_v5(
            saved.request,
            saved.profile,
            dataset,
            None,
            operation_budget=saved.request.max_draws,
        )
        app.state.repo.complete_profile_batch_run(
            identifier, 0, result, settings=app.state.settings
        )
        app.state.repo.complete_experiment(identifier)

        with sqlite3.connect(app.state.repo.path) as db:
            if corruption == "dataset":
                db.execute("DROP TRIGGER datasets_no_update")
                db.execute(
                    "UPDATE datasets SET raw_bytes = X'00' WHERE dataset_sha256 = ?",
                    (saved.request.dataset_sha256,),
                )
            else:
                row = db.execute(
                    "SELECT source_identity_json FROM profile_batch_admissions "
                    "WHERE experiment_id = ?",
                    (identifier,),
                ).fetchone()
                identity = json.loads(row[0])
                identity["row_count"] += 1
                db.execute("DROP TRIGGER profile_batch_admissions_no_update")
                db.execute(
                    "UPDATE profile_batch_admissions SET source_identity_json = ? "
                    "WHERE experiment_id = ?",
                    (json.dumps(identity, separators=(",", ":")), identifier),
                )

        native_base = f"/api/v1/experiments/{identifier}"
        agent_base = f"/api/agent/v1/experiments/{identifier}"
        for suffix in ("", "/compare", "/runs/0/replay", "/runs/0/trajectory"):
            native = client.get(native_base + suffix)
            facade = client.get(agent_base + suffix, headers=headers)
            assert native.status_code == facade.status_code == 409
            assert native.json() == facade.json()


def test_agent_history_preview_and_promote_use_raw_body_and_registered_context(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        token = _credential(client)
        game = profile()
        app.state.repo.create_game_profile(game)
        headers = {
            **history_headers(game),
            "Origin": ORIGIN,
            "Authorization": f"Bearer {token}",
        }
        raw = json.dumps(document(), separators=(",", ":")).encode()

        too_large = client.post(
            "/api/agent/v1/history/preview",
            content=b"x" * (MAX_HISTORY_BYTES + 1),
            headers=headers,
        )
        assert too_large.status_code == 413
        path_input = client.post(
            "/api/agent/v1/history/preview",
            json={"path": "not-a-filesystem-input"},
            headers=headers,
        )
        assert path_input.status_code == 422

        preview = client.post("/api/agent/v1/history/preview", content=raw, headers=headers)
        assert preview.status_code == 200, preview.text
        assert preview.json()["promotable"] is True
        promoted = client.post(
            "/api/agent/v1/history/promote",
            content=raw,
            headers={**headers, "X-Expected-Dataset-Sha256": preview.json()["dataset_sha256"]},
        )
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["dataset_sha256"] == preview.json()["dataset_sha256"]
        assert token not in preview.text + promoted.text


def test_corrupt_agent_credential_fails_closed(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "agent-token").write_text("not a valid credential\n", encoding="utf-8")
    app = _app(tmp_path)
    with pytest.raises((RuntimeError, ValueError, OSError)):
        with TestClient(app, base_url=ORIGIN):
            pass


def test_agent_auth_rejects_duplicate_authorization_headers(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        token = _credential(client)
        for values in (
            (f"Bearer {token}", f"Bearer {token}"),
            (f"Bearer {token}", "Bearer incorrect"),
        ):
            response = client.get(
                "/api/agent/v1/catalog",
                headers=[("Authorization", value) for value in values],
            )
            assert response.status_code == 401
            assert token not in response.text


def test_agent_auth_rejects_non_ascii_authorization_without_server_error(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN):

        async def request_with_invalid_header_byte():
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
                headers = [(b"authorization", b"Bearer \xff")]
                return await client.get("/api/agent/v1/catalog", headers=headers)

        response = asyncio.run(request_with_invalid_header_byte())
        assert response.status_code == 401
        assert "Bearer" not in response.text


def test_concurrent_agent_credential_creation_publishes_only_complete_winner(tmp_path, monkeypatch):
    credential_path = tmp_path / "agent-token"
    first_paused = Event()
    release_first = Event()
    call_lock = Lock()
    calls = 0

    def controlled_token_urlsafe(_nbytes):
        nonlocal calls
        with call_lock:
            calls += 1
            call = calls
        if call == 1:
            first_paused.set()
            if not release_first.wait(timeout=5):
                raise TimeoutError("test did not release the first credential creator")
            return "A" * 43
        return "B" * 43

    monkeypatch.setattr(
        "laboratorio.agent_credentials.secrets.token_urlsafe", controlled_token_urlsafe
    )
    pool = ThreadPoolExecutor(max_workers=2)
    first_future = pool.submit(load_or_create_token, credential_path)
    second_future = None
    first_result = None
    try:
        assert first_paused.wait(timeout=3), "first creator did not reach the controlled pause"
        second_future = pool.submit(load_or_create_token, credential_path)
        second_result = second_future.result(timeout=3)
        assert second_result == "B" * 43
        assert credential_path.read_text(encoding="ascii") == second_result
        scratch = [item for item in tmp_path.iterdir() if item != credential_path]
        assert len(scratch) == 1
        assert scratch[0].read_bytes() == b""
    finally:
        release_first.set()
        try:
            first_result = first_future.result(timeout=5)
        finally:
            pool.shutdown(wait=True)

    assert first_result == second_result == "B" * 43
    assert credential_path.read_text(encoding="ascii") == first_result
    assert list(tmp_path.iterdir()) == [credential_path]
