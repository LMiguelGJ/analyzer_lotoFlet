"""HTTP read projections of persisted profile jobs; no public profile submission."""

# Contract traceability:
# B-API-073..076: test_profile_static_and_random_get_projection_is_inert_and_discriminated
# B-API-077: test_profile_held_and_failed_are_incomplete_without_replay
# B-API-078: test_public_registration_import_submission_and_completed_read
# B-API-079..081: test_dataset_detail_and_draws_use_verified_embedded_profile
# B-API-082: test_registration_strict_idempotent_conflict_quota_and_origin
# B-API-083/084: test_profile_submit_rejects_invalid_binding_affordability_and_queue_failure
# B-API-085: test_legacy_exact_http_fixture_unchanged
# B-API-086: test_private_cycling_public_reads_and_queue_start_refuse_without_leaking
# B-API-087: test_public_cycling_submit_spawn_replay_and_rejection_before_rows
# B-API-088: test_completed_cycling_public_read_projection_and_visibility
# B-API-089: test_public_audaz_post_has_truthful_detail_list_and_replay
# B-API-090: test_public_schema4_recovery_submission_worker_and_truthful_reads
# B-API-091: test_public_schema4_stop_persists_round_limit_and_replays

import asyncio
import json
import sqlite3
import time
from dataclasses import asdict, replace
from hashlib import sha256
from unittest.mock import patch

import pytest
from test_api import CatalogStub, payload, result
from test_import_api import payload as import_payload
from test_import_records import options, row
from test_import_records import profile as imported_profile
from test_profile_storage import cycling_result, profile_request, replay

from laboratorio.api import run_summary
from laboratorio.domain.contracts import (
    ExperimentRequest,
    ExperimentStatus,
    RunStatus,
    SettlementMode,
    legacy_quiniela_80_profile,
)
from laboratorio.domain.metrics import financial_metrics
from laboratorio.domain.profile_request import profile_sha256, serialize_profile_request
from laboratorio.domain.profile_request_v2 import (
    ProfileCyclingRequest,
    serialize_profile_cycling_request,
)
from laboratorio.domain.profile_result_v2 import serialize_profile_cycling_result
from laboratorio.domain.profile_session import ProfileConditions, ProfileSelector, Q80CyclingStaking
from laboratorio.settings import Settings
from laboratorio.storage.quota import QuotaExceeded
from laboratorio.storage.repository import SavedRun


@pytest.fixture
def api_setup(tmp_path):
    from fastapi.testclient import TestClient

    from laboratorio.app import create_app

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    app = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(app, base_url="http://localhost:8765") as client:
        yield client, app, settings


@pytest.fixture(params=[1, 3, 5])
def profile_job(api_setup, request):
    client, app, _ = api_setup
    repo = app.state.repo
    positions = request.param
    profile = imported_profile(positions=positions)
    dataset = repo.promote_dataset(
        json.dumps(
            [row(day=f"2025-09-0{day}", numbers=tuple(range(positions))) for day in (1, 2, 3)]
        ).encode(),
        **options(positions=positions),
    ).dataset
    repo.create_game_profile(profile)
    request = replace(
        profile_request(profile),
        dataset_sha256=dataset.dataset_sha256,
        conditions=ProfileConditions(
            1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL, max_elapsed_draws=2
        ),
        selector=ProfileSelector(1, "static-numbers/v1", 2, numbers=(0, 1)),
    )
    return client, app, profile, dataset, request


@pytest.mark.parametrize("random", [False, True])
def test_profile_static_and_random_get_projection_is_inert_and_discriminated(
    profile_job, monkeypatch, random
):
    client, app, profile, dataset, request = profile_job
    if random:
        request = replace(
            request,
            name="Random trial",
            selector=ProfileSelector(
                1,
                "seeded-random/hash-sha256-v1",
                2,
                seed=17,
                algorithm_version="hash-sha256-v1",
            ),
        )
    repo = app.state.repo
    identifier = repo.create_profile_experiment(request)
    expected_result = replay(request, profile, dataset)
    repo.start_run(identifier, 0)
    repo.complete_profile_run(identifier, 0, expected_result)
    repo.complete_experiment(identifier)
    # A GET must project the persisted result; never re-run the financial engine.
    monkeypatch.setattr(
        "laboratorio.domain.profile_session.run_profile_session",
        lambda *args, **kwargs: pytest.fail("recalculated during GET"),
    )
    monkeypatch.setattr(
        "laboratorio.domain.session.run_session",
        lambda *args, **kwargs: pytest.fail("legacy recalculation during GET"),
    )
    uri = f"/api/v1/experiments/{identifier}"
    detail = client.get(uri)
    assert detail.status_code == 200
    detail = detail.json()
    listed = client.get("/api/v1/experiments", params={"name_contains": request.name}).json()
    assert listed["total"] == 1 and listed["items"] == [detail]
    assert detail["request_kind"] == "profile"
    assert detail["request"] == json.loads(serialize_profile_request(request))
    assert detail["profile"] == profile.model_dump(mode="json")
    assert detail["display"] == {
        "name": request.name,
        "currency": profile.currency,
        "scale": profile.scale,
        "capital": 100,
        "goal": 200,
        "selector_label": request.selector.capability,
        "staking_label": request.staking.capability,
    }
    assert detail["sources"] == {
        "history_id": dataset.dataset_sha256,
        "history_sha256": dataset.dataset_sha256,
        "rankings_id": "",
        "rankings_sha256": "",
        "code_version": "profile-v1",
    }
    summary = detail["runs"][0]
    assert summary == {
        "ordinal": 0,
        "configuration_id": None,
        "status": "completed",
        "result_kind": "profile",
        "bets_count": expected_result.bet_draws,
        "result": {
            "schema_version": 1,
            "profile_id": profile.profile_id,
            "profile_revision": profile.revision,
            "outcome": expected_result.outcome.value,
            "collisions": list(expected_result.collisions),
            "elapsed_draws": expected_result.elapsed_draws,
            "bet_draws": expected_result.bet_draws,
            "wagered": expected_result.wagered,
            "paid": expected_result.paid,
            "final_balance": expected_result.final_balance,
            "delta": expected_result.final_balance - request.conditions.capital,
            **financial_metrics(expected_result, request.conditions.capital),
        },
    }
    assert "bets" not in summary["result"]
    comparison = client.get(f"{uri}/compare").json()
    assert comparison == {
        "id": identifier,
        "status": "completed",
        "request_kind": "profile",
        "completed": 1,
        "requested": 1,
        "complete": True,
        "runs": [summary],
    }
    page = client.get(f"{uri}/runs/0/replay", params={"limit": 1}).json()
    assert page == {
        "result_kind": "profile",
        "total": expected_result.bet_draws,
        "offset": 0,
        "limit": 1,
        "items": [
            {
                "label": bet.label,
                "stakes": [list(pair) for pair in bet.stakes],
                "results": list(bet.results),
                "wagered": bet.wagered,
                "paid": bet.paid,
                "balance": bet.balance,
            }
            for bet in expected_result.bets[:1]
        ],
    }
    assert len(page["items"][0]["results"]) == profile.positions
    assert "numbers" not in page["items"][0] and "per_number" not in page["items"][0]
    trajectory = client.get(f"{uri}/runs/0/trajectory")
    assert trajectory.status_code == 200
    assert trajectory.json()["result_kind"] == "profile"
    assert trajectory.json()["total"] == expected_result.bet_draws
    assert all(
        point["replay"] == f"replay?offset={point['source_index']}&limit=1"
        for point in trajectory.json()["points"]
    )
    assert client.get(f"{uri}/runs/0/replay", params={"offset": 1, "limit": 1}).json()["items"] == [
        {
            "label": bet.label,
            "stakes": [list(pair) for pair in bet.stakes],
            "results": list(bet.results),
            "wagered": bet.wagered,
            "paid": bet.paid,
            "balance": bet.balance,
        }
        for bet in expected_result.bets[1:2]
    ]
    assert client.get(f"{uri}/runs/0/replay", params={"limit": 101}).status_code == 422
    assert client.get(f"{uri}/runs/1/replay").status_code == 404
    assert (
        client.post(
            "/api/v1/experiments",
            json={"request": json.loads(serialize_profile_request(request))},
            headers={"Origin": "http://localhost:8765"},
        ).status_code
        == 422
    )


@pytest.mark.parametrize("end_status", ["held", "failed"])
def test_profile_held_and_failed_are_incomplete_without_replay(profile_job, end_status):
    client, app, _, _, request = profile_job
    repo = app.state.repo
    identifier = repo.create_profile_experiment(request)
    if end_status == "held":
        repo.recover_jobs()
    else:
        repo.start_run(identifier, 0)
        repo.fail_run(identifier, 0)
        repo.fail_experiment_after_runs(identifier)
    uri = f"/api/v1/experiments/{identifier}"
    detail = client.get(uri).json()
    assert detail["status"] == end_status
    assert detail["request_kind"] == "profile"
    assert detail["runs"] == [
        {
            "ordinal": 0,
            "configuration_id": None,
            "status": "pending" if end_status == "held" else "failed",
            "result": None,
            "bets_count": 0,
            "result_kind": "profile",
        }
    ]
    assert client.get("/api/v1/experiments", params={"status": end_status}).json()["items"] == [
        detail
    ]
    assert client.get(f"{uri}/compare").json() == {
        "id": identifier,
        "status": end_status,
        "completed": 0,
        "requested": 1,
        "complete": False,
        "request_kind": "profile",
        "runs": detail["runs"],
    }
    assert client.get(f"{uri}/runs/0/replay").status_code == 409
    assert client.get(f"{uri}/runs/0/trajectory").status_code == 409


PROFILE_URL = "/api/v1/catalog/profiles"
RUN_URL = "/api/v1/experiments/profiles"
ORIGIN = {"Origin": "http://localhost:8765"}


def _post(client, path, body):
    return client.post(path, json=body, headers=ORIGIN)


def _imported_request(client, profile):
    raw = json.dumps([row(day=f"2025-09-0{day}", numbers=(0, 1, 2)) for day in (1, 2, 3)]).encode()
    body = import_payload(raw, profile=profile.model_dump(mode="json"))
    preview = _post(client, "/api/v1/imports/preview", body)
    assert preview.status_code == 200 and preview.json()["promotable"]
    promoted = _post(
        client,
        "/api/v1/imports/promote",
        {**body, "expected_dataset_sha256": preview.json()["dataset_sha256"]},
    )
    assert promoted.status_code == 200
    return replace(
        profile_request(profile),
        dataset_sha256=promoted.json()["dataset_sha256"],
        conditions=ProfileConditions(
            1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL, max_elapsed_draws=2
        ),
        selector=ProfileSelector(1, "static-numbers/v1", 2, numbers=(0, 1)),
    )


def test_public_registration_import_submission_and_completed_read(api_setup, monkeypatch):
    client, app, _ = api_setup
    profile = imported_profile(positions=3)
    original_register = app.state.repo.create_game_profile
    original_submit = app.state.jobs.submit_profile
    offloop = []

    def register(*args, **kwargs):
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        offloop.append("register")
        return original_register(*args, **kwargs)

    def submit(*args, **kwargs):
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        offloop.append("submit")
        return original_submit(*args, **kwargs)

    monkeypatch.setattr(app.state.repo, "create_game_profile", register)
    monkeypatch.setattr(app.state.jobs, "submit_profile", submit)
    registered = _post(client, PROFILE_URL, profile.model_dump(mode="json"))
    assert registered.status_code == 201
    assert registered.json()["profile"] == profile.model_dump(mode="json")
    assert registered.json()["profile_sha256"] == profile_sha256(profile)
    assert registered.json()["profile_execution"]["ready"] is True
    assert registered.json()["execution_supported"] is False
    assert registered.json()["profile_execution"]["requires_compatible_dataset"] is True
    request = _imported_request(client, profile)
    wire = json.loads(serialize_profile_request(request))
    created = _post(client, RUN_URL, wire)
    assert created.status_code == 201
    identifier = created.json()["id"]
    assert created.json() == {"id": identifier, "status": "pending"}
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if app.state.repo.get_experiment(identifier).status is ExperimentStatus.COMPLETED:
            break
        time.sleep(0.02)
    else:
        pytest.fail("profile job did not complete")
    assert offloop == ["register", "submit"]
    saved = app.state.repo.get_experiment(identifier)
    expected = replay(request, profile, app.state.repo.get_dataset(request.dataset_sha256))
    assert saved.runs[0].result == expected
    detail = client.get(f"/api/v1/experiments/{identifier}").json()
    assert detail["request"] == wire and detail["profile"] == profile.model_dump(mode="json")
    assert detail["request_kind"] == detail["runs"][0]["result_kind"] == "profile"
    assert client.get(f"/api/v1/experiments/{identifier}/compare").json()["complete"]
    assert (
        client.get(f"/api/v1/experiments/{identifier}/runs/0/replay").json()["total"]
        == expected.bet_draws
    )
    assert client.get("/api/v1/experiments").json()["items"][0] == detail


def test_dataset_detail_and_draws_use_verified_embedded_profile(api_setup, monkeypatch):
    client, app, _ = api_setup
    profile = imported_profile(positions=3)
    raw = json.dumps(
        [
            *(row(day=f"2025-09-0{day}", numbers=(0, 1, 2)) for day in (1, 2, 3)),
            row(day="2025-09-02", hour="05:15"),
        ],
        indent=2,
    ).encode()
    saved = app.state.repo.promote_dataset(raw, **options(positions=3)).dataset
    uri = f"/api/v1/datasets/{saved.dataset_sha256}"
    canonical_profile = profile.model_dump(mode="json")
    expected_digest = sha256(
        json.dumps(
            canonical_profile,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    assert profile_sha256(profile) == expected_digest
    before = client.get(uri)
    assert before.status_code == 200
    detail = before.json()
    assert detail == {
        **client.get("/api/v1/datasets").json()["items"][0],
        "profile": canonical_profile,
    }
    assert detail["profile_sha256"] == expected_digest
    assert detail["profile_execution"]["ready"] is False
    assert detail["execution_supported"] is False
    assert detail["records_total"] == 4
    assert detail["first_draw"] == "2025-09-01 05:10"
    assert detail["last_draw"] == "2025-09-03 05:10"
    assert detail["clock"] == {"mode": "naive_legacy", "zone": None}
    assert detail["source_id"] == "local-1" and detail["source_revision"] == "v1"
    assert saved.raw_bytes.decode() not in json.dumps(detail)
    assert saved.canonical_json.decode() not in json.dumps(detail)
    assert "records" not in detail and "provenance" not in json.dumps(detail)
    assert _post(client, PROFILE_URL, canonical_profile).json()["profile_sha256"] == expected_digest
    registered = client.get(uri).json()
    assert registered["profile"] == canonical_profile
    assert registered["profile_execution"]["ready"] is True
    assert client.get("/api/v1/datasets").json()["items"][0]["profile_execution"]["ready"]
    assert registered["execution_supported"] is False
    different = profile.model_copy(update={"maximum_stake": profile.maximum_stake + 1})
    monkeypatch.setattr(app.state.repo, "get_game_profile", lambda *_: different)
    assert client.get(uri).json()["profile_execution"]["ready"] is False
    assert client.get("/api/v1/datasets").json()["items"][0]["profile_execution"]["ready"] is False

    draws = f"{uri}/draws"
    labels = [
        "2025-09-01 05:10",
        "2025-09-02 05:10",
        "2025-09-02 05:15",
        "2025-09-03 05:10",
    ]
    assert client.get(draws, params={"limit": 2}).json() == {
        "total": 4,
        "offset": 0,
        "limit": 2,
        "items": labels[:2],
    }
    assert client.get(draws, params={"offset": 2, "limit": 1}).json() == {
        "total": 4,
        "offset": 2,
        "limit": 1,
        "items": labels[2:3],
    }
    assert client.get(draws, params={"limit": 100}).json()["items"] == labels
    assert client.get(draws, params={"date": "2025-09-02"}).json() == {
        "total": 2,
        "offset": 0,
        "limit": 100,
        "items": labels[1:3],
    }
    assert client.get(draws, params={"date": "2025-09-02", "offset": 1, "limit": 1}).json() == {
        "total": 2,
        "offset": 1,
        "limit": 1,
        "items": labels[2:3],
    }
    assert client.get(draws, params={"date": "2025-09-04"}).json()["items"] == []
    assert client.get(draws, params={"offset": 4}).json()["items"] == []
    for params in (
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"date": "2025-02-30"},
        {"date": "2025-9-02"},
    ):
        assert client.get(draws, params=params).status_code == 422
    for invalid in ("bad", "A" * 64, "a" * 63, "g" * 64):
        assert client.get(f"/api/v1/datasets/{invalid}").status_code == 422
        assert client.get(f"/api/v1/datasets/{invalid}/draws").status_code == 422
    for path in (f"/api/v1/datasets/{'f' * 64}", f"/api/v1/datasets/{'f' * 64}/draws"):
        assert client.get(path).status_code == 404
    monkeypatch.setattr(
        app.state.repo, "get_dataset", lambda *_: (_ for _ in ()).throw(ValueError("private"))
    )
    for path in (uri, draws):
        response = client.get(path)
        assert response.status_code == 409 and "private" not in response.text


def test_registration_strict_idempotent_conflict_quota_and_origin(api_setup):
    client, app, settings = api_setup
    profile = imported_profile(positions=3)
    body = profile.model_dump(mode="json")
    assert client.post(PROFILE_URL, json=body).status_code == 403
    assert (
        client.post(PROFILE_URL, json=body, headers={"Origin": "http://evil.example"}).status_code
        == 403
    )
    assert (
        client.post(PROFILE_URL, json=body, headers={**ORIGIN, "Host": "evil.example"}).status_code
        == 403
    )
    for invalid in (
        {**body, "unknown": 1},
        {**body, "minimum_stake": 1.0},
        {**body, "multipliers": [{"numerator": 2.0, "denominator": 1}] * 3},
    ):
        assert _post(client, PROFILE_URL, invalid).status_code == 422
    for raw in (
        b'{"profile_id":"x","profile_id":"y"}',
        b"NaN",
        b"[" * 65_537,
    ):
        response = client.post(PROFILE_URL, content=raw, headers=ORIGIN)
        assert response.status_code == (413 if len(raw) > 65_536 else 422)
    assert client.get(PROFILE_URL).json()["total"] == 1
    app.state.settings = replace(settings, quota_bytes=1, quota_explicit=True)
    assert _post(client, PROFILE_URL, body).status_code == 409
    assert client.get(PROFILE_URL).json()["total"] == 1
    app.state.settings = settings
    first = _post(client, PROFILE_URL, body)
    assert first.status_code == 201
    assert _post(client, PROFILE_URL, body).json() == first.json()
    assert client.get(PROFILE_URL).json()["total"] == 2
    conflict = _post(client, PROFILE_URL, {**body, "currency": "USD"})
    assert conflict.status_code == 409
    assert client.get(PROFILE_URL).json()["total"] == 2


def test_profile_submit_rejects_invalid_binding_affordability_and_queue_failure(
    api_setup, monkeypatch
):
    client, app, settings = api_setup
    profile = imported_profile(positions=3)
    request = _imported_request(client, profile)
    wire = json.loads(serialize_profile_request(request))
    assert client.post(RUN_URL, json=wire).status_code == 403
    assert (
        client.post(RUN_URL, json=wire, headers={"Origin": "http://evil.example"}).status_code
        == 403
    )
    assert (
        client.post(RUN_URL, json=wire, headers={**ORIGIN, "Host": "evil.example"}).status_code
        == 403
    )
    for invalid in (
        {**wire, "unknown": 1},
        {**wire, "conditions": {**wire["conditions"], "capital": 100.0}},
        {**wire, "selector": {**wire["selector"], "capability": "cold"}},
        {**wire, "entry_policy": "conditional-entry/v1"},
    ):
        assert _post(client, RUN_URL, invalid).status_code == 422
    for raw in (
        b'{"kind":"profile","kind":"legacy"}',
        b'{"conditions":{"capital":1,"capital":2}}',
        b"[" * 65_537,
    ):
        response = client.post(RUN_URL, content=raw, headers=ORIGIN)
        assert response.status_code == (413 if len(raw) > 65_536 else 422)
    for invalid in (
        wire,  # imported inline profile is not registered
        {**wire, "profile_sha256": "b" * 64},
        {**wire, "dataset_sha256": "b" * 64},
    ):
        assert _post(client, RUN_URL, invalid).status_code == 409
    assert _post(client, PROFILE_URL, profile.model_dump(mode="json")).status_code == 201
    mismatch = imported_profile(positions=3, revision=2)
    assert _post(client, PROFILE_URL, mismatch.model_dump(mode="json")).status_code == 201
    assert (
        _post(
            client,
            RUN_URL,
            {**wire, "profile_revision": 2, "profile_sha256": profile_sha256(mismatch)},
        ).status_code
        == 409
    )
    unaffordable = {**wire, "conditions": {**wire["conditions"], "capital": 1, "goal": 2}}
    assert _post(client, RUN_URL, unaffordable).status_code == 409
    assert app.state.repo.list_experiments() == []
    assert app.state.jobs.pending_ids() == ()
    app.state.jobs.settings = replace(settings, quota_bytes=1, quota_explicit=True)
    assert _post(client, RUN_URL, wire).status_code == 507
    app.state.jobs.settings = settings
    from laboratorio.storage.quota import QuotaExceeded

    monkeypatch.setattr(
        app.state.jobs,
        "enqueue",
        lambda _: (_ for _ in ()).throw(QuotaExceeded("queue quota")),
    )
    assert _post(client, RUN_URL, wire).status_code == 507
    assert app.state.repo.list_experiments() == []
    assert app.state.jobs.pending_ids() == ()
    monkeypatch.setattr(
        app.state.jobs,
        "submit_profile",
        lambda _: (_ for _ in ()).throw(RuntimeError("queue stopped")),
    )
    assert _post(client, RUN_URL, wire).status_code == 409
    assert app.state.repo.list_experiments() == []


def test_legacy_exact_http_fixture_unchanged(api_setup):
    client, app, _ = api_setup
    repo = app.state.repo
    identifier = repo.create_experiment(
        ExperimentRequest.model_validate(payload()),
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    repo.start_run(identifier, 0)
    repo.complete_run(identifier, 0, result())
    repo.complete_experiment(identifier)
    uri = f"/api/v1/experiments/{identifier}"
    expected_run = {
        "ordinal": 0,
        "configuration_id": None,
        "status": "completed",
        "result": {
            "outcome": "goal",
            "bets_count": 1,
            "wagered": 1,
            "paid": 80,
            "final_balance": 179,
            "delta": 79,
            "net": 79,
            "return_per_wagered": 80.0,
            "roi": 79.0,
            "max_drawdown": 0,
            "metric_scope": "saved_individual_run",
            "ratio_rounding": "decimal-half-up-6",
        },
        "bets_count": 1,
    }
    expected = {
        "id": identifier,
        "status": "completed",
        "created_at": repo.get_experiment(identifier).created_at,
        "request": payload(),
        "profile": repo.get_experiment(identifier).profile.model_dump(mode="json"),
        "sources": {
            "history_id": "history",
            "history_sha256": "a" * 64,
            "rankings_id": "rankings",
            "rankings_sha256": "b" * 64,
            "code_version": "v1",
        },
        "runs": [expected_run],
    }
    assert client.get(uri).json() == expected
    assert client.get("/api/v1/experiments", params={"limit": 1}).json()["items"] == [expected]
    assert client.get(f"{uri}/compare").json() == {
        "id": identifier,
        "status": "completed",
        "completed": 1,
        "requested": 1,
        "complete": True,
        "runs": [expected_run],
    }
    assert client.get(f"{uri}/runs/0/replay").json() == {
        "total": 1,
        "offset": 0,
        "limit": 20,
        "items": [
            {
                "label": "2025-01-01 05:10",
                "numbers": [7],
                "per_number": 1,
                "wagered": 1,
                "results": [7, 8, 9, 10, 11],
                "paid": 80,
                "balance": 179,
            }
        ],
    }


def test_private_cycling_public_reads_and_queue_start_refuse_without_leaking(api_setup):
    client, app, _ = api_setup
    repo = app.state.repo
    profile = legacy_quiniela_80_profile()
    raw = json.dumps(
        [row(numbers=(0, 1, 2, 3, 4), day=f"2025-09-0{day}") for day in (1, 2, 3)]
    ).encode()
    dataset = repo.promote_dataset(raw, **options(positions=5, profile=profile)).dataset
    request = ProfileCyclingRequest(
        "profile",
        2,
        "Private cycling",
        dataset.dataset_sha256,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        ProfileConditions(1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(7,)),
        Q80CyclingStaking(),
        "all_rows/v1",
    )
    identifier = repo.create_profile_cycling_experiment(request)
    # Pending v2 is a truthful public snapshot, not a fabricated completed result.
    v1 = repo.create_experiment(
        ExperimentRequest.model_validate(payload()),
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    listing = client.get("/api/v1/experiments", params={"limit": 1}).json()
    assert listing["total"] == 2
    assert listing["items"][0]["id"] in (v1, identifier)
    assert {item["id"] for item in client.get("/api/v1/experiments").json()["items"]} == {
        v1,
        identifier,
    }
    detail = client.get(f"/api/v1/experiments/{identifier}").json()
    assert detail["status"] == "pending" and detail["runs"][0]["result"] is None
    assert client.get(f"/api/v1/experiments/{identifier}/runs/0/replay").status_code == 409
    repo.recover_jobs()
    assert client.get("/api/v1/queue").json()["held"]["total"] == 2
    assert client.get(f"/api/v1/experiments/{identifier}").json()["status"] == "held"
    response = _post(client, f"/api/v1/queue/{identifier}/cancel", {})
    assert response.status_code == 200
    assert repo.get_experiment(identifier).status is ExperimentStatus.CANCELLED


def test_public_cycling_submit_spawn_replay_and_rejection_before_rows(api_setup):
    client, app, _ = api_setup
    repo = app.state.repo
    profile = legacy_quiniela_80_profile()
    dataset = repo.promote_dataset(
        json.dumps(
            [row(numbers=(0, 1, 2, 3, 4), day=f"2025-09-0{day}") for day in (1, 2, 3)]
        ).encode(),
        **options(positions=5, profile=profile),
    ).dataset
    request = ProfileCyclingRequest(
        "profile",
        2,
        "Public cycling",
        dataset.dataset_sha256,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        ProfileConditions(1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(7,)),
        Q80CyclingStaking(),
        "all_rows/v1",
    )
    wire = json.loads(serialize_profile_cycling_request(request))
    assert (
        "q80-first-prize-cycling/v1"
        in next(
            item
            for item in client.get(PROFILE_URL).json()["items"]
            if item["profile"]["profile_id"] == profile.profile_id
        )["profile_execution"]["staking_capabilities"]
    )
    for invalid, expected in (
        ({**wire, "schema_version": 3}, 422),
        ({**wire, "staking": {**wire["staking"], "per_number_stake": 1}}, 422),
        (
            {
                **wire,
                "conditions": {**wire["conditions"], "capital": 1, "goal": 2},
                "selector": {**wire["selector"], "coverage": 2, "numbers": [7, 8]},
            },
            409,
        ),
        (
            {**wire, "selector": {**wire["selector"], "coverage": 80, "numbers": list(range(80))}},
            409,
        ),
    ):
        assert _post(client, RUN_URL, invalid).status_code == expected
    assert (
        client.post(
            RUN_URL, content=b'{"schema_version":2,"schema_version":1}', headers=ORIGIN
        ).status_code
        == 422
    )
    assert client.post(RUN_URL, content=b"[" * 65_537, headers=ORIGIN).status_code == 413
    assert client.post(RUN_URL, json=wire).status_code == 403
    assert _post(client, RUN_URL, {**wire, "profile_sha256": "b" * 64}).status_code == 409
    other = imported_profile(positions=3)
    assert _post(client, PROFILE_URL, other.model_dump(mode="json")).status_code == 201
    assert (
        "q80-first-prize-cycling/v1"
        not in next(
            item
            for item in client.get(PROFILE_URL).json()["items"]
            if item["profile"]["profile_id"] == other.profile_id
        )["profile_execution"]["staking_capabilities"]
    )
    assert (
        _post(
            client,
            RUN_URL,
            {
                **wire,
                "profile_id": other.profile_id,
                "profile_revision": other.revision,
                "profile_sha256": profile_sha256(other),
            },
        ).status_code
        == 409
    )
    assert repo.list_experiments() == [] and app.state.jobs.pending_ids() == ()
    with patch.object(
        app.state.jobs, "_enqueue_profile_cycling", side_effect=QuotaExceeded("queue quota")
    ):
        assert _post(client, RUN_URL, wire).status_code == 507
    assert repo.list_experiments() == [] and app.state.jobs.pending_ids() == ()
    created = _post(client, RUN_URL, wire)
    assert created.status_code == 201
    identifier = created.json()["id"]
    assert created.json()["status"] == "pending"
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if repo.get_experiment(identifier).status is ExperimentStatus.COMPLETED:
            break
        time.sleep(0.02)
    else:
        pytest.fail("public cycling job did not complete")
    detail = client.get(f"/api/v1/experiments/{identifier}").json()
    assert detail["request"] == wire and detail["runs"][0]["result"]["schema_version"] == 2
    replay_page = client.get(f"/api/v1/experiments/{identifier}/runs/0/replay").json()
    assert replay_page["schema_version"] == 2
    trajectory = client.get(f"/api/v1/experiments/{identifier}/runs/0/trajectory")
    assert trajectory.status_code == 200 and trajectory.json()["schema_version"] == 2


def test_completed_cycling_public_read_projection_and_visibility(api_setup):
    client, app, _ = api_setup
    repo = app.state.repo
    profile = legacy_quiniela_80_profile()
    dataset = repo.promote_dataset(
        json.dumps(
            [row(numbers=(0, 1, 2, 3, 4), day=f"2025-09-0{day}") for day in (1, 2, 3)]
        ).encode(),
        **options(positions=5, profile=profile),
    ).dataset
    request = ProfileCyclingRequest(
        "profile",
        2,
        "Cycling visible",
        dataset.dataset_sha256,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        ProfileConditions(1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(7,)),
        Q80CyclingStaking(),
        "all_rows/v1",
    )
    pending = repo.create_profile_cycling_experiment(request)
    identifier = repo.create_profile_cycling_experiment(request)
    repo.start_run(identifier, 0)
    result = cycling_result(request, profile, dataset)
    repo.complete_profile_cycling_run(identifier, 0, result)
    repo.complete_experiment(identifier)
    uri = f"/api/v1/experiments/{identifier}"
    detail = client.get(uri)
    assert detail.status_code == 200
    body = detail.json()
    assert body["request"] == json.loads(serialize_profile_cycling_request(request))
    assert body["request"]["staking"] == {
        "schema_version": 1,
        "capability": "q80-first-prize-cycling/v1",
    }
    assert "dinámica" in body["display"]["staking_label"]
    expected = json.loads(serialize_profile_cycling_result(result))
    session = result.session
    assert body["runs"][0] == {
        "ordinal": 0,
        "configuration_id": None,
        "status": "completed",
        "result_kind": "profile",
        "bets_count": session.bet_draws,
        "result": {
            **{key: value for key, value in expected.items() if key not in ("bets", "kind")},
            "delta": session.final_balance - request.conditions.capital,
            **financial_metrics(session, request.conditions.capital),
        },
    }
    assert client.get(f"{uri}/compare").json() == {
        "id": identifier,
        "status": "completed",
        "request_kind": "profile",
        "completed": 1,
        "requested": 1,
        "complete": True,
        "runs": body["runs"],
    }
    assert client.get(f"{uri}/runs/0/replay", params={"offset": 0, "limit": 1}).json() == {
        "result_kind": "profile",
        "schema_version": 2,
        "total": session.bet_draws,
        "offset": 0,
        "limit": 1,
        "items": expected["bets"][:1],
    }
    second = client.get(f"{uri}/runs/0/replay", params={"offset": 1, "limit": 1})
    assert second.json()["items"] == expected["bets"][1:2]
    assert client.get(f"{uri}/runs/1/replay").status_code == 404
    assert repo.search_experiments(0, 10, name_contains="Cycling")[0] == 0
    _, visible = repo.search_experiments(
        0, 10, name_contains="Cycling", include_completed_cycling=True
    )
    assert {row.id for row in visible} == {identifier, pending}
    page = client.get("/api/v1/experiments", params={"name_contains": "Cycling", "limit": 1}).json()
    assert page["total"] == 2 and page["items"][0] == body
    next_page = client.get(
        "/api/v1/experiments", params={"name_contains": "Cycling", "offset": 1, "limit": 1}
    )
    assert next_page.json()["items"][0]["id"] == pending
    assert client.get(f"/api/v1/experiments/{pending}").json()["runs"][0]["result"] is None
    assert client.get(f"/api/v1/experiments/{pending}/runs/0/replay").status_code == 409
    for status in ("held", "running", "failed"):
        with sqlite3.connect(repo.path) as db:
            db.execute("UPDATE experiments SET status = ? WHERE id = ?", (status, pending))
        refused = client.get(
            "/api/v1/experiments", params={"status": status, "name_contains": "Cycling"}
        )
        assert refused.json()["total"] == 1
        assert client.get(f"/api/v1/experiments/{pending}").json()["status"] == status
        assert client.get(f"/api/v1/experiments/{pending}/runs/0/replay").status_code == 409


def test_public_audaz_post_has_truthful_detail_list_and_replay(profile_job):
    from laboratorio.domain.profile_request_v3 import (
        ProfileAudazRequest,
        serialize_profile_audaz_request,
    )
    from laboratorio.domain.profile_session import ProfileSelector
    from laboratorio.domain.profile_staking import ProfileAudazStaking

    client, app, profile, dataset, request = profile_job
    app.state.repo.create_game_profile(profile)
    audaz = ProfileAudazRequest(
        "profile",
        3,
        "Audaz public",
        dataset.dataset_sha256,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        request.conditions,
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(0,)),
        ProfileAudazStaking(),
        "all_rows/v1",
    )
    created = _post(client, RUN_URL, json.loads(serialize_profile_audaz_request(audaz)))
    assert created.status_code == 201
    identifier = created.json()["id"]
    detail_url = f"/api/v1/experiments/{identifier}"
    detail = client.get(detail_url)
    assert detail.status_code == 200
    body = detail.json()
    assert body["request"]["schema_version"] == 3
    assert body["display"]["staking_label"] == "Audaz · apuesta dinámica por sorteo"
    assert body["status"] in ("pending", "running", "completed")
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        detail = client.get(detail_url)
        assert "status" in detail.json(), f"detail {detail.status_code}: {detail.text}"
        if detail.json()["status"] == "completed":
            break
        time.sleep(0.02)
    assert detail.status_code == 200 and detail.json()["status"] == "completed"
    listed = client.get("/api/v1/experiments", params={"name_contains": "Audaz public"})
    assert listed.status_code == 200 and listed.json()["items"] == [detail.json()]
    replay_page = client.get(f"{detail_url}/runs/0/replay")
    assert replay_page.status_code == 200
    assert replay_page.json()["result_kind"] == "profile"
    assert replay_page.json()["schema_version"] == 3
    assert replay_page.json()["total"] == detail.json()["runs"][0]["bets_count"]
    trajectory = client.get(f"{detail_url}/runs/0/trajectory")
    assert trajectory.status_code == 200 and trajectory.json()["schema_version"] == 3

    before = app.state.repo.search_experiments(0, 100, name_contains="Audaz public")[0]
    incompatible = ProfileAudazRequest(
        "profile",
        3,
        "Audaz incompatible",
        dataset.dataset_sha256,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        request.conditions,
        ProfileSelector(1, "static-numbers/v1", 2, numbers=(0, 1)),
        ProfileAudazStaking(),
        "all_rows/v1",
    )
    rejected = _post(client, RUN_URL, json.loads(serialize_profile_audaz_request(incompatible)))
    assert rejected.status_code == 409
    assert app.state.repo.search_experiments(0, 100, name_contains="Audaz public")[0] == before


def test_public_schema4_recovery_submission_worker_and_truthful_reads(api_setup):
    from laboratorio.domain.profile_request_v4 import (
        ProfileRecoveryRequest,
        serialize_profile_recovery_request,
    )
    from laboratorio.domain.profile_staking import ProfileRecoveryLadderStaking

    client, app, _ = api_setup
    profile = imported_profile(positions=3)
    base = _imported_request(client, profile)
    app.state.repo.create_game_profile(profile)
    request = ProfileRecoveryRequest(
        "profile",
        4,
        "Recovery API",
        base.dataset_sha256,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        base.conditions,
        replace(base.selector, coverage=1, numbers=(0,)),
        ProfileRecoveryLadderStaking(2, 3, "cycle"),
        "all_rows/v1",
    )
    response = _post(client, RUN_URL, json.loads(serialize_profile_recovery_request(request)))
    assert response.status_code == 201
    identifier = response.json()["id"]
    deadline = time.monotonic() + 15
    detail = client.get(f"/api/v1/experiments/{identifier}")
    while detail.status_code == 200 and detail.json()["status"] in ("pending", "running"):
        if time.monotonic() >= deadline:
            pytest.fail("schema-4 recovery job did not finish")
        time.sleep(0.02)
        detail = client.get(f"/api/v1/experiments/{identifier}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["request"]["schema_version"] == 4
    assert body["request"]["staking"] == {
        "schema_version": 1,
        "target_margin": 2,
        "rounds": 3,
        "end_mode": "cycle",
    }
    assert body["display"]["currency"] == profile.currency
    assert body["display"]["scale"] == profile.scale
    assert body["display"]["staking_label"].startswith("Escalera de recuperación")
    assert body["runs"][0]["result"]["schema_version"] == 4
    listing = client.get("/api/v1/experiments", params={"name_contains": "Recovery API"})
    assert listing.json()["items"] == [body]
    assert client.get(f"/api/v1/experiments/{identifier}/compare").json()["complete"] is True
    replay = client.get(f"/api/v1/experiments/{identifier}/runs/0/replay").json()
    assert replay["schema_version"] == 4 and replay["result_kind"] == "profile"
    trajectory = client.get(f"/api/v1/experiments/{identifier}/runs/0/trajectory")
    assert trajectory.status_code == 200 and trajectory.json()["schema_version"] == 4


def test_public_schema4_stop_persists_round_limit_and_replays(api_setup):
    from laboratorio.domain.profile_request_v4 import (
        ProfileRecoveryRequest,
        serialize_profile_recovery_request,
    )
    from laboratorio.domain.profile_staking import ProfileRecoveryLadderStaking

    client, app, _ = api_setup
    profile = imported_profile(positions=3)
    base = _imported_request(client, profile)
    app.state.repo.create_game_profile(profile)
    request = ProfileRecoveryRequest(
        "profile",
        4,
        "Recovery stop",
        base.dataset_sha256,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        base.conditions,
        replace(base.selector, coverage=1, numbers=(4,)),
        ProfileRecoveryLadderStaking(2, 1, "stop"),
        "all_rows/v1",
    )
    response = _post(client, RUN_URL, json.loads(serialize_profile_recovery_request(request)))
    assert response.status_code == 201, response.text
    identifier = response.json()["id"]
    deadline = time.monotonic() + 15
    while True:
        detail = client.get(f"/api/v1/experiments/{identifier}")
        assert detail.status_code == 200
        if detail.json()["status"] not in ("pending", "running"):
            break
        if time.monotonic() >= deadline:
            pytest.fail("schema-4 recovery stop job did not finish")
        time.sleep(0.02)
    body = detail.json()
    assert body["status"] == "completed"
    assert body["runs"][0]["result"]["outcome"] == "limit"
    assert body["runs"][0]["result"]["collisions"] == ["recovery_round_limit"]
    replay = client.get(f"/api/v1/experiments/{identifier}/runs/0/replay")
    assert replay.status_code == 200
    assert replay.json()["schema_version"] == 4


@pytest.mark.parametrize("kind", ["legacy", "profile"])
def test_common_run_read_boundary_retains_resultless_native_envelope(kind):
    run = SavedRun(7, "persisted-configuration", RunStatus.PENDING, None, kind, None)
    summary = run_summary(run, 100)
    expected = {
        "ordinal": 7,
        "configuration_id": "persisted-configuration",
        "status": "pending",
        "result": None,
        "bets_count": 0,
    }
    if kind == "profile":
        expected["result_kind"] = "profile"
    assert json.loads(json.dumps(summary)) == expected
    assert "result_schema_version" not in summary and "complete" not in summary


def test_common_run_read_boundary_keeps_legacy_result_and_count_native():
    native = result()
    before = asdict(native)
    run = SavedRun(9, "saved-configuration", RunStatus.COMPLETED, native)
    summary = run_summary(run, 100)
    assert summary == {
        "ordinal": 9,
        "configuration_id": "saved-configuration",
        "status": RunStatus.COMPLETED,
        "result": {
            **{key: value for key, value in before.items() if key != "bets"},
            "delta": native.final_balance - 100,
            **financial_metrics(native, 100),
        },
        "bets_count": len(native.bets),
    }
    assert run.result is native and asdict(native) == before
    assert "strategy" not in summary and "source_count" not in summary["result"]
