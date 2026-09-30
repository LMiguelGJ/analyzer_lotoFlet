"""HTTP contract, isolation and lifecycle tests against temporary storage."""

import sqlite3
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from laboratorio.domain.contracts import (
    Conditions,
    ExperimentRequest,
    ExperimentStatus,
    Outcome,
    SelectorKind,
    StakingStyle,
    Strategy,
)
from laboratorio.domain.session import Bet, SessionResult
from laboratorio.jobs.queue import JobQueue, QueueFailure
from laboratorio.settings import Settings
from laboratorio.storage.quota import QuotaExceeded


def strategy(name="Cold"):
    return Strategy(
        name=name,
        selector=SelectorKind.SYSTEM,
        system="cold",
        coverage=1,
        staking=StakingStyle.FLAT,
    )


def payload():
    return ExperimentRequest(
        name="Trial",
        conditions=Conditions(start_draw="2025-01-01 05:10", capital=100, goal=200, seed=42),
        strategies=(strategy(),),
    ).model_dump(mode="json")


class CatalogStub:
    def __init__(self):
        self.history = SimpleNamespace(
            labels=("2025-01-01 05:10", "2025-01-01 05:15"), sha256="a" * 64
        )
        self.rankings = SimpleNamespace(row_ids=(0,), path="rankings.npz")


@pytest.fixture
def setup(tmp_path):
    from laboratorio.app import create_app

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    app = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(app, base_url="http://localhost:8765") as client:
        yield client, app, settings


def post(client, path, body=None):
    return client.post(path, json=body, headers={"Origin": "http://localhost:8765"})


def test_catalog_and_create_read_without_recalculation(setup, monkeypatch):
    client, _, _ = setup
    catalog = client.get("/api/v1/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["starting_draws"] == ["2025-01-01 05:10"]
    assert catalog.json()["coverages"] == [1, 5, 10, 20, 25, 30, 40, 50]
    monkeypatch.setattr(
        "laboratorio.domain.session.run_session", lambda *a: pytest.fail("recalculated")
    )
    created = post(client, "/api/v1/experiments", {"request": payload()})
    assert created.status_code == 201
    identifier = created.json()["id"]
    assert client.get(f"/api/v1/experiments/{identifier}").json()["request"] == payload()
    assert client.get("/api/v1/experiments").json()["total"] == 1
    assert client.get("/api/v1/experiments?offset=-1").status_code == 422
    assert client.get("/api/v1/experiments?limit=101").status_code == 422


def test_experiment_search_filters_orders_paginates_and_serializes_created_at(setup):
    from datetime import datetime

    client, app, _ = setup
    repo = app.state.repo
    ids = {}
    for name in ("Beta%", "Alpha", "beta_", "Gamma"):
        ids[name] = repo.create_experiment(
            ExperimentRequest.model_validate({**payload(), "name": name}),
            history_id="h",
            history_sha256="a" * 64,
            rankings_id="r",
            rankings_sha256="b" * 64,
            code_version="v1",
        )
    repo.finish_incomplete(ids["Beta%"], ExperimentStatus.CANCELLED)
    page = client.get(
        "/api/v1/experiments",
        params={"name_contains": "BETA", "sort": "name", "order": "desc", "limit": 1},
    )
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert page.json()["items"][0]["id"] == ids["beta_"]
    filtered = client.get(
        "/api/v1/experiments",
        params={"name_contains": "%", "status": "cancelled", "offset": 0, "limit": 1},
    ).json()
    assert filtered["total"] == 1 and [item["id"] for item in filtered["items"]] == [ids["Beta%"]]
    assert client.get("/api/v1/experiments", params={"name_contains": "_"}).json()["total"] == 1
    detail = client.get(f"/api/v1/experiments/{ids['Alpha']}").json()
    assert page.json()["items"][0]["created_at"] is not None
    created_at = datetime.fromisoformat(detail["created_at"].replace("Z", "+00:00"))
    utc_offset = created_at.utcoffset()
    assert utc_offset is not None and utc_offset.total_seconds() == 0
    assert client.get("/api/v1/experiments", params={"status": "completed"}).json()["total"] == 0
    by_status = client.get("/api/v1/experiments", params={"sort": "status", "order": "asc"})
    assert by_status.json()["items"][0]["id"] == ids["Beta%"]
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE experiments SET created_at = NULL WHERE id = ?", (ids["Alpha"],))
    assert client.get(f"/api/v1/experiments/{ids['Alpha']}").json()["created_at"] is None
    newest = client.get("/api/v1/experiments", params={"limit": 4}).json()
    assert newest["items"][-1]["id"] == ids["Alpha"]
    assert newest["items"][-1]["created_at"] is None
    beyond = client.get("/api/v1/experiments", params={"offset": 20, "status": "pending"})
    assert beyond.json()["total"] == 3 and beyond.json()["items"] == []
    for params in (
        {"sort": "request_json"},
        {"order": "sideways"},
        {"status": "goal"},
        {"limit": 101},
        {"offset": -1},
        {"name_contains": "x" * 81},
    ):
        assert client.get("/api/v1/experiments", params=params).status_code == 422, params


def test_max_safe_seed_round_trips_exactly_through_create_and_get(setup):
    client, _, _ = setup
    max_safe_seed = 2**53 - 1
    data = payload()
    data["conditions"]["seed"] = max_safe_seed
    created = post(client, "/api/v1/experiments", {"request": data})
    assert created.status_code == 201
    identifier = created.json()["id"]
    detail = client.get(f"/api/v1/experiments/{identifier}")
    assert detail.json()["request"]["conditions"]["seed"] == max_safe_seed
    over_limit = payload()
    over_limit["conditions"]["seed"] = max_safe_seed + 1
    assert post(client, "/api/v1/experiments", {"request": over_limit}).status_code == 422


def test_seed_rejects_string_and_float_with_field_loc(setup):
    client, _, _ = setup
    for bad_seed in ("9007199254740991", 9007199254740991.0):
        data = payload()
        data["conditions"]["seed"] = bad_seed
        response = post(client, "/api/v1/experiments", {"request": data})
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "request", "conditions", "seed"]


def test_duplicate_strategy_name_error_is_field_located_not_root(setup):
    client, _, _ = setup
    data = payload()
    data["strategies"] = [
        {**data["strategies"][0], "name": "Una"},
        {**data["strategies"][0], "name": "una"},
    ]
    response = post(client, "/api/v1/experiments", {"request": data})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert len(detail) == 1
    assert detail[0]["loc"] == ["body", "request", "strategies", 1, "name"]


def test_invalid_payload_and_start(setup):
    client, _, _ = setup
    for change in (
        lambda data: data["conditions"].update(goal=100),
        lambda data: data["conditions"].update(start_draw="bad"),
        lambda data: data["conditions"].update(max_bets=0),
        lambda data: data["conditions"].update(max_minutes=-1),
        lambda data: data["strategies"][0].update(coverage=3),
        lambda data: data.update(extra="forbidden"),
        lambda data: data.update(strategies=data["strategies"] * 6),
        lambda data: data["strategies"][0].update(
            selector="blend",
            system=None,
            components=[{"system": "cold", "weight": 50}, {"system": "decay", "weight": 49}],
        ),
    ):
        data = payload()
        change(data)
        assert post(client, "/api/v1/experiments", {"request": data}).status_code == 422
    data = payload()
    data["conditions"]["start_draw"] = "2025-01-01 05:15"
    assert post(client, "/api/v1/experiments", {"request": data}).status_code == 400
    response = post(client, "/api/v1/experiments", {"request": payload(), "unexpected": True})
    assert response.status_code == 422


def test_host_origin_guard(setup):
    client, _, _ = setup
    for host in (
        "evil.example",
        "localhost.evil.example",
        "127.0.0.1:9999",
        "localhost:8765@evil",
        "localhost:8765,evil",
        "[::1]:8765",
    ):
        response = client.get("/api/v1/catalog", headers={"Host": host})
        assert response.status_code == 403, host
    body = {"name": "Saved", "strategy": strategy().model_dump(mode="json")}
    for origin in (
        "https://localhost:8765",
        "http://evil.example",
        "http://localhost.evil:8765",
        "null",
        "http://localhost:8765/path",
        "http://localhost:8765@evil.example",
        "http://127.0.0.1:8765",
        "http://localhost:8765#",
    ):
        response = client.post("/api/v1/configurations", json=body, headers={"Origin": origin})
        assert response.status_code == 403, origin
    response = client.post(
        "/api/v1/configurations", json={}, headers={"Sec-Fetch-Site": "cross-site"}
    )
    assert response.status_code == 403
    assert client.get("/api/v1/catalog", headers={"Host": "127.0.0.1:8765"}).status_code == 200
    assert client.post("/api/v1/experiments", json={"request": payload()}).status_code == 403
    assert client.get("/api/v1/catalog", headers={"Host": "localhost:bad"}).status_code == 403


def result():
    bet = Bet("2025-01-01 05:10", (7,), 1, 1, (7, 8, 9, 10, 11), 80, 179)
    return SessionResult(Outcome.GOAL, 1, 1, 80, 179, (bet,))


@pytest.mark.parametrize(
    ("paid", "expected_delta"),
    [(80, 79), (0, -1), (1, 0)],
)
def test_run_delta_projects_persisted_result_from_request_capital(setup, paid, expected_delta):
    client, app, _ = setup
    repo = app.state.repo
    data = payload()
    data["strategies"].append({**data["strategies"][0], "name": "Second"})
    identifier = repo.create_experiment(
        ExperimentRequest.model_validate(data),
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    pending = client.get(f"/api/v1/experiments/{identifier}").json()["runs"]
    assert all(run["result"] is None for run in pending)
    repo.start_run(identifier, 0)
    bet = Bet("2025-01-01 05:10", (7,), 1, 1, (7, 8, 9, 10, 11), paid, 99 + paid)
    repo.complete_run(identifier, 0, SessionResult(Outcome.LIMIT, 1, 1, paid, 99 + paid, (bet,)))
    repo.finish_incomplete(identifier, ExperimentStatus.CANCELLED)
    for runs in (
        client.get(f"/api/v1/experiments/{identifier}").json()["runs"],
        client.get("/api/v1/experiments").json()["items"][0]["runs"],
        client.get(f"/api/v1/experiments/{identifier}/compare").json()["runs"],
    ):
        assert runs[0]["result"]["final_balance"] == 99 + paid
        assert runs[0]["result"]["delta"] == expected_delta
        assert runs[1]["result"] is None


def synthetic_runner(settings, conditions, selected, cancel):
    return result()


def wait_for(predicate):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    pytest.fail("queue did not reach expected state")


def test_snapshot_replay_compare_and_confirmed_delete(setup, monkeypatch):
    client, app, _ = setup
    repo = app.state.repo
    body = {"name": "Saved", "strategy": strategy().model_dump(mode="json")}
    config = post(client, "/api/v1/configurations", body).json()["id"]
    assert client.get(f"/api/v1/configurations/{config}").status_code == 200
    assert client.get("/api/v1/configurations?limit=0").status_code == 422
    assert post(client, "/api/v1/configurations", {**body, "extra": 1}).status_code == 422
    assert client.get("/api/v1/catalog/starting-draws?limit=101").status_code == 422
    request = ExperimentRequest.model_validate(payload())
    identifier = repo.create_experiment(
        request,
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
        configuration_ids=(config,),
    )
    repo.start_run(identifier, 0)
    repo.complete_run(identifier, 0, result())
    repo.complete_experiment(identifier)
    monkeypatch.setattr("laboratorio.domain.session.run_session", lambda *a: pytest.fail("recalc"))
    detail = client.get(f"/api/v1/experiments/{identifier}").json()
    assert detail["runs"][0]["result"]["final_balance"] == 179
    assert "bets" not in detail["runs"][0]["result"]
    assert client.get(f"/api/v1/experiments/{identifier}/runs/0/replay?limit=1").json()["items"][0][
        "numbers"
    ] == [7]
    response = client.get(f"/api/v1/experiments/{identifier}/runs/0/replay?limit=101")
    assert response.status_code == 422
    assert client.get(f"/api/v1/experiments/{identifier}/compare").json()["completed"] == 1
    assert client.get(f"/api/v1/experiments/{identifier}/runs/2/replay").status_code == 404
    assert client.get("/api/v1/experiments/missing").status_code == 404
    assert (
        client.request(
            "DELETE",
            f"/api/v1/configurations/{config}",
            json={"confirm_id": "wrong"},
            headers={"Origin": "http://localhost:8765"},
        ).status_code
        == 400
    )
    assert (
        client.request(
            "DELETE",
            f"/api/v1/configurations/{config}",
            json={"confirm_id": config},
            headers={"Origin": "http://localhost:8765"},
        ).status_code
        == 204
    )
    assert client.get(f"/api/v1/experiments/{identifier}").json()["runs"][0]["result"] is not None
    assert (
        client.request(
            "DELETE",
            f"/api/v1/experiments/{identifier}",
            json={"confirm_id": "wrong"},
            headers={"Origin": "http://localhost:8765"},
        ).status_code
        == 400
    )
    assert (
        client.request(
            "DELETE",
            f"/api/v1/experiments/{identifier}",
            json={"confirm_id": identifier},
            headers={"Origin": "http://localhost:8765"},
        ).status_code
        == 204
    )
    assert client.get(f"/api/v1/experiments/{identifier}").status_code == 404


def test_active_delete_refused_and_cancel_held_start(setup):
    client, app, _ = setup
    repo = app.state.repo
    identifier = repo.create_experiment(
        ExperimentRequest.model_validate(payload()),
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    headers = {"Origin": "http://localhost:8765"}

    def delete():
        return client.request(
            "DELETE",
            f"/api/v1/experiments/{identifier}",
            json={"confirm_id": identifier},
            headers=headers,
        )

    assert delete().status_code == 409
    assert post(client, f"/api/v1/queue/{identifier}/start").status_code == 409
    assert post(client, f"/api/v1/queue/{identifier}/cancel").status_code == 409
    repo.recover_jobs()
    assert repo.get_experiment(identifier).status is ExperimentStatus.HELD
    assert client.get("/api/v1/queue").json()["held"]["items"] == [identifier]
    assert post(client, f"/api/v1/queue/{identifier}/cancel").status_code == 200
    saved = repo.get_experiment(identifier)
    assert saved is not None and saved.status is ExperimentStatus.CANCELLED
    assert post(client, f"/api/v1/queue/{identifier}/start").status_code == 409
    assert delete().status_code == 204


def test_queue_status_pages_pending_and_held_without_materializing_backlog(setup, monkeypatch):
    client, app, _ = setup
    repo = app.state.repo
    identifiers = [
        repo.create_experiment(
            ExperimentRequest.model_validate(payload()),
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="v1",
        )
        for _ in range(3)
    ]
    repo.recover_jobs()
    with app.state.jobs._lock:
        app.state.jobs._pending.extend(identifiers)
    monkeypatch.setattr(
        app.state.jobs, "pending_ids", lambda: pytest.fail("full pending materialization")
    )
    page = client.get("/api/v1/queue?offset=1&limit=1")
    assert page.status_code == 200
    assert page.json()["pending"] == {
        "total": 3,
        "offset": 1,
        "limit": 1,
        "count": 1,
        "items": [identifiers[1]],
    }
    assert page.json()["held"] == {
        "total": 3,
        "offset": 1,
        "limit": 1,
        "count": 1,
        "items": [identifiers[1]],
    }
    assert "pending_ids" not in page.json()
    beyond = client.get("/api/v1/queue?offset=3&limit=1").json()
    assert beyond["pending"]["total"] == beyond["held"]["total"] == 3
    assert beyond["pending"]["count"] == beyond["held"]["count"] == 0
    assert beyond["pending"]["items"] == beyond["held"]["items"] == []
    assert client.get("/api/v1/queue?limit=101").status_code == 422


def test_running_delete_refused_and_unpersisted_failure_is_truthful(setup):
    client, app, _ = setup
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
    response = client.request(
        "DELETE",
        f"/api/v1/experiments/{identifier}",
        json={"confirm_id": identifier},
        headers={"Origin": "http://localhost:8765"},
    )
    assert response.status_code == 409
    app.state.jobs.last_failure = QueueFailure(
        identifier, RuntimeError("private path or traceback"), False, OSError("private")
    )
    failure = client.get("/api/v1/queue").json()["last_failure"]
    assert failure["persisted"] is False
    assert failure["persistence_error"] == "OSError"
    assert "private" not in str(failure)


def test_capacity_rejects_before_insert_and_enqueue_compensates(setup, monkeypatch):
    client, app, settings = setup
    queue = app.state.jobs
    queue.settings = replace(settings, quota_bytes=100)
    response = post(client, "/api/v1/experiments", {"request": payload()})
    assert response.status_code == 507
    assert app.state.repo.list_experiments() == []
    queue.settings = settings
    monkeypatch.setattr(queue, "enqueue", lambda _: (_ for _ in ()).throw(QuotaExceeded("quota")))
    assert post(client, "/api/v1/experiments", {"request": payload()}).status_code == 507
    assert app.state.repo.list_experiments() == []


def test_startup_failure_and_no_auto_resume(tmp_path):
    from laboratorio.app import create_app
    from laboratorio.storage.database import initialize_database
    from laboratorio.storage.repository import Repository

    settings = Settings(
        tmp_path / "data", tmp_path / "missing.json", tmp_path / "missing.npz", tmp_path
    )
    app = create_app(settings)
    with pytest.raises(ValueError, match="file not found"):
        with TestClient(app, base_url="http://localhost:8765"):
            pass
    initialize_database(settings.database_path)
    repo = Repository(settings.database_path)
    identifier = repo.create_experiment(
        ExperimentRequest.model_validate(payload()),
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    app = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(app, base_url="http://localhost:8765") as client:
        saved = repo.get_experiment(identifier)
        assert saved is not None and saved.status is ExperimentStatus.HELD
        assert client.get("/api/v1/queue").json()["active_id"] is None
        assert post(client, f"/api/v1/queue/{identifier}/cancel").status_code == 200
    saved = repo.get_experiment(identifier)
    assert saved is not None and saved.status is ExperimentStatus.CANCELLED


def test_single_queue_owner_and_manual_held_start(tmp_path):
    from laboratorio.app import create_app
    from laboratorio.storage.database import initialize_database
    from laboratorio.storage.repository import Repository

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "ranks.npz", tmp_path
    )
    initialize_database(settings.database_path)
    repo = Repository(settings.database_path)
    identifier = repo.create_experiment(
        ExperimentRequest.model_validate(payload()),
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
    )

    def queue_factory(path, cfg):
        return JobQueue(path, cfg, runner=synthetic_runner)

    app = create_app(settings, catalog_loader=lambda _: CatalogStub(), queue_factory=queue_factory)
    second = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(app, base_url="http://localhost:8765") as client:
        saved = repo.get_experiment(identifier)
        assert saved is not None and saved.status is ExperimentStatus.HELD
        with pytest.raises(RuntimeError, match="already owns"):
            with TestClient(second, base_url="http://localhost:8765"):
                pass
        assert post(client, f"/api/v1/queue/{identifier}/start").status_code == 200
        wait_for(
            lambda: (
                (saved := repo.get_experiment(identifier)) is not None
                and saved.status is ExperimentStatus.COMPLETED
            )
        )
        assert post(client, f"/api/v1/queue/{identifier}/start").status_code == 409
    with TestClient(second, base_url="http://localhost:8765") as client:
        assert client.get(f"/api/v1/experiments/{identifier}").status_code == 200


def test_shutdown_timeout_retains_database_owner_until_coordinator_stops(tmp_path):
    from threading import Event, Thread

    from laboratorio.app import create_app

    release = Event()
    entered = Event()
    instances = []

    class SlowShutdownQueue:
        def __init__(self, path, settings):
            self.thread = Thread(target=self._run)
            instances.append(self)

        def _run(self):
            entered.set()
            release.wait()

        def start(self):
            self.thread.start()

        def shutdown(self):
            self.thread.join(timeout=0)
            if self.thread.is_alive():
                raise RuntimeError("queue shutdown timed out")

        @property
        def is_stopped(self):
            return not self.thread.is_alive()

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "ranks.npz", tmp_path
    )
    first = create_app(
        settings, catalog_loader=lambda _: CatalogStub(), queue_factory=SlowShutdownQueue
    )
    second = create_app(settings, catalog_loader=lambda _: CatalogStub())
    try:
        with pytest.raises(RuntimeError, match="queue shutdown timed out"):
            with TestClient(first, base_url="http://localhost:8765"):
                assert entered.wait(2)
        assert instances[0].thread.is_alive()
        with pytest.raises(RuntimeError, match="already owns"):
            with TestClient(second, base_url="http://localhost:8765"):
                pass
    finally:
        release.set()
        if instances:
            instances[0].thread.join(timeout=2)
    assert not instances[0].thread.is_alive()
    with TestClient(second, base_url="http://localhost:8765") as client:
        assert client.get("/api/v1/queue").status_code == 200


def test_failed_start_with_live_coordinator_retains_owner(tmp_path):
    from threading import Event, Thread

    from laboratorio.app import create_app

    release = Event()
    threads = []

    class FailedStartQueue:
        def __init__(self, path, settings):
            self.thread = Thread(target=release.wait)
            threads.append(self.thread)

        def start(self):
            self.thread.start()
            raise RuntimeError("startup failed after thread start")

        def shutdown(self):
            self.thread.join(timeout=0)
            if self.thread.is_alive():
                raise RuntimeError("queue shutdown timed out")

        @property
        def is_stopped(self):
            return not self.thread.is_alive()

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "ranks.npz", tmp_path
    )
    first = create_app(
        settings, catalog_loader=lambda _: CatalogStub(), queue_factory=FailedStartQueue
    )
    second = create_app(settings, catalog_loader=lambda _: CatalogStub())
    try:
        with pytest.raises(RuntimeError, match="queue shutdown timed out") as error:
            with TestClient(first, base_url="http://localhost:8765"):
                pass
        assert isinstance(error.value.__context__, RuntimeError)
        assert "startup failed after thread start" in str(error.value.__context__)
        with pytest.raises(RuntimeError, match="already owns"):
            with TestClient(second, base_url="http://localhost:8765"):
                pass
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=2)
    assert all(not thread.is_alive() for thread in threads)
    with TestClient(second, base_url="http://localhost:8765") as client:
        assert client.get("/api/v1/queue").status_code == 200


def failing_runner(settings, conditions, selected, cancel):
    raise RuntimeError("secret internal runner failure")


def test_queue_failure_is_sanitized_with_persistence_truth(tmp_path):
    from laboratorio.app import create_app

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "ranks.npz", tmp_path
    )

    def queue_factory(path, cfg):
        return JobQueue(path, cfg, runner=failing_runner)

    app = create_app(settings, catalog_loader=lambda _: CatalogStub(), queue_factory=queue_factory)
    with TestClient(app, base_url="http://localhost:8765") as client:
        identifier = post(client, "/api/v1/experiments", {"request": payload()}).json()["id"]
        wait_for(
            lambda: app.state.repo.get_experiment(identifier).status is ExperimentStatus.FAILED
        )
        failure = client.get("/api/v1/queue").json()["last_failure"]
        assert failure == {
            "experiment_id": identifier,
            "persisted": True,
            "reason": "RuntimeError",
            "persistence_error": None,
        }
        assert "secret" not in str(failure)


def test_spawned_route_integration(tmp_path):
    from laboratorio.app import create_app

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "ranks.npz", tmp_path
    )

    def queue_factory(path, cfg):
        return JobQueue(path, cfg, runner=synthetic_runner)

    app = create_app(
        settings,
        catalog_loader=lambda _: CatalogStub(),
        queue_factory=queue_factory,
    )
    with TestClient(app, base_url="http://localhost:8765") as client:
        identifier = post(client, "/api/v1/experiments", {"request": payload()}).json()["id"]
        wait_for(
            lambda: app.state.repo.get_experiment(identifier).status is ExperimentStatus.COMPLETED
        )
        assert client.get(f"/api/v1/experiments/{identifier}/runs/0/replay").json()["total"] == 1


def test_queue_start_failure_reaps(tmp_path):
    from laboratorio.app import create_app

    state = {"shutdown": 0}

    class BrokenQueue:
        def __init__(self, path, settings):
            pass

        def start(self):
            raise RuntimeError("startup failed")

        def shutdown(self):
            state["shutdown"] += 1

        @property
        def is_stopped(self):
            return True

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "ranks.npz", tmp_path
    )
    app = create_app(
        settings,
        catalog_loader=lambda _: CatalogStub(),
        queue_factory=BrokenQueue,
    )
    with pytest.raises(RuntimeError, match="startup failed"):
        with TestClient(app, base_url="http://localhost:8765"):
            pass
    assert state["shutdown"] == 1


@pytest.mark.real_data
def test_real_catalog_factory_uses_installed_inputs(data_dir):
    from laboratorio.app import create_app

    settings = replace(Settings.from_environment(), data_dir=data_dir, port=8765)
    app = create_app(settings)
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.get("/api/v1/catalog")
        assert response.status_code == 200
        assert response.json()["starting_draws_total"] > 100
        assert len(response.json()["starting_draws"]) == 100
        page = client.get("/api/v1/catalog/starting-draws?offset=1&limit=1").json()
        assert page["items"] == response.json()["starting_draws"][1:2]


def put_settings(client, body, **headers):
    return client.put(
        "/api/v1/settings", json=body, headers={"Origin": "http://localhost:8765", **headers}
    )


def test_settings_exact_quota_and_validation(setup):
    client, _, settings = setup
    initial = client.get("/api/v1/settings").json()
    assert initial["storage"]["limit_bytes"] == settings.quota_bytes
    assert initial["storage"]["sqlite_bytes"] >= 0
    assert initial["quota"] == {
        "effective_bytes": str(settings.quota_bytes),
        "persisted_bytes": None,
        "source": "default",
        "writable": True,
    }
    assert initial["storage"]["logical_used_bytes_exact"] == "0"
    maximum = str(2**63 - 1)
    assert put_settings(client, {"quota_bytes": maximum}).json()["quota"] == {
        "effective_bytes": maximum,
        "persisted_bytes": maximum,
        "source": "persisted",
        "writable": True,
    }
    for value in (0, True, 5.0, 2**53, "", "0", "-1", "+1", "1.0", "1e3", "\uff11\uff12", "9" * 20):
        response = put_settings(client, {"quota_bytes": value})
        assert response.status_code == 422, value
        assert response.json()["detail"][0]["loc"] == ["body", "quota_bytes"]
        assert client.get("/api/v1/settings").json()["quota"]["persisted_bytes"] == maximum
    assert put_settings(client, {"quota_bytes": "5", "unexpected": 1}).status_code == 422
    assert put_settings(client, {}).status_code == 422
    assert put_settings(client, {"quota_bytes": "9223372036854775808"}).status_code == 422
    assert put_settings(client, {"quota_bytes": "0001"}).status_code == 422
    for body in ({"quota_bytes": " 1"}, {"quota_bytes": "1\n"}, {"quota_bytes": "1_0"}, []):
        response = put_settings(client, body)
        assert response.status_code == 422
        location = response.json()["detail"][0]["loc"]
        assert location[:2] == (["body", "quota_bytes"] if isinstance(body, dict) else ["body"])
    assert client.get("/api/v1/settings").json()["quota"]["persisted_bytes"] == maximum


def test_settings_below_used_conflicts_without_mutation(setup):
    client, app, _ = setup
    app.state.repo.create_experiment(
        ExperimentRequest.model_validate(payload()),
        history_id="h",
        history_sha256="a" * 64,
        rankings_id="r",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    used = app.state.repo.logical_experiment_bytes()
    assert put_settings(client, {"quota_bytes": str(used)}).status_code == 200
    rejected = put_settings(client, {"quota_bytes": str(used - 1)})
    assert rejected.status_code == 409
    view = client.get("/api/v1/settings").json()
    assert view["quota"]["persisted_bytes"] == str(used)
    assert view["storage"]["logical_used_bytes_exact"] == str(used)
    assert view["storage"]["limit_bytes"] == used


def test_settings_env_override_read_only_and_guarded(setup, monkeypatch):
    client, app, settings = setup
    assert put_settings(client, {"quota_bytes": "2147483648"}).status_code == 200
    monkeypatch.setenv("LABORATORIO_QUOTA_BYTES", str(settings.quota_bytes))
    app.state.settings = Settings.from_environment()
    view = client.get("/api/v1/settings").json()
    assert view["quota"] == {
        "effective_bytes": str(settings.quota_bytes),
        "persisted_bytes": "2147483648",
        "source": "environment",
        "writable": False,
    }
    assert view["storage"]["limit_bytes"] == settings.quota_bytes
    assert put_settings(client, {"quota_bytes": "10000000000"}).status_code == 409
    assert client.get("/api/v1/settings").json()["quota"] == view["quota"]
    denied = put_settings(client, {"quota_bytes": "5"}, Origin="http://evil.example")
    assert denied.status_code == 403
    assert client.put("/api/v1/settings", json={"quota_bytes": "5"}).status_code == 403
    assert (
        client.put(
            "/api/v1/settings",
            json={"quota_bytes": "5"},
            headers={"Origin": "http://localhost:8765", "Host": "evil.example"},
        ).status_code
        == 403
    )


def test_settings_preference_survives_new_app_and_sources_remain_read_only(tmp_path):
    from laboratorio.app import create_app

    settings = Settings(tmp_path / "data", tmp_path / "history", tmp_path / "rankings", tmp_path)
    first = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(first, base_url="http://localhost:8765") as client:
        before = client.get("/api/v1/settings").json()
        written = put_settings(client, {"quota_bytes": "2147483648"})
        assert written.status_code == 200
        assert written.json()["sources"] == before["sources"]
        assert written.json()["connection"] == before["connection"]
        assert written.json()["storage"]["limit_bytes"] == 2147483648
        assert put_settings(client, {"sources": {}}).status_code == 422
    second = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(second, base_url="http://localhost:8765") as client:
        assert client.get("/api/v1/settings").json()["quota"] == {
            "effective_bytes": "2147483648",
            "persisted_bytes": "2147483648",
            "source": "persisted",
            "writable": True,
        }
