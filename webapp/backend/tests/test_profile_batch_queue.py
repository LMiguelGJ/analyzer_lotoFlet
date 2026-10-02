"""Queue execution for privately persisted profile batch v5 requests."""

import json
import threading
import time
from dataclasses import replace
from functools import partial
from multiprocessing import get_context
from types import SimpleNamespace

import pytest
from test_batch_admission import _new_repo, _saved_inputs

from laboratorio.domain.batch_admission import StrategyReference, admit_profile_batch
from laboratorio.domain.contracts import ExperimentStatus, RunStatus
from laboratorio.domain.profile_request_v5 import ProfileBatchRequestV5
from laboratorio.domain.profile_session_v5 import ProfileBatchResultV5
from laboratorio.domain.profile_strategy import StrategyDefinition
from laboratorio.jobs.queue import JobQueue
from laboratorio.jobs.worker import profile_batch_process_entry
from laboratorio.settings import Settings


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    pytest.fail("profile batch queue did not reach expected state")


def completed(repo, identifier):
    saved = repo.get_experiment(identifier)
    return saved is not None and saved.status is ExperimentStatus.COMPLETED


def has_status(repo, identifier, status):
    saved = repo.get_experiment(identifier)
    return saved is not None and saved.status is status


def submission_with_three(repo):
    _, _, _, _, original = _saved_inputs(repo, row_count=3)
    refs = list(original.strategy_refs)
    for name, numbers in (("Second", (8,)), ("Third", (9,))):
        saved = repo.create_strategy(StrategyDefinition.static_numbers(name, numbers))
        refs.append(StrategyReference(saved["id"], 1, saved["definition_sha256"]))
    return replace(original, strategy_refs=tuple(refs), max_draws=3, client_request_id="queue-v5")


def fail_first_strategy(send, settings, profile, dataset, request, identity, cancel, budget):
    if request.strategies[0].name == "Static low risk":
        send.send_bytes(
            b'{"version":5,"status":"failed","kind":"strategy_local",'
            b'"reason":"controlled strategy failure"}'
        )
        send.close()
        return
    profile_batch_process_entry(send, settings, profile, dataset, request, identity, cancel, budget)


def pause_second_strategy(
    send, settings, profile, dataset, request, identity, cancel, budget, entered
):
    if request.strategies[0].name == "Second":
        entered.set()
        time.sleep(10)
        send.close()
        return
    profile_batch_process_entry(send, settings, profile, dataset, request, identity, cancel, budget)


def timeout_first_strategy(send, settings, profile, dataset, request, identity, cancel, budget):
    if request.strategies[0].name == "Static low risk":
        time.sleep(10)
        send.close()
        return
    profile_batch_process_entry(send, settings, profile, dataset, request, identity, cancel, budget)


def malformed_second_strategy(send, settings, profile, dataset, request, identity, cancel, budget):
    if request.strategies[0].name == "Second":
        send.send_bytes(b"not-json")
        send.close()
        return
    profile_batch_process_entry(send, settings, profile, dataset, request, identity, cancel, budget)


def oversized_first_strategy(send, settings, profile, dataset, request, identity, cancel, budget):
    if request.strategies[0].name == "Static low risk":
        send.send_bytes(b"x" * (16 * 1024 * 1024 + 1))
        send.close()
        return
    profile_batch_process_entry(send, settings, profile, dataset, request, identity, cancel, budget)


def make_queue(repo, tmp_path):
    settings = Settings(tmp_path, tmp_path / "absent.json", tmp_path / "absent.npz", tmp_path)
    return JobQueue(repo.path, settings)


def test_manual_child_authenticates_archive_frozen_by_mixed_batch(tmp_path, monkeypatch):
    repo = _new_repo(tmp_path)
    _, dataset, _, _, submission = _saved_inputs(repo, row_count=3)
    identifier = admit_profile_batch(repo, submission)
    saved = repo.get_experiment(identifier)
    assert saved is not None and saved.batch_admission is not None
    assert type(saved.request) is ProfileBatchRequestV5
    identity = dict(saved.batch_admission["source_identity"])
    identity.update(
        archive_bound=True,
        archive_history_sha256="trusted-archive",
        archive_rank_row_ids=[0],
    )
    admission = dict(saved.batch_admission)
    admission["source_identity"] = identity
    saved = replace(saved, batch_admission=admission)
    mixed_request = replace(
        saved.request,
        strategies=(StrategyDefinition.reference_cold_25(), *saved.request.strategies),
    )
    child_request = replace(mixed_request, strategies=(mixed_request.strategies[1],))
    trusted_binding = SimpleNamespace(
        history=SimpleNamespace(sha256="trusted-archive"), rank_row_ids=(0,)
    )
    bound = []
    frames = []
    monkeypatch.setattr(
        "laboratorio.jobs.worker.bind_archived_dataset",
        lambda _dataset, _settings: bound.append(_dataset) or trusted_binding,
    )
    monkeypatch.setattr("laboratorio.jobs.worker.run_profile_batch_v5", lambda *a, **k: object())
    monkeypatch.setattr(
        "laboratorio.jobs.worker.serialize_profile_batch_result_v5", lambda _r: "{}"
    )
    writer = SimpleNamespace(send_bytes=frames.append, close=lambda: None)
    settings = Settings(tmp_path, tmp_path / "absent.json", tmp_path / "absent.npz", tmp_path)

    import laboratorio.jobs.worker as worker_module

    worker_module.profile_batch_process_entry(
        writer,
        settings,
        saved.profile,
        dataset,
        child_request,
        identity,
        SimpleNamespace(is_set=lambda: False),
        3,
    )

    assert bound == [dataset]
    assert json.loads(frames[0])["status"] == "completed"


def test_profile_batch_source_value_error_with_unfamiliar_message_is_shared(tmp_path, monkeypatch):
    repo = _new_repo(tmp_path)
    game, dataset, _, _, submission = _saved_inputs(repo, row_count=3)
    identifier = admit_profile_batch(repo, submission)
    saved = repo.get_experiment(identifier)
    assert saved is not None and saved.batch_admission is not None
    monkeypatch.setattr(
        "laboratorio.jobs.worker.bind_archived_dataset",
        lambda *_args: (_ for _ in ()).throw(ValueError("signature digest disagrees")),
    )
    identity = dict(saved.batch_admission["source_identity"])
    identity["archive_bound"] = True
    frames = []
    writer = SimpleNamespace(send_bytes=frames.append, close=lambda: None)
    settings = Settings(tmp_path, tmp_path / "absent.json", tmp_path / "absent.npz", tmp_path)

    import laboratorio.jobs.worker as worker_module

    worker_module.profile_batch_process_entry(
        writer,
        settings,
        game,
        dataset,
        saved.request,
        identity,
        SimpleNamespace(is_set=lambda: False),
        3,
    )

    frame = json.loads(frames[0])
    assert frame["status"] == "failed"
    assert frame["kind"] == "shared"


def test_profile_batch_financial_value_error_is_typed_local_failure(tmp_path):
    repo = _new_repo(tmp_path)
    game, dataset, _, _, submission = _saved_inputs(repo, row_count=3)
    identifier = admit_profile_batch(repo, submission)
    saved = repo.get_experiment(identifier)
    assert saved is not None and saved.batch_admission is not None
    definition = StrategyDefinition.static_numbers("Unaffordable", (7,), stake=2)
    request = replace(
        saved.request,
        conditions=replace(saved.request.conditions, capital=1),
        strategies=(definition,),
    )
    frames = []
    writer = SimpleNamespace(send_bytes=frames.append, close=lambda: None)
    settings = Settings(tmp_path, tmp_path / "absent.json", tmp_path / "absent.npz", tmp_path)

    import laboratorio.jobs.worker as worker_module

    worker_module.profile_batch_process_entry(
        writer,
        settings,
        game,
        dataset,
        request,
        saved.batch_admission["source_identity"],
        SimpleNamespace(is_set=lambda: False),
        3,
    )

    frame = json.loads(frames[0])
    assert frame["status"] == "failed"
    assert frame["kind"] == "strategy_local"


def test_typed_submission_runs_three_ordinals_serially_and_persists_each(tmp_path):
    repo = _new_repo(tmp_path)
    submission = submission_with_three(repo)
    queue = make_queue(repo, tmp_path)
    try:
        queue.start()
        identifier = queue.submit_profile_batch(submission)
        wait_for(lambda: completed(repo, identifier))
        saved = repo.get_experiment(identifier)
        assert saved is not None
        assert [run.ordinal for run in saved.runs] == [0, 1, 2]
        assert all(run.status is RunStatus.COMPLETED for run in saved.runs)
        assert all(type(run.result) is ProfileBatchResultV5 for run in saved.runs)
        batch_results = []
        for run in saved.runs:
            assert type(run.result) is ProfileBatchResultV5
            batch_results.append(run.result)
        assert [result.results[0].ordinal for result in batch_results] == [0, 0, 0]
        assert [result.results[0].definition.name for result in batch_results] == [
            "Static low risk",
            "Second",
            "Third",
        ]
        assert queue.last_failure is None
    finally:
        queue.shutdown()


def test_submission_idempotency_never_enqueues_existing_batch_twice(tmp_path):
    repo = _new_repo(tmp_path)
    submission = submission_with_three(repo)
    queue = make_queue(repo, tmp_path)
    try:
        queue.start()
        identifier = queue.submit_profile_batch(submission)
        again = queue.submit_profile_batch(submission)
        assert again == identifier
        assert len(repo.list_experiments()) == 1
        assert queue.pending_ids().count(identifier) <= 1
        with pytest.raises(ValueError, match="client_request_id"):
            queue.submit_profile_batch(
                replace(
                    submission,
                    conditions=replace(submission.conditions, capital=101),
                )
            )
        wait_for(lambda: completed(repo, identifier))
        assert queue.submit_profile_batch(submission) == identifier
        assert len(repo.list_experiments()) == 1
    finally:
        queue.shutdown()


def test_local_strategy_failure_continues_later_ordinals(tmp_path, monkeypatch):
    repo = _new_repo(tmp_path)
    submission = submission_with_three(repo)
    queue = make_queue(repo, tmp_path)
    monkeypatch.setattr("laboratorio.jobs.queue.profile_batch_process_entry", fail_first_strategy)
    try:
        queue.start()
        identifier = queue.submit_profile_batch(submission)
        wait_for(lambda: has_status(repo, identifier, ExperimentStatus.FAILED))
        saved = repo.get_experiment(identifier)
        assert saved is not None
        assert [run.status for run in saved.runs] == [
            RunStatus.FAILED,
            RunStatus.COMPLETED,
            RunStatus.COMPLETED,
        ]
        assert saved.runs[1].result is not None and saved.runs[2].result is not None
    finally:
        queue.shutdown()


def test_corrupt_worker_result_stops_batch_but_keeps_prior_ordinal(tmp_path, monkeypatch):
    repo = _new_repo(tmp_path)
    submission = submission_with_three(repo)
    queue = make_queue(repo, tmp_path)
    monkeypatch.setattr(
        "laboratorio.jobs.queue.profile_batch_process_entry", malformed_second_strategy
    )
    try:
        queue.start()
        identifier = queue.submit_profile_batch(submission)
        wait_for(lambda: has_status(repo, identifier, ExperimentStatus.FAILED))
        saved = repo.get_experiment(identifier)
        assert saved is not None
        assert [run.status for run in saved.runs] == [
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.NOT_RUN,
        ]
        assert saved.runs[0].result is not None
        assert queue.last_failure is not None
        assert "malformed or oversized" in str(queue.last_failure.error)
    finally:
        queue.shutdown()


def test_oversized_worker_frame_fails_shared_and_does_not_run_later_ordinals(tmp_path, monkeypatch):
    repo = _new_repo(tmp_path)
    submission = submission_with_three(repo)
    queue = make_queue(repo, tmp_path)
    monkeypatch.setattr(
        "laboratorio.jobs.queue.profile_batch_process_entry", oversized_first_strategy
    )
    try:
        queue.start()
        identifier = queue.submit_profile_batch(submission)
        wait_for(lambda: has_status(repo, identifier, ExperimentStatus.FAILED))
        saved = repo.get_experiment(identifier)
        assert saved is not None
        assert [run.status for run in saved.runs] == [
            RunStatus.FAILED,
            RunStatus.NOT_RUN,
            RunStatus.NOT_RUN,
        ]
        assert queue.is_stopped
        assert queue.last_failure is not None
        assert "oversized" in str(queue.last_failure.error)
        assert queue._process is None
    finally:
        queue.shutdown()


def test_cancel_during_child_keeps_completed_ordinal_and_cancels_remainder(tmp_path, monkeypatch):
    repo = _new_repo(tmp_path)
    submission = submission_with_three(repo)
    entered = get_context("spawn").Event()
    queue = make_queue(repo, tmp_path)
    monkeypatch.setattr(
        "laboratorio.jobs.queue.profile_batch_process_entry",
        partial(pause_second_strategy, entered=entered),
    )
    try:
        queue.start()
        identifier = queue.submit_profile_batch(submission)
        assert entered.wait(10)
        queue.cancel(identifier)
        wait_for(lambda: has_status(repo, identifier, ExperimentStatus.CANCELLED))
        saved = repo.get_experiment(identifier)
        assert saved is not None
        assert [run.status for run in saved.runs] == [
            RunStatus.COMPLETED,
            RunStatus.CANCELLED,
            RunStatus.NOT_RUN,
        ]
        assert saved.runs[0].result is not None
        assert queue._process is None
    finally:
        queue.shutdown()


def test_timeout_uses_frozen_admission_policy_not_current_policy(tmp_path, monkeypatch):
    repo = _new_repo(tmp_path)
    repo.update_execution_policy({"run_timeout_seconds": 1}, expected_revision=1)
    submission = submission_with_three(repo)
    queue = make_queue(repo, tmp_path)
    monkeypatch.setattr(
        "laboratorio.jobs.queue.profile_batch_process_entry", timeout_first_strategy
    )
    try:
        queue.start()
        identifier = queue.submit_profile_batch(submission)
        repo.update_execution_policy({"run_timeout_seconds": 3_600}, expected_revision=2)
        wait_for(lambda: has_status(repo, identifier, ExperimentStatus.FAILED))
        saved = repo.get_experiment(identifier)
        assert saved is not None and saved.batch_admission is not None
        assert saved.batch_admission["policy"]["run_timeout_seconds"] == 1
        assert [run.status for run in saved.runs] == [
            RunStatus.FAILED,
            RunStatus.COMPLETED,
            RunStatus.COMPLETED,
        ]
        assert "frozen wall limit" in str(queue.last_error)
    finally:
        queue.shutdown()


@pytest.mark.parametrize("stop_kind", ["cancel", "deadline"])
def test_stalled_frame_receive_observes_cancel_and_frozen_deadline(
    tmp_path, monkeypatch, stop_kind
):
    repo = _new_repo(tmp_path)
    _, _, _, _, submission = _saved_inputs(repo, row_count=3)
    identifier = admit_profile_batch(repo, submission)
    saved = repo.get_experiment(identifier)
    assert saved is not None and saved.batch_admission is not None
    saved = replace(
        saved,
        batch_admission={
            **saved.batch_admission,
            "policy": {"run_timeout_seconds": 1},
        },
    )
    entered = threading.Event()
    release = threading.Event()
    terminated = threading.Event()
    reader_closed = threading.Event()
    writer_closed = threading.Event()
    cancel = threading.Event()

    class BlockingReader:
        def poll(self, _timeout=0):
            return True

        def recv_bytes(self, maxlength=None):
            entered.set()
            release.wait(5)
            return b'{"version":5,"status":"cancelled"}'

        def close(self):
            reader_closed.set()

    class Writer:
        def close(self):
            writer_closed.set()

    class Child:
        pid = 42
        exitcode = None

        def start(self):
            pass

        def is_alive(self):
            return not terminated.is_set()

        def terminate(self):
            terminated.set()
            # A real child exit closes its pipe writer and releases the reader.
            release.set()
            self.exitcode = -15

        def join(self, _timeout=None):
            pass

        def kill(self):
            self.terminate()

    child = Child()
    queue = make_queue(repo, tmp_path)
    queue._cancel = cancel
    monkeypatch.setattr(
        queue,
        "_ctx",
        SimpleNamespace(
            Pipe=lambda duplex=False: (BlockingReader(), Writer()),
            Process=lambda **_kwargs: child,
        ),
    )
    result = []
    done = threading.Event()

    def calculate():
        try:
            result.append(queue._calculate(saved, 0, (saved.profile, object(), None, {})))
        except Exception as exc:  # result is checked after the liveness assertion below
            result.append(exc)
        finally:
            done.set()

    caller = threading.Thread(target=calculate, daemon=True)
    caller.start()
    try:
        assert entered.wait(2), "the frame receive was not entered"
        if stop_kind == "cancel":
            cancel.set()
            responsive_within = 1.2
        else:
            responsive_within = 1.5
        assert done.wait(responsive_within), (
            f"{stop_kind} did not interrupt the stalled frame receive before fixture release"
        )
        if stop_kind == "cancel":
            assert result == [None]
        else:
            assert len(result) == 1
            assert type(result[0]).__name__ == "StrategyLocalFailure"
            assert "frozen wall limit" in str(result[0])
        assert terminated.is_set()
        assert writer_closed.is_set()
        assert reader_closed.is_set()
        assert not any(
            thread.name == "laboratorio-profile-batch-reader" and thread.is_alive()
            for thread in threading.enumerate()
        )
    finally:
        # On the pre-fix implementation this releases recv_bytes after recording RED.
        release.set()
        caller.join(3)
        queue._process = None
        queue._cancel = None
        assert not caller.is_alive(), "test fixture failed to release the blocked receive"


def test_enqueue_failure_compensates_batch_and_allows_same_identity_retry(tmp_path, monkeypatch):
    repo = _new_repo(tmp_path)
    submission = submission_with_three(repo)
    queue = make_queue(repo, tmp_path)
    try:
        queue.start()
        original = queue._enqueue_profile_batch

        def fail_enqueue(_identifier):
            raise RuntimeError("enqueue failed")

        monkeypatch.setattr(queue, "_enqueue_profile_batch", fail_enqueue)
        with pytest.raises(RuntimeError, match="enqueue failed"):
            queue.submit_profile_batch(submission)
        assert repo.list_experiments() == []
        assert queue.pending_ids() == ()
        monkeypatch.setattr(queue, "_enqueue_profile_batch", original)
        identifier = queue.submit_profile_batch(submission)
        wait_for(lambda: completed(repo, identifier))
    finally:
        queue.shutdown()
