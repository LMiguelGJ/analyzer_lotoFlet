# Contract traceability:
# B-API-092/093: test_validate_is_dry_and_native_batch_routes_are_registered
# B-API-094/095: test_native_batch_post_uses_queue_and_idempotent_lookup;
#   test_identity_lookup_maps_a_missing_verified_experiment_to_conflict
# B-API-096/097: test_policy_route_is_bounded_cas_and_does_not_rewrite_frozen_batches
# B-API-098: test_validate_does_not_reserve_capacity_or_request_identity
# B-API-099: test_native_batch_schema_versions_reject_coercible_values
# B-API-100: test_native_batch_body_is_closed_and_limited

import sqlite3

import pytest
from fastapi.testclient import TestClient
from test_api import CatalogStub
from test_batch_admission import _saved_inputs
from test_queue import request as legacy_request

from laboratorio.app import create_app
from laboratorio.domain.contracts import ExperimentStatus
from laboratorio.domain.profile_session_v5 import run_profile_batch_v5
from laboratorio.settings import Settings


def _client(tmp_path):
    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    app = create_app(settings, catalog_loader=lambda _: CatalogStub())
    return app, TestClient(app, base_url="http://localhost:8765")


def _submission_body(app, request_id="native-api-1"):
    _, dataset, _, strategy, submission = _saved_inputs(app.state.repo, row_count=4)
    return {
        "schema_version": 1,
        "profile": {
            "id": submission.profile_id,
            "revision": submission.profile_revision,
            "sha256": submission.profile_sha256,
        },
        "dataset_sha256": dataset.dataset_sha256,
        "strategies": [
            {
                "id": strategy["id"],
                "revision": 1,
                "definition_sha256": strategy["definition_sha256"],
            }
        ],
        "conditions": {
            "schema_version": 1,
            "start_draw": submission.conditions.start_draw,
            "capital": submission.conditions.capital,
            "goal": submission.conditions.goal,
            "settlement": submission.conditions.settlement.value,
            "max_elapsed_draws": None,
            "max_bet_draws": None,
            "end_minute": None,
            "duration_minutes": None,
        },
        "max_draws": submission.max_draws,
        "client_request_id": request_id,
    }


def _post(client, path, body):
    return client.post(path, json=body, headers={"Origin": "http://localhost:8765"})


def _capture_enqueue(app):
    enqueued = []
    app.state.jobs._enqueue_profile_batch = lambda identifier: enqueued.append(identifier)
    return enqueued


def test_validate_is_dry_and_native_batch_routes_are_registered(tmp_path):
    app, client = _client(tmp_path)
    with client:
        body = _submission_body(app)
        body["conditions"]["start_draw"] = "2025-09-02 05:11"
        invalid = _post(client, "/api/v1/profile-batches/validate", body)
        assert invalid.status_code == 422
        body["conditions"]["start_draw"] = "2025-09-02 05:10"
        before = app.state.repo.admission_logical_bytes()
        with sqlite3.connect(app.state.repo.path) as db:
            before_counts = tuple(
                db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("experiments", "runs", "profile_batch_admissions", "settings_quota")
            )
        response = _post(client, "/api/v1/profile-batches/validate", body)
        assert response.status_code == 200, response.text
        assert response.json()["valid"] is True
        with sqlite3.connect(app.state.repo.path) as db:
            after_counts = tuple(
                db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("experiments", "runs", "profile_batch_admissions", "settings_quota")
            )
        assert after_counts == before_counts
        assert app.state.repo.admission_logical_bytes() == before
        assert app.state.repo.get_profile_batch_request_id(body["client_request_id"]) is None
        enqueued = _capture_enqueue(app)
        created = _post(client, "/api/v1/profile-batches", body)
        assert created.status_code == 201
        assert (
            created.json()["batch_admission"]["effective_constraints"]
            == response.json()["effective_constraints"]
        )
        assert enqueued == [created.json()["id"]]
        strategy = body["strategies"][0]
        query = {
            "profile_id": body["profile"]["id"],
            "profile_revision": body["profile"]["revision"],
            "profile_sha256": body["profile"]["sha256"],
        }
        projection = client.get(f"/api/v1/strategies/{strategy['id']}", params=query).json()
        assert projection["execution_available"] is True


def test_native_batch_post_uses_queue_and_idempotent_lookup(tmp_path):
    app, client = _client(tmp_path)
    with client:
        enqueued = _capture_enqueue(app)
        body = _submission_body(app, request_id="native/api/request")
        first = _post(client, "/api/v1/profile-batches", body)
        assert first.status_code == 201, first.text
        result = first.json()
        assert result["created"] is True
        assert result["request_schema_version"] == 5
        assert result["runs"][0]["strategy"]["id"] == body["strategies"][0]["id"]
        second = _post(client, "/api/v1/profile-batches", body)
        assert second.status_code == 200
        assert second.json()["id"] == result["id"]
        assert second.json()["created"] is False
        assert client.get("/api/v1/profile-batches/by-client-request/not-found").status_code == 404
        lookup = client.get(
            f"/api/v1/profile-batches/by-client-request/{body['client_request_id']}"
        )
        assert lookup.status_code == 200
        assert lookup.json()["id"] == result["id"]
        assert lookup.json()["status"] == "pending"
        assert lookup.json()["links"]["compare"].endswith("/compare")
        assert lookup.json()["links"]["runs"][0]["replay"].endswith("/runs/0/replay")
        assert enqueued == [result["id"]]
        saved = app.state.repo.get_experiment(result["id"])
        dataset = app.state.repo.get_dataset(saved.request.dataset_sha256)
        app.state.repo.start_run(saved.id, 0)
        run_result = run_profile_batch_v5(
            saved.request, saved.profile, dataset, None, operation_budget=saved.request.max_draws
        )
        app.state.repo.complete_profile_batch_run(
            saved.id, 0, run_result, settings=app.state.settings
        )
        app.state.repo.complete_experiment(saved.id)
        completed_retry = _post(client, "/api/v1/profile-batches", body)
        assert completed_retry.status_code == 200
        assert completed_retry.json()["status"] == "completed"
        assert enqueued == [result["id"]]
        changed = {**body, "max_draws": 1}
        conflict = _post(client, "/api/v1/profile-batches", changed)
        assert conflict.status_code == 409
        cancelled_body = {**body, "client_request_id": "native-api-cancelled"}
        cancelled = _post(client, "/api/v1/profile-batches", cancelled_body)
        assert cancelled.status_code == 201
        app.state.repo.finish_incomplete(cancelled.json()["id"], ExperimentStatus.CANCELLED)
        cancelled_retry = _post(client, "/api/v1/profile-batches", cancelled_body)
        assert cancelled_retry.status_code == 200
        assert cancelled_retry.json()["status"] == "cancelled"
        assert enqueued == [result["id"], cancelled.json()["id"]]


def test_identity_lookup_maps_a_missing_verified_experiment_to_conflict(tmp_path, monkeypatch):
    app, client = _client(tmp_path)
    with client:
        _capture_enqueue(app)
        body = _submission_body(app, request_id="corrupt-client-record")
        created = _post(client, "/api/v1/profile-batches", body)
        assert created.status_code == 201
        monkeypatch.setattr(app.state.repo, "get_experiment", lambda _: None)
        lookup = client.get(
            f"/api/v1/profile-batches/by-client-request/{body['client_request_id']}"
        )
        assert lookup.status_code == 409


def test_policy_route_is_bounded_cas_and_does_not_rewrite_frozen_batches(tmp_path):
    app, client = _client(tmp_path)
    with client:
        _capture_enqueue(app)
        body = _submission_body(app)
        created = _post(client, "/api/v1/profile-batches", body)
        assert created.status_code == 201, created.text
        original = created.json()["batch_admission"]["effective_constraints"]
        current = client.get("/api/v1/execution-policy")
        assert current.status_code == 200
        policy = current.json()
        assert policy["policy"]["worker_count"] == 1
        assert policy["explanation"]
        updated = client.put(
            "/api/v1/execution-policy",
            json={"expected_revision": policy["revision"], "max_bet_draws": 7},
            headers={"Origin": "http://localhost:8765"},
        )
        assert updated.status_code == 200
        assert updated.json()["policy"]["max_bet_draws"] == 7
        future_body = _submission_body(app, request_id="future-policy")
        future = _post(client, "/api/v1/profile-batches", future_body)
        assert future.status_code == 201
        assert future.json()["batch_admission"]["effective_constraints"]["max_bet_draws"] == 7
        stale = client.put(
            "/api/v1/execution-policy",
            json={"expected_revision": policy["revision"], "max_bet_draws": 8},
            headers={"Origin": "http://localhost:8765"},
        )
        assert stale.status_code == 409
        assert (
            client.put(
                "/api/v1/execution-policy",
                json={"expected_revision": 2, "worker_count": 2},
                headers={"Origin": "http://localhost:8765"},
            ).status_code
            == 422
        )
        assert (
            client.put(
                "/api/v1/execution-policy",
                json={"expected_revision": 2, "run_timeout_seconds": 3_601},
                headers={"Origin": "http://localhost:8765"},
            ).status_code
            == 422
        )
        saved = app.state.repo.get_experiment(created.json()["id"])
        assert saved.batch_admission["effective_constraints"] == original


def test_validate_does_not_reserve_capacity_or_request_identity(tmp_path):
    app, client = _client(tmp_path)
    with client:
        body = _submission_body(app, request_id="dry-at-capacity")
        app.state.repo.create_experiment(
            legacy_request("Legacy pending"),
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="test",
        )
        app.state.repo.update_execution_policy({"max_pending_runs": 1})
        validated = _post(client, "/api/v1/profile-batches/validate", body)
        assert validated.status_code == 200
        assert validated.json()["limits"]["reservation_created"] is False
        assert app.state.repo.get_profile_batch_request_id(body["client_request_id"]) is None
        rejected = _post(client, "/api/v1/profile-batches", body)
        assert rejected.status_code == 409
        assert app.state.repo.get_profile_batch_request_id(body["client_request_id"]) is None


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
@pytest.mark.parametrize("endpoint", ["/validate", ""])
def test_native_batch_schema_versions_reject_coercible_values(
    tmp_path, field_path, value, endpoint
):
    app, client = _client(tmp_path)
    with client:
        body = _submission_body(app)
        target = body
        for key in field_path:
            target = target[key]
        target["schema_version"] = value
        response = _post(client, f"/api/v1/profile-batches{endpoint}", body)
        assert response.status_code == 422, response.text


def test_native_batch_body_is_closed_and_limited(tmp_path):
    app, client = _client(tmp_path)
    with client:
        body = _submission_body(app)
        assert (
            _post(client, "/api/v1/profile-batches/validate", {**body, "selector": "x"}).status_code
            == 422
        )
        assert (
            _post(
                client, "/api/v1/profile-batches/validate", {**body, "client_request_id": ""}
            ).status_code
            == 422
        )
        duplicate_ref = {**body, "strategies": [body["strategies"][0]] * 2}
        assert _post(client, "/api/v1/profile-batches/validate", duplicate_ref).status_code == 422
        custom_code = {
            **body,
            "strategies": [{**body["strategies"][0], "python_code": "print(1)"}],
        }
        assert _post(client, "/api/v1/profile-batches/validate", custom_code).status_code == 422
        oversized_window = {**body, "max_draws": 10_001}
        assert (
            _post(client, "/api/v1/profile-batches/validate", oversized_window).status_code == 422
        )
        response = client.post(
            "/api/v1/profile-batches/validate",
            content=b"{}" + b" " * (65 * 1024),
            headers={"Origin": "http://localhost:8765", "Content-Type": "application/json"},
        )
        assert response.status_code == 413
