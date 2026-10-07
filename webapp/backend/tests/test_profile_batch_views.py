"""Read projections for persisted profile batch v5 sessions."""

# Contract traceability:
# B-API-101: test_completed_v5_detail_list_and_replay_project_saved_session
# B-API-102: test_v5_stop_reasons_distinguish_budget_goal_and_source_end
# B-API-103: test_v5_resultless_runs_have_no_financial_claims
# B-API-104: test_v5_saved_source_identity_corruption_is_conflict
# B-API-105: test_corrupt_v5_saved_dataset_is_conflict_for_replay_and_trajectory
# B-API-106: test_corrupt_v5_admission_is_conflict_not_server_error
# B-API-108..110: strategy API behavior remains covered by the strategy-library
#   startup/pagination/retrieval and stored-corruption tests in test_strategy_library.py.

import json
import sqlite3
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from test_api import CatalogStub
from test_batch_admission import _saved_inputs

from laboratorio.api.profile_views import BatchRunContext, _stop, run_summary, v5_run_summary
from laboratorio.app import create_app
from laboratorio.domain.batch_admission import admit_profile_batch
from laboratorio.domain.contracts import RunStatus
from laboratorio.domain.profile_session import ProfileOutcome
from laboratorio.domain.profile_session_v5 import run_profile_batch_v5
from laboratorio.settings import Settings
from laboratorio.storage.repository import SavedRun


def _completed_v5(client, *, name="Read V5", max_draws=2):
    app = client.app
    settings = app.state.settings
    repo = app.state.repo
    _, _, _, _, submission = _saved_inputs(repo, row_count=4)
    conditions = replace(
        submission.conditions,
        start_draw="2025-09-03 05:10",
        max_elapsed_draws=max_draws,
    )
    submission = replace(
        submission,
        conditions=conditions,
        max_draws=max_draws,
        client_request_id=name,
    )
    identifier = admit_profile_batch(repo, submission)
    saved = repo.get_experiment(identifier)
    dataset = repo.get_dataset(submission.dataset_sha256)
    assert saved is not None and dataset is not None
    repo.start_run(identifier, 0)
    result = run_profile_batch_v5(
        saved.request, saved.profile, dataset, None, operation_budget=max_draws
    )
    repo.complete_profile_batch_run(identifier, 0, result, settings=settings)
    repo.complete_experiment(identifier)
    return app, identifier, submission


def test_completed_v5_detail_list_and_replay_project_saved_session(tmp_path, monkeypatch):
    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    app = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(app, base_url="http://localhost:8765") as client:
        _, identifier, request = _completed_v5(client)
        monkeypatch.setattr(
            "laboratorio.domain.profile_session_v5.run_profile_batch_v5",
            lambda *args, **kwargs: pytest.fail("recalculated during read projection"),
        )
        saved = app.state.repo.get_experiment(identifier)
        assert saved is not None
        native_result = saved.runs[0].result
        admission = saved.batch_admission
        assert admission is not None
        projected = run_summary(
            saved.runs[0],
            saved.request.conditions.capital,
            batch_context=BatchRunContext(
                admission["source_identity"]["row_count"],
                admission["requested_constraints"],
                admission["effective_constraints"],
                admission["strategy_refs"][0],
            ),
        )
        path = f"/api/v1/experiments/{identifier}"
        detail = client.get(path)
        assert detail.status_code == 200
        body = detail.json()
        assert body["request_schema_version"] == 5
        assert body["runs"][0]["result"]["schema_version"] == 5
        run = body["runs"][0]
        assert json.loads(json.dumps(projected)) == run
        assert saved.runs[0].result is native_result
        assert body["display"]["currency"] == saved.profile.currency
        assert body["display"]["scale"] == saved.profile.scale
        assert run["bets_count"] == len(native_result.results[0].session.bets)
        assert run["result"]["definition_name"] == "Static low risk"
        assert run["result"]["metric_scope"] == "saved_individual_run"
        assert run["result"]["start_draw_index"] == 1
        assert run["result"]["prior_cutoff"] == "2025-09-02 05:10"
        assert run["result"]["stop_category"] == "configured_limit"
        assert body["batch_admission"]["source_identity"]["row_count"] == 4
        listing = client.get(
            "/api/v1/experiments", params={"name_contains": request.client_request_id}
        ).json()
        assert listing["items"] == [body]
        replay = client.get(f"{path}/runs/0/replay", params={"offset": 1, "limit": 1})
        assert replay.status_code == 200
        assert replay.json()["items"][0]["source_index"] == 2
        assert replay.json()["items"][0]["bet_index"] == 1
        trajectory = client.get(f"{path}/runs/0/trajectory").json()
        assert trajectory["result_kind"] == "profile"
        assert trajectory["schema_version"] == 5
        assert all(point["source_index"] >= 1 for point in trajectory["points"])
        assert all(
            point["bet_index"] + 1 == point["source_index"] for point in trajectory["points"]
        )


def test_v5_stop_reasons_distinguish_budget_goal_and_source_end():
    requested = {"max_elapsed_draws": 100}
    effective = {"max_elapsed_draws": 10}
    assert _stop(
        ProfileOutcome.LIMIT,
        ("max_elapsed_draws",),
        10,
        5,
        40,
        requested,
        effective,
    ) == ("operational_budget", "max_elapsed_draws", False)
    assert _stop(ProfileOutcome.HISTORY_EXHAUSTED, (), 30, 10, 40, requested, effective) == (
        "source_end",
        "full saved source ended",
        True,
    )
    assert (
        _stop(ProfileOutcome.GOAL, ("max_elapsed_draws",), 10, 5, 40, requested, effective)[0]
        == "financial_goal"
    )


@pytest.mark.parametrize(
    ("status", "category"),
    [(RunStatus.FAILED, "unknown"), (RunStatus.CANCELLED, "interrupted")],
)
def test_v5_resultless_runs_have_no_financial_claims(status, category):
    run = SavedRun(2, None, status, None, "profile", None)
    summary = v5_run_summary(
        run,
        100,
        40,
        {"max_draws": 10},
        {"max_draws": 10},
        {"id": "strategy-id", "revision": 2, "definition_sha256": "a" * 64},
    )
    assert summary["ordinal"] == 2
    assert summary["result"] is None
    assert summary["stop_category"] == category
    assert summary["complete"] is False
    assert "roi" not in summary
    context = BatchRunContext(
        40,
        {"max_draws": 10},
        {"max_draws": 10},
        {"id": "strategy-id", "revision": 2, "definition_sha256": "a" * 64},
    )
    assert run_summary(run, 100, batch_context=context) == summary
    assert list(summary) == [
        "ordinal",
        "configuration_id",
        "status",
        "result_kind",
        "result_schema_version",
        "strategy",
        "result",
        "bets_count",
        "complete",
        "completion",
        "stop_category",
        "stop_reason",
        "stop_code",
        "error",
    ]
    assert summary == {
        "ordinal": 2,
        "configuration_id": None,
        "status": status.value,
        "result_kind": "profile",
        "result_schema_version": None,
        "strategy": {**context.strategy_ref, "name": None},
        "result": None,
        "bets_count": 0,
        "complete": False,
        "completion": "unavailable",
        "stop_category": category,
        "stop_reason": status.value,
        "stop_code": "unknown",
        "error": None,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("row_count", 3),
        ("source_sha256", "f" * 64),
        ("canonical_sha256", "e" * 64),
    ],
)
def test_v5_saved_source_identity_corruption_is_conflict(tmp_path, field, value):
    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    app = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(app, base_url="http://localhost:8765", raise_server_exceptions=False) as client:
        _, identifier, submission = _completed_v5(client, name=f"Corrupt {field}")
        with sqlite3.connect(app.state.repo.path) as db:
            row = db.execute(
                "SELECT source_identity_json FROM profile_batch_admissions WHERE experiment_id = ?",
                (identifier,),
            ).fetchone()
            identity = json.loads(row[0])
            identity[field] = value
            db.execute("DROP TRIGGER profile_batch_admissions_no_update")
            db.execute(
                "UPDATE profile_batch_admissions SET source_identity_json = ? "
                "WHERE experiment_id = ?",
                (json.dumps(identity, separators=(",", ":")), identifier),
            )

        path = f"/api/v1/experiments/{identifier}"
        assert submission.conditions.start_draw == "2025-09-03 05:10"
        assert client.get(path).status_code == 409
        listing = client.get("/api/v1/experiments", params={"name_contains": f"Corrupt {field}"})
        assert listing.status_code == 409
        assert client.get(f"{path}/compare").status_code == 409


def test_corrupt_v5_saved_dataset_is_conflict_for_replay_and_trajectory(tmp_path):
    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    app = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(app, base_url="http://localhost:8765", raise_server_exceptions=False) as client:
        _, identifier, submission = _completed_v5(client, name="Corrupt dataset")
        with sqlite3.connect(app.state.repo.path) as db:
            db.execute("DROP TRIGGER datasets_no_update")
            db.execute(
                "UPDATE datasets SET raw_bytes = X'00' WHERE dataset_sha256 = ?",
                (submission.dataset_sha256,),
            )
        path = f"/api/v1/experiments/{identifier}/runs/0"
        assert client.get(f"{path}/replay").status_code == 409
        assert client.get(f"{path}/trajectory").status_code == 409


def test_corrupt_v5_admission_is_conflict_not_server_error(tmp_path, monkeypatch):
    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    app = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(app, base_url="http://localhost:8765") as client:
        _, identifier, _ = _completed_v5(client, name="Corrupt V5")

        def corrupted_snapshot(_):
            raise ValueError("corrupt saved batch admission")

        monkeypatch.setattr(app.state.repo, "get_experiment", corrupted_snapshot)
        response = client.get(f"/api/v1/experiments/{identifier}")
        assert response.status_code == 409
