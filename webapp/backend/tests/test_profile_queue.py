"""Profile jobs use authenticated parent snapshots and a profile-only spawned worker."""

import json
import os
import sqlite3
import time
from dataclasses import replace
from multiprocessing import get_context

import pytest
from test_profile_storage import cycling_result, profile_request, replay
from test_queue import request as legacy_request

from laboratorio.domain.contracts import ExperimentStatus, RunStatus
from laboratorio.domain.profile_result import serialize_profile_result
from laboratorio.domain.profile_result_v2 import serialize_profile_cycling_result
from laboratorio.jobs.queue import JobQueue
from laboratorio.settings import Settings

pytest_plugins = ("test_profile_storage",)


def wait_for(predicate, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    pytest.fail("profile queue did not reach expected state")


def malformed_profile_entry(send, profile, request, rows, cancel):
    send.send(("completed", '{"kind":"legacy"}'))
    send.close()


def dead_profile_entry(send, profile, request, rows, cancel):
    os._exit(17)


def silent_profile_entry(send, profile, request, rows, cancel):
    send.close()


def wrong_kind_profile_entry(send, profile, request, rows, cancel):
    from laboratorio.domain.profile_session import run_profile_session

    result = run_profile_session(
        profile, request.conditions, request.selector, request.staking, rows
    )
    payload = json.loads(serialize_profile_result(result))
    payload["kind"] = "legacy"
    send.send(("completed", json.dumps(payload)))
    send.close()


def forged_profile_entry(send, profile, request, rows, cancel):
    from laboratorio.domain.profile_session import run_profile_session

    result = run_profile_session(
        profile, request.conditions, request.selector, request.staking, rows
    )
    forged = replace(result, final_balance=result.final_balance + 1)
    send.send(("completed", serialize_profile_result(forged)))
    send.close()


def held_profile_entry(send, profile, request, rows, cancel, entered):
    entered.set()
    time.sleep(10)  # intentionally does not observe cancellation
    from laboratorio.domain.profile_session import run_profile_session

    result = run_profile_session(
        profile, request.conditions, request.selector, request.staking, rows
    )
    send.send(("completed", serialize_profile_result(result)))
    send.close()


def bad_cycling_entry(send, profile, request, rows, cancel):
    send.send(("completed", '{"kind":"profile","schema_version":1}'))
    send.close()


def dead_cycling_entry(send, profile, request, rows, cancel):
    os._exit(17)


def forged_cycling_entry(send, profile, request, rows, cancel):
    from laboratorio.domain.profile_result_v2 import ProfileCyclingResult
    from laboratorio.domain.profile_session import run_profile_session

    session = run_profile_session(
        profile, request.conditions, request.selector, request.staking, rows
    )
    forged = ProfileCyclingResult(
        "profile", 2, replace(session, final_balance=session.final_balance + 1)
    )
    send.send(("completed", serialize_profile_cycling_result(forged)))
    send.close()


def test_submit_profile_spawn_static_and_random_three_positions(bound, tmp_path):
    repo, profile, dataset, request = bound
    repo.create_game_profile(profile)
    settings = Settings(tmp_path, tmp_path / "absent.json", tmp_path / "absent.npz", tmp_path)
    queue = JobQueue(repo.path, settings)
    try:
        queue.start()
        static = queue.submit_profile(request)
        random_request = replace(
            request,
            name="Random",
            selector=replace(
                request.selector,
                capability="seeded-random/hash-sha256-v1",
                coverage=2,
                numbers=None,
                seed=17,
                algorithm_version="hash-sha256-v1",
            ),
        )
        random = queue.submit_profile(random_request)
        wait_for(lambda: repo.get_experiment(random).status is ExperimentStatus.COMPLETED)
        assert repo.get_experiment(static).runs[0].result == replay(request, profile, dataset)
        assert repo.get_experiment(random).runs[0].result == replay(
            random_request, profile, dataset
        )
        assert all(len(bet.results) == 3 for bet in repo.get_experiment(static).runs[0].result.bets)
        assert queue.last_failure is None
    finally:
        queue.shutdown()


def test_submit_rejects_metadata_hash_mismatch_without_orphan(bound, tmp_path):
    repo, profile, _, request = bound
    repo.create_game_profile(profile)
    queue = JobQueue(repo.path, Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path))
    try:
        queue.start()
        with pytest.raises(ValueError, match="registered"):
            queue.submit_profile(replace(request, profile_sha256="b" * 64))
        with pytest.raises(ValueError, match="dataset not found"):
            queue.submit_profile(replace(request, dataset_sha256="b" * 64))
        assert repo.list_experiments() == []
        assert queue.pending_ids() == ()
    finally:
        queue.shutdown()


@pytest.mark.parametrize(
    "entry,expected",
    [
        (malformed_profile_entry, "malformed"),
        (wrong_kind_profile_entry, "malformed"),
        (forged_profile_entry, "differs"),
        (dead_profile_entry, "worker exited with code 17"),
        (silent_profile_entry, "without a final result"),
    ],
)
def test_bad_completed_profile_is_queue_fatal_and_preserves_prior_result(
    bound, tmp_path, monkeypatch, entry, expected
):
    repo, profile, _, request = bound
    repo.create_game_profile(profile)
    queue = JobQueue(repo.path, Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path))
    try:
        queue.start()
        first = queue.submit_profile(request)
        wait_for(lambda: repo.get_experiment(first).status is ExperimentStatus.COMPLETED)
        monkeypatch.setattr("laboratorio.jobs.queue.profile_process_entry", entry)
        broken = queue.submit_profile(replace(request, name="Broken"))
        later = queue.submit_profile(replace(request, name="Later"))
        wait_for(lambda: queue.last_failure is not None)
        wait_for(lambda: queue.is_stopped)
        failure = queue.last_failure
        assert failure is not None
        assert expected in str(failure.error)
        assert failure.persisted
        assert repo.get_experiment(first).runs[0].result is not None
        assert repo.get_experiment(broken).runs[0].status is RunStatus.FAILED
        assert repo.get_experiment(broken).runs[0].result is None
        assert repo.get_experiment(later).status is ExperimentStatus.PENDING
        assert queue._process is None
    finally:
        queue.shutdown()


def test_cancel_unresponsive_profile_discard_and_shutdown_interrupt(bound, tmp_path, monkeypatch):
    repo, profile, _, request = bound
    repo.create_game_profile(profile)
    ctx = get_context("spawn")
    entered = ctx.Event()

    # A top-level partial is spawn-picklable; a closure is not.
    from functools import partial

    monkeypatch.setattr(
        "laboratorio.jobs.queue.profile_process_entry",
        partial(held_profile_entry, entered=entered),
    )
    queue = JobQueue(repo.path, Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path))
    try:
        queue.start()
        identifier = queue.submit_profile(request)
        assert entered.wait(10)
        child = queue._process
        assert child is not None
        queue.cancel(identifier)
        wait_for(lambda: repo.get_experiment(identifier).status is ExperimentStatus.CANCELLED, 5)
        assert not child.is_alive()
        assert repo.get_experiment(identifier).runs[0].result is None
    finally:
        queue.shutdown()
    entered.clear()
    next_queue = JobQueue(repo.path, queue.settings)
    try:
        next_queue.start()
        identifier = next_queue.submit_profile(replace(request, name="Interrupted"))
        assert entered.wait(10)
        next_queue.shutdown()
        assert repo.get_experiment(identifier).status is ExperimentStatus.INTERRUPTED
        assert repo.get_experiment(identifier).runs[0].result is None
    finally:
        next_queue.shutdown()


def test_cycling_preparation_cannot_enqueue_or_start_or_recover(cycling, tmp_path):
    repo, _, _, request = cycling
    identifier = repo.create_profile_cycling_experiment(request)
    queue = JobQueue(repo.path, Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path))
    try:
        queue.start()
        assert repo.get_experiment(identifier).status is ExperimentStatus.HELD
        assert repo.page_held_ids(0, 10) == (1, [identifier])
        queue.cancel(identifier)
        assert repo.get_experiment(identifier).status is ExperimentStatus.CANCELLED
        assert queue.pending_ids() == () and queue.active_id is None
        with pytest.raises(ValueError, match="new pending"):
            queue.enqueue(identifier)
        assert repo.get_experiment(identifier).status is ExperimentStatus.CANCELLED
        # Even a manually reintroduced pending row cannot use the v1-only enqueue.
        with sqlite3.connect(repo.path) as db:
            db.execute("UPDATE experiments SET status = 'pending' WHERE id = ?", (identifier,))
        with pytest.raises(ValueError, match="not executable"):
            queue.enqueue(identifier)
        assert queue.pending_ids() == () and queue.active_id is None
        assert repo.get_experiment(identifier).runs[0].status is RunStatus.NOT_RUN
    finally:
        queue.shutdown()


def test_private_cycling_spawn_authenticates_full_dataset_and_preserves_v1(cycling, tmp_path):
    repo, profile, dataset, request = cycling
    settings = Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path)
    queue = JobQueue(repo.path, settings)
    try:
        queue.start()
        identifier = repo.create_profile_cycling_experiment(request)
        queue._enqueue_profile_cycling(identifier)
        wait_for(lambda: repo.get_experiment(identifier).status is ExperimentStatus.COMPLETED)
        saved = repo.get_experiment(identifier)
        assert saved.runs[0].result == cycling_result(request, profile, dataset)
        assert saved.runs[0].result_schema_version == 2
        assert saved.runs[0].result.session.elapsed_draws > 0
        with sqlite3.connect(repo.path) as db:
            wire, version = db.execute(
                "SELECT result_json, result_schema_version FROM runs WHERE experiment_id = ?",
                (identifier,),
            ).fetchone()
        assert version == 2 and json.loads(wire)["schema_version"] == 2
        assert queue.last_failure is None
    finally:
        queue.shutdown()

    # Startup recovery holds private jobs but never silently schedules them.
    held = repo.create_profile_cycling_experiment(replace(request, name="Held"))
    restarted = JobQueue(repo.path, settings)
    try:
        restarted.start()
        assert repo.get_experiment(held).status is ExperimentStatus.HELD
        assert restarted.pending_ids() == () and restarted.active_id is None
        assert repo.page_held_ids(0, 10) == (1, [held])
        with pytest.raises(ValueError, match="new pending"):
            restarted.enqueue(held)
        restarted.start_held(held)
        wait_for(lambda: repo.get_experiment(held).status is ExperimentStatus.COMPLETED)
        assert repo.get_experiment(held).runs[0].result == cycling_result(request, profile, dataset)
    finally:
        restarted.shutdown()


@pytest.mark.parametrize(
    "entry,expected",
    [
        (bad_cycling_entry, "malformed"),
        (dead_cycling_entry, "worker exited with code 17"),
        (forged_cycling_entry, "differs"),
    ],
)
def test_private_cycling_bad_ipc_stops_queue_preserving_prior_and_later(
    cycling, tmp_path, monkeypatch, entry, expected
):
    repo, _, _, request = cycling
    queue = JobQueue(repo.path, Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path))
    try:
        queue.start()
        first = repo.create_profile_cycling_experiment(request)
        queue._enqueue_profile_cycling(first)
        wait_for(lambda: repo.get_experiment(first).status is ExperimentStatus.COMPLETED)
        monkeypatch.setattr("laboratorio.jobs.queue.profile_cycling_process_entry", entry)
        broken = repo.create_profile_cycling_experiment(replace(request, name="Broken"))
        later = repo.create_profile_cycling_experiment(replace(request, name="Later"))
        queue._enqueue_profile_cycling(broken)
        queue._enqueue_profile_cycling(later)
        wait_for(lambda: queue.last_failure is not None)
        wait_for(lambda: queue.is_stopped)
        failure = queue.last_failure
        assert failure is not None
        assert expected in str(failure.error)
        assert failure.persisted
        assert repo.get_experiment(first).runs[0].result is not None
        assert repo.get_experiment(broken).runs[0].result is None
        assert repo.get_experiment(broken).runs[0].status is RunStatus.FAILED
        assert repo.get_experiment(later).status is ExperimentStatus.PENDING
    finally:
        queue.shutdown()


def test_private_cycling_enqueue_refuses_wrong_kind_version_status_and_duplicate(cycling, tmp_path):
    repo, profile, _, request = cycling
    queue = JobQueue(repo.path, Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path))
    try:
        queue.start()
        missing = "missing"
        v1 = repo.create_profile_experiment(
            replace(
                profile_request(profile),
                dataset_sha256=request.dataset_sha256,
                conditions=request.conditions,
                selector=request.selector,
            )
        )
        legacy = repo.create_experiment(
            legacy_request("First"),
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="v1",
        )
        for wrong in (missing, v1, legacy):
            with pytest.raises(ValueError, match="profile cycling"):
                queue._enqueue_profile_cycling(wrong)
        identifier = repo.create_profile_cycling_experiment(request)
        with pytest.raises(ValueError, match="not executable"):
            queue.enqueue(identifier)
        queue._enqueue_profile_cycling(identifier)
        with pytest.raises(ValueError, match="already enqueued"):
            queue._enqueue_profile_cycling(identifier)
        wait_for(lambda: repo.get_experiment(identifier).status is ExperimentStatus.COMPLETED)
        with pytest.raises(ValueError, match="profile cycling"):
            queue._enqueue_profile_cycling(identifier)
    finally:
        queue.shutdown()


def test_private_cycling_shutdown_interrupts_spawn_without_result(cycling, tmp_path, monkeypatch):
    from functools import partial

    repo, _, _, request = cycling
    entered = get_context("spawn").Event()
    monkeypatch.setattr(
        "laboratorio.jobs.queue.profile_cycling_process_entry",
        partial(held_profile_entry, entered=entered),
    )
    queue = JobQueue(repo.path, Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path))
    try:
        queue.start()
        identifier = repo.create_profile_cycling_experiment(request)
        queue._enqueue_profile_cycling(identifier)
        assert entered.wait(10)
        child = queue._process
        queue.shutdown()
        assert child is not None and not child.is_alive()
        saved = repo.get_experiment(identifier)
        assert saved.status is ExperimentStatus.INTERRUPTED
        assert saved.runs[0].status is RunStatus.INTERRUPTED
        assert saved.runs[0].result is None
    finally:
        queue.shutdown()


def test_private_cycling_artifact_integrity_error_stops_before_spawn(
    cycling, tmp_path, monkeypatch
):
    repo, _, _, request = cycling
    settings = Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path)
    queue = JobQueue(repo.path, settings)
    try:
        queue.start()
        identifier = repo.create_profile_cycling_experiment(request)

        def corrupt_artifact(_):
            raise ValueError("corrupt dataset bytes")

        monkeypatch.setattr(queue.repo, "get_dataset", corrupt_artifact)
        # The repository's immutable-artifact integrity check must be fatal
        # before any child output can be trusted.
        queue._enqueue_profile_cycling(identifier)
        wait_for(lambda: queue.last_failure is not None)
        wait_for(lambda: queue.is_stopped)
        failure = queue.last_failure
        assert failure is not None and not failure.persisted
        assert failure.persistence_error is not None  # pending cannot fail before start_run
        assert repo.get_experiment(identifier).status is ExperimentStatus.PENDING
        assert repo.get_experiment(identifier).runs[0].result is None
    finally:
        queue.shutdown()
    restarted = JobQueue(repo.path, settings)
    try:
        restarted.start()
        assert repo.get_experiment(identifier).status is ExperimentStatus.HELD
        assert restarted.pending_ids() == ()
    finally:
        restarted.shutdown()


def test_manual_resume_held_profile(bound, tmp_path):
    repo, profile, _, request = bound
    repo.create_game_profile(profile)
    identifier = repo.create_profile_experiment(request)
    queue = JobQueue(repo.path, Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path))
    try:
        queue.start()
        assert repo.get_experiment(identifier).status is ExperimentStatus.HELD
        queue.start_held(identifier)
        wait_for(lambda: repo.get_experiment(identifier).status is ExperimentStatus.COMPLETED)
    finally:
        queue.shutdown()


def test_audaz_schema3_held_cancel_manual_resume_and_spawned_replay(bound, tmp_path):
    from laboratorio.domain.profile_request import profile_sha256
    from laboratorio.domain.profile_request_v3 import ProfileAudazRequest
    from laboratorio.domain.profile_session import ProfileSelector
    from laboratorio.domain.profile_staking import ProfileAudazStaking

    repo, profile, dataset, request = bound
    repo.create_game_profile(profile)
    audaz = ProfileAudazRequest(
        "profile", 3, "Audaz queue", dataset.dataset_sha256, profile.profile_id,
        profile.revision, profile_sha256(profile), request.conditions,
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(0,)),
        ProfileAudazStaking(), "all_rows/v1",
    )
    cancelled = repo.create_profile_audaz_experiment(audaz)
    resumed = repo.create_profile_audaz_experiment(replace(audaz, name="Audaz resumed"))
    settings = Settings(tmp_path, tmp_path / "none", tmp_path / "none", tmp_path)
    queue = JobQueue(repo.path, settings)
    try:
        queue.start()
        assert repo.get_experiment(cancelled).status is ExperimentStatus.HELD
        assert repo.get_experiment(resumed).status is ExperimentStatus.HELD
        queue.cancel(cancelled)
        assert repo.get_experiment(cancelled).status is ExperimentStatus.CANCELLED
        queue.start_held(resumed)
        wait_for(lambda: repo.get_experiment(resumed).status is ExperimentStatus.COMPLETED)
        saved = repo.get_experiment(resumed)
        assert saved.request_schema_version == 3
        assert saved.runs[0].result_schema_version == 3
        assert saved.runs[0].result.session.final_balance >= 0
        assert queue.last_failure is None
    finally:
        queue.shutdown()
