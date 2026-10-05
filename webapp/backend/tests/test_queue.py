"""Spawned calculation and durable queue transitions; never touch the user's data."""

import os
import time
from dataclasses import replace
from multiprocessing import get_context
from threading import Barrier, Thread
from threading import Event as LocalEvent
from types import SimpleNamespace

import pytest

from laboratorio.domain.contracts import (
    Conditions,
    ExperimentRequest,
    ExperimentStatus,
    Outcome,
    RunStatus,
    SelectorKind,
    StakingStyle,
    Strategy,
)
from laboratorio.domain.session import Bet, SessionResult
from laboratorio.engine.adapter import DataError
from laboratorio.jobs.queue import JobQueue
from laboratorio.jobs.worker import SharedCalculationError, StrategyLocalError, calculate_run
from laboratorio.settings import Settings
from laboratorio.storage.database import initialize_database
from laboratorio.storage.repository import Repository


def synthetic(settings, conditions, strategy, cancel, entered, release, report):
    report.put(os.getpid())
    if strategy.name.startswith("Wait"):
        entered.set()
        while not release.wait(0.02):
            if cancel.is_set():
                return None
    if strategy.name.startswith("Stuck"):
        entered.set()
        LocalEvent().wait(5)  # deliberately ignores cancellation, no shared lock to strand
    if strategy.name.startswith("Die"):
        entered.set()
        release.wait(5)
        os._exit(17)
    if strategy.name.startswith("Error"):
        raise ValueError("synthetic data load failure")
    if strategy.name.startswith("Local"):
        raise StrategyLocalError("independent strategy failure")
    if strategy.name.startswith("Shared"):
        raise DataError("shared draw integrity failure")
    if strategy.name.startswith("Storage"):
        raise OSError("shared infrastructure failure")
    if strategy.name.startswith("None"):
        return None
    if strategy.name.startswith("Wrong"):
        return {"outcome": "goal"}
    if strategy.name.startswith("Bad"):
        return SessionResult(Outcome.GOAL, 1, 1, 80, 179, ())
    bet = Bet(conditions.start_draw, (7,), 1, 1, (7, 8, 9, 10, 11), 80, 179)
    return SessionResult(Outcome.GOAL, 1, 1, 80, 179, (bet,))


def malformed_entry(send, *args):
    send.send(("failed", ("strategy_local", 123)))
    send.close()


def silent_entry(send, *args):
    send.close()


def strategy(name):
    return Strategy(
        name=name,
        selector=SelectorKind.SYSTEM,
        system="cold",
        coverage=1,
        staking=StakingStyle.FLAT,
    )


def request(*names):
    return ExperimentRequest(
        name="Trial",
        conditions=Conditions(start_draw="2025-01-01 05:10", capital=100, goal=150, seed=42),
        strategies=tuple(strategy(n) for n in names),
    )


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "lab.db"
    initialize_database(path)
    repo = Repository(path)
    settings = Settings(tmp_path, tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path)
    ctx = get_context("spawn")
    entered, release, report = ctx.Event(), ctx.Event(), ctx.Queue()

    def create(*names):
        return repo.create_experiment(
            request(*names),
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="v1",
        )

    yield repo, settings, ctx, entered, release, report, create
    release.set()
    report.close()
    report.join_thread()


def wait_for(predicate, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    pytest.fail("queue did not reach expected state")


def queue_for(setup):
    repo, settings, _, entered, release, report, _ = setup
    return JobQueue(repo.path, settings, runner=synthetic, runner_args=(entered, release, report))


# B-QUE-001

def test_spawned_local_failure_preserves_neighbours_and_continues(setup):
    repo, _, _, _, _, report, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        identifier = create("First", "Local second", "Third")
        queue.enqueue(identifier)
        wait_for(lambda: repo.get_experiment(identifier).status is ExperimentStatus.FAILED)
        saved = repo.get_experiment(identifier)
        assert [run.status for run in saved.runs] == [
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.COMPLETED,
        ]
        assert saved.runs[0].result is not None
        assert saved.runs[1].result is None
        assert saved.runs[2].result is not None
        assert all(report.get(timeout=5) != os.getpid() for _ in range(3))
        assert queue.last_failure.persisted is True
        assert "independent strategy" in str(queue.last_failure.error)
    finally:
        queue.shutdown()


# B-QUE-002

def test_unknown_worker_value_error_fails_current_experiment_not_later_job(setup):
    repo, _, _, _, _, report, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        broken, later = create("First", "Error second", "Third"), create("Later")
        queue.enqueue(broken)
        queue.enqueue(later)
        wait_for(lambda: repo.get_experiment(later).status is ExperimentStatus.COMPLETED)
        assert [r.status for r in repo.get_experiment(broken).runs] == [
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.NOT_RUN,
        ]
        assert report.get(timeout=5) != os.getpid()
        assert report.get(timeout=5) != os.getpid()
        assert report.get(timeout=5) != os.getpid()
        assert report.empty()
    finally:
        queue.shutdown()


# B-QUE-003
@pytest.mark.parametrize("name", ["Shared", "Storage"])
def test_shared_worker_failure_stops_queue_and_preserves_unstarted_job(setup, name):
    repo, _, _, _, _, _, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        broken, later = create("First", name, "Third"), create("Later")
        queue.enqueue(broken)
        queue.enqueue(later)
        wait_for(lambda: queue.last_failure is not None)
        assert queue.is_stopped
        assert [r.status for r in repo.get_experiment(broken).runs] == [
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.NOT_RUN,
        ]
        assert repo.get_experiment(later).status is ExperimentStatus.PENDING
        assert queue.last_failure.persisted is True
    finally:
        queue.shutdown()


# B-QUE-004
@pytest.mark.parametrize("entry", [malformed_entry, silent_entry])
def test_malformed_spawn_message_is_queue_fatal(setup, monkeypatch, entry):
    repo, _, _, _, _, _, create = setup
    queue = queue_for(setup)
    monkeypatch.setattr("laboratorio.jobs.queue.process_entry", entry)
    try:
        queue.start()
        broken, later = create("First", "Second"), create("Later")
        queue.enqueue(broken)
        queue.enqueue(later)
        wait_for(lambda: queue.last_failure is not None)
        assert queue.is_stopped
        assert [r.status for r in repo.get_experiment(broken).runs] == [
            RunStatus.FAILED,
            RunStatus.NOT_RUN,
        ]
        assert repo.get_experiment(later).status is ExperimentStatus.PENDING
    finally:
        queue.shutdown()


# B-QUE-005

def test_clean_exit_eof_is_fatal_even_when_pipe_reports_readable(setup, monkeypatch):
    repo, _, ctx, _, _, _, create = setup
    queue = queue_for(setup)
    monkeypatch.setattr("laboratorio.jobs.queue.process_entry", silent_entry)

    class ReadableEOF:
        def __init__(self, receiver):
            self.receiver = receiver

        def poll(self, timeout=0):
            return True  # Exercise recv()'s EOF path, not the poll-false path.

        def recv(self):
            return self.receiver.recv()

        def close(self):
            self.receiver.close()

    def pipe(*args, **kwargs):
        receiver, sender = ctx.Pipe(*args, **kwargs)
        return ReadableEOF(receiver), sender

    monkeypatch.setattr(
        queue, "_ctx", SimpleNamespace(Event=ctx.Event, Process=ctx.Process, Pipe=pipe)
    )
    try:
        queue.start()
        broken, later = create("First"), create("Later")
        queue.enqueue(broken)
        queue.enqueue(later)
        wait_for(lambda: queue.is_stopped)
        assert repo.get_experiment(broken).runs[0].status is RunStatus.FAILED
        assert repo.get_experiment(later).status is ExperimentStatus.PENDING
        assert "without a final result" in str(queue.last_error)
    finally:
        queue.shutdown()


# B-QUE-006

def test_production_boundary_only_localizes_initial_stake(setup, monkeypatch):
    from laboratorio.jobs import worker

    _, settings, _, _, _, _, _ = setup
    conditions = request("First").conditions.model_copy(update={"capital": 1})
    selected = strategy("First").model_copy(update={"coverage": 50})
    monkeypatch.setattr(worker, "open_lab_data", lambda _: object())
    with pytest.raises(StrategyLocalError, match="initial capital"):
        calculate_run(settings, conditions, selected, LocalEvent())
    monkeypatch.setattr(worker, "open_lab_data", lambda _: (_ for _ in ()).throw(DataError("bad")))
    with pytest.raises(DataError, match="bad"):
        calculate_run(settings, conditions, selected, LocalEvent())
    monkeypatch.setattr(worker, "open_lab_data", lambda _: object())

    def corrupt_draw(*args):
        raise ValueError("bad draw")

    monkeypatch.setattr(worker, "run_session", corrupt_draw)
    with pytest.raises(SharedCalculationError, match="bad draw"):
        calculate_run(settings, request("First").conditions, strategy("First"), LocalEvent())


# B-QUE-007

def test_admission_at_enqueue_and_held_start(setup):
    repo, settings, _, _, _, _, create = setup
    quota = JobQueue(repo.path, replace(settings, quota_bytes=1))
    try:
        quota.start()
        held = create("Held")
        # Created after start: pending; both routes must reject without spawning.
        fresh = create("Fresh")
        with pytest.raises(Exception, match="quota"):
            quota.enqueue(fresh)
        assert quota.pending_ids() == ()
    finally:
        quota.shutdown()
    restarted = JobQueue(repo.path, replace(settings, quota_bytes=1))
    try:
        restarted.start()
        assert repo.get_experiment(held).status is ExperimentStatus.HELD
        with pytest.raises(Exception, match="quota"):
            restarted.start_held(held)
        assert restarted.pending_ids() == ()
    finally:
        restarted.shutdown()


# B-QUE-008

def test_backlog_rechecks_capacity_before_expensive_run(setup, monkeypatch):
    repo, _, _, entered, release, report, create = setup
    queue = queue_for(setup)
    complete = queue.repo.complete_experiment

    def after_first(identifier):
        complete(identifier)
        monkeypatch.setattr(
            queue, "disk_usage", lambda _: SimpleNamespace(total=100, used=100, free=0)
        )

    monkeypatch.setattr(queue.repo, "complete_experiment", after_first)
    try:
        queue.start()
        first, second = create("Wait first"), create("Next")
        queue.enqueue(first)
        queue.enqueue(second)
        assert entered.wait(10)
        release.set()
        wait_for(lambda: queue.last_failure is not None)
        assert repo.get_experiment(first).status is ExperimentStatus.COMPLETED
        assert repo.get_experiment(second).status is ExperimentStatus.HELD
        assert queue.last_failure is not None
        assert queue.last_failure.experiment_id == second
        assert report.get(timeout=5) != os.getpid()
        assert report.empty()
    finally:
        release.set()
        queue.shutdown()


# B-QUE-009

def test_write_failure_stops_queue_preserves_prior_result_and_reaps_child(setup, monkeypatch):
    repo, _, _, entered, release, _, create = setup
    queue = queue_for(setup)
    original = queue.repo.complete_run
    calls = 0

    def fail_second(identifier, ordinal, result, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic disk full")
        return original(identifier, ordinal, result, **kwargs)

    monkeypatch.setattr(queue.repo, "complete_run", fail_second)
    try:
        queue.start()
        broken, later = create("First", "Wait second"), create("Later")
        queue.enqueue(broken)
        queue.enqueue(later)
        assert entered.wait(10)
        release.set()
        wait_for(lambda: queue.last_failure is not None)
        saved = repo.get_experiment(broken)
        assert saved.status is ExperimentStatus.FAILED
        assert [r.status for r in saved.runs] == [RunStatus.COMPLETED, RunStatus.FAILED]
        assert saved.runs[0].result is not None and saved.runs[1].result is None
        assert repo.get_experiment(later).status is ExperimentStatus.PENDING
        assert queue.last_failure is not None
        assert queue.last_failure.persisted is True
        assert "disk full" in str(queue.last_failure.error)
        assert queue._process is None
    finally:
        release.set()
        queue.shutdown()
    restarted = queue_for(setup)
    try:
        restarted.start()
        assert repo.get_experiment(later).status is ExperimentStatus.HELD
        assert repo.get_experiment(broken).status is ExperimentStatus.FAILED
    finally:
        restarted.shutdown()


# B-QUE-010

def test_failed_status_write_is_reported_only_in_memory_then_recovered(setup, monkeypatch):
    repo, _, _, entered, release, _, create = setup
    queue = queue_for(setup)
    original_finish = queue.repo.finish_incomplete

    def disk_full(*args, **kwargs):
        raise OSError("disk full")

    def store_unavailable(*args):
        raise OSError("store unavailable")

    monkeypatch.setattr(queue.repo, "complete_run", disk_full)
    monkeypatch.setattr(queue.repo, "finish_incomplete", store_unavailable)
    try:
        queue.start()
        broken = create("Wait first")
        queue.enqueue(broken)
        assert entered.wait(10)
        child = queue._process
        assert child is not None
        release.set()
        wait_for(lambda: queue.last_failure is not None)
        assert not child.is_alive()
        assert queue.last_failure is not None
        assert queue.last_failure.experiment_id == broken
        assert queue.last_failure.persisted is False
        assert "store unavailable" in str(queue.last_failure.persistence_error)
        assert repo.get_experiment(broken).status is ExperimentStatus.RUNNING
    finally:
        queue.shutdown()
    monkeypatch.setattr(queue.repo, "finish_incomplete", original_finish)
    restarted = queue_for(setup)
    try:
        restarted.start()
        assert repo.get_experiment(broken).status is ExperimentStatus.INTERRUPTED
        assert repo.get_experiment(broken).runs[0].result is None
    finally:
        restarted.shutdown()


# B-QUE-011

def test_serial_experiments_and_child_process(setup):
    repo, _, _, entered, release, report, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        first, second = create("Wait first"), create("Second")
        queue.enqueue(first)
        queue.enqueue(second)
        assert entered.wait(10)
        child_pid = report.get(timeout=5)
        assert child_pid != os.getpid()
        assert repo.get_experiment(second).status is ExperimentStatus.PENDING
        release.set()
        wait_for(lambda: repo.get_experiment(second).status is ExperimentStatus.COMPLETED)
        assert repo.get_experiment(first).status is ExperimentStatus.COMPLETED
        assert report.get(timeout=5) != os.getpid()
    finally:
        queue.shutdown()


# B-QUE-012

def test_cancel_active_preserves_completed_and_discards_partial(setup):
    repo, _, _, entered, release, _, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        experiment = create("First", "Wait second", "Third")
        queue.enqueue(experiment)
        assert entered.wait(10)
        saved = repo.get_experiment(experiment)
        assert [r.status for r in saved.runs] == [
            RunStatus.COMPLETED,
            RunStatus.RUNNING,
            RunStatus.PENDING,
        ]
        queue.cancel(experiment)
        wait_for(lambda: repo.get_experiment(experiment).status is ExperimentStatus.CANCELLED)
        saved = repo.get_experiment(experiment)
        assert [r.status for r in saved.runs] == [
            RunStatus.COMPLETED,
            RunStatus.CANCELLED,
            RunStatus.NOT_RUN,
        ]
        assert saved.runs[0].result is not None
        assert saved.runs[1].result is saved.runs[2].result is None
    finally:
        release.set()
        queue.shutdown()


# B-QUE-013

def test_cancel_does_not_wait_for_a_stuck_session_and_reaps_child(setup):
    repo, _, _, entered, release, _, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        experiment = create("Stuck calculation")
        queue.enqueue(experiment)
        assert entered.wait(10)
        child = queue._process
        assert child is not None and child.is_alive()
        queue.cancel(experiment)
        wait_for(
            lambda: repo.get_experiment(experiment).status is ExperimentStatus.CANCELLED, timeout=4
        )
        assert not child.is_alive()
        assert repo.get_experiment(experiment).runs[0].result is None
    finally:
        release.set()
        queue.shutdown()


# B-QUE-014

def test_shutdown_and_restart_holds_pending_and_does_not_resume(setup):
    repo, _, _, entered, release, _, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        active, pending = create("First", "Wait second", "Third"), create("Later")
        queue.enqueue(active)
        queue.enqueue(pending)
        assert entered.wait(10)
        queue.shutdown()
        saved = repo.get_experiment(active)
        assert saved.status is ExperimentStatus.INTERRUPTED
        assert [r.status for r in saved.runs] == [
            RunStatus.COMPLETED,
            RunStatus.INTERRUPTED,
            RunStatus.NOT_RUN,
        ]
        assert repo.get_experiment(pending).status is ExperimentStatus.PENDING
        restarted = queue_for(setup)
        try:
            restarted.start()
            assert repo.get_experiment(pending).status is ExperimentStatus.HELD
            assert restarted.pending_ids() == ()
            restarted.start_held(pending)
            wait_for(lambda: repo.get_experiment(pending).status is ExperimentStatus.COMPLETED)
        finally:
            restarted.shutdown()
    finally:
        release.set()
        queue.shutdown()


# B-QUE-015

def test_abrupt_child_death_fails_and_next_job_proceeds(setup):
    repo, _, _, entered, release, _, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        broken, next_job = create("Die first", "Third"), create("Next")
        queue.enqueue(broken)
        queue.enqueue(next_job)
        assert entered.wait(10)
        release.set()
        wait_for(lambda: repo.get_experiment(next_job).status is ExperimentStatus.COMPLETED)
        saved = repo.get_experiment(broken)
        assert saved.status is ExperimentStatus.FAILED
        assert [r.status for r in saved.runs] == [RunStatus.FAILED, RunStatus.NOT_RUN]
        assert all(r.result is None for r in saved.runs)
        assert "17" in str(queue.last_error)
    finally:
        queue.shutdown()


# B-QUE-016

def test_child_initialization_failure_is_explicit_and_queue_recovers(setup):
    repo, _, _, _, _, _, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        failed, next_job = create("Error first"), create("Next")
        queue.enqueue(failed)
        queue.enqueue(next_job)
        wait_for(lambda: repo.get_experiment(next_job).status is ExperimentStatus.COMPLETED)
        assert repo.get_experiment(failed).status is ExperimentStatus.FAILED
        assert repo.get_experiment(failed).runs[0].status is RunStatus.FAILED
    finally:
        queue.shutdown()


# B-QUE-017
@pytest.mark.parametrize("malformed", ["None result", "Wrong type", "Bad result"])
def test_invalid_child_result_is_queue_fatal_without_losing_prior_result(setup, malformed):
    repo, _, _, _, _, report, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        failed, next_job = create("First", malformed, "Never"), create("Next")
        queue.enqueue(failed)
        queue.enqueue(next_job)
        wait_for(lambda: queue.last_failure is not None)
        wait_for(lambda: queue.is_stopped)
        saved = repo.get_experiment(failed)
        assert saved.status is ExperimentStatus.FAILED
        assert [run.status for run in saved.runs] == [
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.NOT_RUN,
        ]
        assert saved.runs[0].result is not None
        assert saved.runs[1].result is saved.runs[2].result is None
        assert repo.get_experiment(next_job).status is ExperimentStatus.PENDING
        assert queue.last_failure.persisted is True
        assert "malformed worker completed result" in str(queue.last_failure.error)
        assert report.get(timeout=5) != os.getpid()
        assert report.get(timeout=5) != os.getpid()
        assert report.empty()
        assert queue._process is None
    finally:
        queue.shutdown()


# B-QUE-018

def test_start_held_rejects_active_before_status_changes(setup, monkeypatch):
    repo, _, _, _, _, _, create = setup
    held = create("Held")
    queue = queue_for(setup)
    entered, release = LocalEvent(), LocalEvent()
    original_admit = queue._admit

    def pause_admission(identifier):
        entered.set()
        assert release.wait(10)
        return original_admit(identifier)

    monkeypatch.setattr(queue, "_admit", pause_admission)
    try:
        queue.start()
        assert repo.get_experiment(held).status is ExperimentStatus.HELD
        queue.start_held(held)
        assert entered.wait(10)
        assert queue.active_id == held
        assert repo.get_experiment(held).status is ExperimentStatus.HELD
        with pytest.raises(ValueError, match="already enqueued"):
            queue.start_held(held)
        assert queue.pending_ids() == ()
    finally:
        release.set()
        queue.shutdown()


# B-QUE-019

def test_concurrent_held_starts_enqueue_once(setup):
    _, _, _, _, _, _, create = setup
    held = create("Held")
    queue = queue_for(setup)
    gate = Barrier(3)
    outcomes = []

    def start_together():
        gate.wait(timeout=10)
        try:
            queue.start_held(held)
            outcomes.append("queued")
        except ValueError:
            outcomes.append("rejected")

    try:
        queue.start()
        threads = [Thread(target=start_together) for _ in range(2)]
        for thread in threads:
            thread.start()
        gate.wait(timeout=10)
        for thread in threads:
            thread.join(timeout=10)
            assert not thread.is_alive()
        assert sorted(outcomes) == ["queued", "rejected"]
        assert queue.pending_ids().count(held) + int(queue.active_id == held) <= 1
    finally:
        queue.shutdown()


# B-QUE-020

def test_cancel_queued_and_held_without_spawning(setup):
    repo, _, _, entered, release, _, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        active, pending = create("Wait active"), create("Never")
        queue.enqueue(active)
        queue.enqueue(pending)
        assert entered.wait(10)
        queue.cancel(pending)
        assert repo.get_experiment(pending).status is ExperimentStatus.CANCELLED
        assert repo.get_experiment(pending).runs[0].status is RunStatus.NOT_RUN
    finally:
        queue.shutdown()
    held = create("Held")
    restarted = queue_for(setup)
    try:
        restarted.start()
        assert repo.get_experiment(held).status is ExperimentStatus.HELD
        restarted.cancel(held)
        assert repo.get_experiment(held).status is ExperimentStatus.CANCELLED
        assert repo.get_experiment(held).runs[0].status is RunStatus.NOT_RUN
    finally:
        release.set()
        restarted.shutdown()


# B-QUE-021

def test_persisted_quota_reaches_existing_queue_submit_enqueue_and_held_start(setup):
    repo, settings, _, _, _, _, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        existing = create("Existing")
        repo.set_quota_preference(repo.admission_logical_bytes())
        with pytest.raises(Exception, match="quota"):
            queue.submit(
                request("New"),
                history_id="history",
                history_sha256="a" * 64,
                rankings_id="rankings",
                rankings_sha256="b" * 64,
                code_version="v1",
            )
        assert [item.id for item in repo.list_experiments()] == [existing]
        with pytest.raises(Exception, match="quota"):
            queue.enqueue(existing)
        assert queue.pending_ids() == ()
    finally:
        queue.shutdown()
    restarted = JobQueue(repo.path, settings)
    try:
        restarted.start()
        assert repo.get_experiment(existing).status is ExperimentStatus.HELD
        with pytest.raises(Exception, match="quota"):
            restarted.start_held(existing)
        assert restarted.pending_ids() == ()
    finally:
        restarted.shutdown()


# B-QUE-022

def test_explicit_environment_default_wins_over_persisted_limit_at_runtime(setup):
    repo, settings, _, entered, release, report, _ = setup
    queue = JobQueue(
        repo.path,
        replace(settings, quota_explicit=True),
        runner=synthetic,
        runner_args=(entered, release, report),
    )
    try:
        queue.start()
        persisted_limit = repo.admission_logical_bytes()
        repo.set_quota_preference(persisted_limit)
        identifier = queue.submit(
            request("Environment"),
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="v1",
        )
        wait_for(lambda: repo.get_experiment(identifier).status is ExperimentStatus.COMPLETED)
        assert repo.get_experiment(identifier).runs[0].result is not None
        assert repo.get_quota_preference() == persisted_limit
    finally:
        queue.shutdown()


# B-QUE-023

def test_persisted_update_during_active_calculation_blocks_result_without_partial_write(setup):
    repo, _, _, entered, release, _, create = setup
    queue = queue_for(setup)
    try:
        queue.start()
        identifier = create("Wait result")
        queue.enqueue(identifier)
        assert entered.wait(10)
        assert repo.get_experiment(identifier).runs[0].status is RunStatus.RUNNING
        repo.set_quota_preference(repo.admission_logical_bytes())
        release.set()
        wait_for(lambda: queue.last_failure is not None)
        saved = repo.get_experiment(identifier)
        assert saved.status is ExperimentStatus.FAILED
        assert saved.runs[0].result is None
        assert queue.last_failure is not None
        assert queue.last_failure.experiment_id == identifier
    finally:
        release.set()
        queue.shutdown()


# B-QUE-024

def test_next_configuration_rechecks_persisted_limit_after_completed_result(setup, monkeypatch):
    repo, _, _, _, _, report, create = setup
    queue = queue_for(setup)
    complete = queue.repo.complete_run

    def lower_after_first(identifier, ordinal, result, **kwargs):
        complete(identifier, ordinal, result, **kwargs)
        repo.set_quota_preference(repo.admission_logical_bytes())

    monkeypatch.setattr(queue.repo, "complete_run", lower_after_first)
    try:
        queue.start()
        identifier = create("First", "Second")
        queue.enqueue(identifier)
        wait_for(lambda: queue.last_failure is not None)
        saved = repo.get_experiment(identifier)
        assert saved.runs[0].status is RunStatus.COMPLETED
        assert saved.runs[1].result is None
        assert queue.last_failure is not None
        assert "quota" in str(queue.last_failure.error)
        assert report.get(timeout=5) != os.getpid()
        assert report.empty()  # no second calculation was spawned
    finally:
        queue.shutdown()


# B-QUE-026
@pytest.mark.real_data
def test_default_worker_runs_real_engine_in_spawned_process(tmp_path):
    from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256, Settings

    default = Settings.from_environment()
    settings = replace(default, data_dir=tmp_path)
    path = settings.database_path
    initialize_database(path)
    repo = Repository(path)
    real_request = request("Real").model_copy(
        update={
            "conditions": Conditions(
                start_draw="2025-09-02 05:10", capital=2000, goal=2800, seed=42, max_bets=1
            ),
        }
    )
    identifier = repo.create_experiment(
        real_request,
        history_id="history",
        history_sha256=HISTORY_SHA256,
        rankings_id="rankings",
        rankings_sha256=RANKINGS_SHA256,
        code_version="v1",
    )
    queue = JobQueue(path, settings)
    try:
        queue.start()
        # An experiment created before startup is held, never auto-resumed.
        queue.start_held(identifier)
        wait_for(
            lambda: (
                (saved := repo.get_experiment(identifier)) is not None
                and saved.status in (ExperimentStatus.COMPLETED, ExperimentStatus.FAILED)
            ),
            timeout=30,
        )
        saved = repo.get_experiment(identifier)
        assert saved is not None
        assert saved.status is ExperimentStatus.COMPLETED, queue.last_error
        result = saved.runs[0].result
        assert result is not None and result.bets_count == 1
    finally:
        queue.shutdown()


# B-QUE-026
@pytest.mark.real_data
def test_real_engine_unaffordable_snapshot_is_local_after_spawn(tmp_path):
    from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256

    settings = replace(Settings.from_environment(), data_dir=tmp_path)
    initialize_database(settings.database_path)
    repo = Repository(settings.database_path)
    conditions = Conditions(
        start_draw="2025-09-02 05:10", capital=1, goal=2800, seed=42, max_bets=1
    )
    snapshot = ExperimentRequest(
        name="Bypassed preflight",
        conditions=conditions,
        strategies=(strategy("Unfunded").model_copy(update={"coverage": 50}), strategy("Funded")),
    )
    identifier = repo.create_experiment(
        snapshot,
        history_id="history",
        history_sha256=HISTORY_SHA256,
        rankings_id="rankings",
        rankings_sha256=RANKINGS_SHA256,
        code_version="v1",
    )
    queue = JobQueue(repo.path, settings)
    try:
        queue.start()
        queue.start_held(identifier)
        wait_for(
            lambda: repo.get_experiment(identifier).status is ExperimentStatus.FAILED,
            timeout=30,
        )
        saved = repo.get_experiment(identifier)
        assert [r.status for r in saved.runs] == [RunStatus.FAILED, RunStatus.COMPLETED]
        assert saved.runs[1].result is not None
    finally:
        queue.shutdown()


# B-QUE-025

def test_startup_reconciles_abandoned_running_and_pending(setup):
    repo, _, _, _, _, _, create = setup
    interrupted, pending = create("First", "Second"), create("Later")
    repo.start_run(interrupted, 0)
    queue = queue_for(setup)
    try:
        queue.start()
        saved = repo.get_experiment(interrupted)
        assert saved.status is ExperimentStatus.INTERRUPTED
        assert [r.status for r in saved.runs] == [RunStatus.INTERRUPTED, RunStatus.NOT_RUN]
        assert repo.get_experiment(pending).status is ExperimentStatus.HELD
    finally:
        queue.shutdown()
