"""One in-process coordinator; one spawned calculation process at a time.

Create only one JobQueue per database. start() reconciles an unowned database before
serving API requests; enqueue() is for newly created pending rows, start_held()
for explicit action after restart. Neither a browser connection nor a request
thread owns the worker lifecycle.
"""

import itertools
import json
import multiprocessing
import shutil
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from laboratorio.domain.contracts import ExperimentStatus, GameProfile, RunStatus
from laboratorio.domain.profile_request import ProfileExperimentRequest, profile_sha256
from laboratorio.domain.profile_request_v2 import ProfileCyclingRequest
from laboratorio.domain.profile_request_v3 import ProfileAudazRequest
from laboratorio.domain.profile_request_v4 import ProfileRecoveryRequest
from laboratorio.domain.profile_result import load_profile_result
from laboratorio.domain.profile_result_v2 import load_profile_cycling_result
from laboratorio.domain.profile_result_v3 import load_profile_audaz_result
from laboratorio.domain.profile_result_v4 import load_profile_recovery_result
from laboratorio.domain.profile_session import MAX_SESSION_ROWS, ProfileDraw, _minute
from laboratorio.jobs.worker import (
    calculate_run,
    process_entry,
    profile_audaz_process_entry,
    profile_cycling_process_entry,
    profile_process_entry,
    profile_recovery_process_entry,
)
from laboratorio.settings import Settings
from laboratorio.storage.quota import QuotaExceeded
from laboratorio.storage.repository import Repository, validate_result_payload

_POLL_SECONDS = 0.05
_STOP_GRACE_SECONDS = 0.5


class StrategyLocalFailure(RuntimeError):
    """A worker explicitly classified this run as independent."""


class SharedWorkerFailure(RuntimeError):
    """A shared input or infrastructure failure stops the coordinator."""


@dataclass(frozen=True)
class QueueFailure:
    experiment_id: str
    error: Exception
    persisted: bool  # Only a committed failed experiment status counts.
    persistence_error: Exception | None = None


class JobQueue:
    def __init__(
        self,
        database_path: Path,
        settings: Settings,
        *,
        runner=calculate_run,
        runner_args=(),
        disk_usage=shutil.disk_usage,
    ):
        self.repo = Repository(database_path)
        self.settings = settings
        self.runner = runner
        self.runner_args = runner_args
        self.disk_usage = disk_usage
        self._ctx = multiprocessing.get_context("spawn")
        self._lock = threading.RLock()
        self._pending = deque()
        self._wake = threading.Event()
        self._stopping = False
        self._thread = None
        self._active = None
        self._cancel = None
        self._process = None
        self.last_error = None
        self.last_failure: QueueFailure | None = None

    def start(self):
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("queue already started")
            self.repo.recover_jobs()
            self._thread = threading.Thread(target=self._loop, name="laboratorio-queue")
            self._thread.start()

    def _require_open(self):
        if self._thread is None or self._stopping:
            raise RuntimeError("queue is not running")

    def enqueue(self, identifier: str):
        with self._lock:
            self._require_open()
            saved = self.repo.get_experiment(identifier)
            if saved is None or saved.status is not ExperimentStatus.PENDING:
                raise ValueError("only a new pending experiment can be enqueued")
            if saved.request_schema_version != 1:
                raise ValueError("stored experiment version is not executable")
            if identifier in self._pending or identifier == self._active:
                raise ValueError("experiment already enqueued")
            self.repo.require_capacity(
                self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            self._pending.append(identifier)
            self._wake.set()

    def _enqueue_profile_cycling(self, identifier: str):
        """Explicit private v2 dispatch; neither startup nor public methods call this."""
        with self._lock:
            self._require_open()
            saved = self.repo.get_experiment(identifier)
            if (
                saved is None
                or saved.request_kind != "profile"
                or saved.request_schema_version != 2
                or type(saved.request) is not ProfileCyclingRequest
                or saved.status not in (ExperimentStatus.PENDING, ExperimentStatus.HELD)
                or len(saved.runs) != 1
                or saved.runs[0].ordinal != 0
                or saved.runs[0].result_kind != "profile"
                or saved.runs[0].status is not RunStatus.PENDING
            ):
                raise ValueError("only a pending or held profile cycling run can be enqueued")
            if identifier in self._pending or identifier == self._active:
                raise ValueError("experiment already enqueued")
            self.repo.require_capacity(
                self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            # start_run accepts held directly; no held->pending repository transition exists.
            self._pending.append(identifier)
            self._wake.set()

    def submit(
        self,
        request,
        *,
        history_id,
        history_sha256,
        rankings_id,
        rankings_sha256,
        code_version,
        configuration_ids=None,
    ):
        """Admit under the queue lock, compensating any failed enqueue."""
        with self._lock:
            self._require_open()
            identifier = self.repo.create_experiment(
                request,
                history_id=history_id,
                history_sha256=history_sha256,
                rankings_id=rankings_id,
                rankings_sha256=rankings_sha256,
                code_version=code_version,
                configuration_ids=configuration_ids,
                quota_bytes=self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            try:
                self.enqueue(identifier)
            except Exception:
                self.repo.discard_pending(identifier)
                raise
            return identifier

    def submit_profile(self, request: ProfileExperimentRequest) -> str:
        """Synchronous admission; an eventual async API must offload this call."""
        with self._lock:
            self._require_open()
            identifier = self.repo.create_profile_experiment(
                request,
                quota_bytes=self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            try:
                self.enqueue(identifier)
            except Exception:
                self.repo.discard_pending(identifier)
                raise
            return identifier

    def submit_profile_audaz(self, request: ProfileAudazRequest) -> str:
        """Admit and schedule a schema-3 audaz session with compensating cleanup."""
        with self._lock:
            self._require_open()
            identifier = self.repo.create_profile_audaz_experiment(
                request,
                quota_bytes=self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            try:
                self._enqueue_profile_audaz(identifier)
            except Exception:
                self.repo.discard_pending(identifier)
                raise
            return identifier

    def _enqueue_profile_audaz(self, identifier: str):
        with self._lock:
            self._require_open()
            saved = self.repo.get_experiment(identifier)
            if (
                saved is None
                or saved.request_kind != "profile"
                or saved.request_schema_version != 3
                or type(saved.request) is not ProfileAudazRequest
                or saved.status not in (ExperimentStatus.PENDING, ExperimentStatus.HELD)
                or len(saved.runs) != 1
                or saved.runs[0].ordinal != 0
                or saved.runs[0].result_kind != "profile"
                or saved.runs[0].status is not RunStatus.PENDING
            ):
                raise ValueError("only a pending or held profile audaz run can be enqueued")
            if identifier in self._pending or identifier == self._active:
                raise ValueError("experiment already enqueued")
            self.repo.require_capacity(
                self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            self._pending.append(identifier)
            self._wake.set()

    def submit_profile_recovery(self, request: ProfileRecoveryRequest) -> str:
        """Admit and schedule schema-4 recovery with compensating cleanup."""
        with self._lock:
            self._require_open()
            identifier = self.repo.create_profile_recovery_experiment(
                request,
                quota_bytes=self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            try:
                self._enqueue_profile_recovery(identifier)
            except Exception:
                self.repo.discard_pending(identifier)
                raise
            return identifier

    def _enqueue_profile_recovery(self, identifier: str):
        with self._lock:
            self._require_open()
            saved = self.repo.get_experiment(identifier)
            if (
                saved is None
                or saved.request_kind != "profile"
                or saved.request_schema_version != 4
                or type(saved.request) is not ProfileRecoveryRequest
                or saved.status not in (ExperimentStatus.PENDING, ExperimentStatus.HELD)
                or len(saved.runs) != 1
                or saved.runs[0].ordinal != 0
                or saved.runs[0].result_kind != "profile"
                or saved.runs[0].status is not RunStatus.PENDING
            ):
                raise ValueError("only a pending or held profile recovery run can be enqueued")
            if identifier in self._pending or identifier == self._active:
                raise ValueError("experiment already enqueued")
            self.repo.require_capacity(
                self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            self._pending.append(identifier)
            self._wake.set()

    def submit_profile_cycling(self, request: ProfileCyclingRequest) -> str:
        """Admit an authenticated v2 request and compensate failed scheduling."""
        with self._lock:
            self._require_open()
            identifier = self.repo.create_profile_cycling_experiment(
                request,
                quota_bytes=self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            try:
                self._enqueue_profile_cycling(identifier)
            except Exception:
                self.repo.discard_pending(identifier)
                raise
            return identifier

    def delete_experiment(self, identifier: str) -> bool:
        with self._lock:
            self._require_open()
            if identifier == self._active or identifier in self._pending:
                raise ValueError("cannot delete an active experiment")
            return self.repo.delete_experiment(identifier)

    def start_held(self, identifier: str):
        with self._lock:
            self._require_open()
            saved = self.repo.get_experiment(identifier)
            if saved is None or saved.status is not ExperimentStatus.HELD:
                raise ValueError("only a held experiment can be started manually")
            if saved.request_schema_version == 2 and saved.request_kind == "profile":
                self._enqueue_profile_cycling(identifier)
                return
            if saved.request_schema_version == 3 and saved.request_kind == "profile":
                self._enqueue_profile_audaz(identifier)
                return
            if saved.request_schema_version == 4 and saved.request_kind == "profile":
                self._enqueue_profile_recovery(identifier)
                return
            if saved.request_schema_version != 1:
                raise ValueError("stored experiment version is not executable")
            if identifier in self._pending or identifier == self._active:
                raise ValueError("experiment already enqueued")
            self.repo.require_capacity(
                self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            self._pending.append(identifier)
            self._wake.set()

    def cancel(self, identifier: str):
        with self._lock:
            self._require_open()
            saved = self.repo.get_experiment(identifier)
            if saved is not None and not (
                saved.request_schema_version == 1
                or (
                    saved.request_kind == "profile"
                    and saved.request_schema_version in (2, 3, 4)
                    and type(saved.request)
                    in (ProfileCyclingRequest, ProfileAudazRequest, ProfileRecoveryRequest)
                )
            ):
                raise ValueError("stored experiment version is not executable")
            if identifier == self._active:
                assert self._cancel is not None
                self._cancel.set()
            elif identifier in self._pending:
                self.repo.finish_incomplete(identifier, ExperimentStatus.CANCELLED)
                self._pending.remove(identifier)
            else:
                saved = self.repo.get_experiment(identifier)
                if saved is None or saved.status is not ExperimentStatus.HELD:
                    raise ValueError("experiment is not active, queued or held")
                self.repo.finish_incomplete(identifier, ExperimentStatus.CANCELLED)
            self._wake.set()

    def pending_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._pending)

    def page_pending_ids(self, offset: int, limit: int) -> tuple[int, list[str]]:
        """Snapshot one page and its total under the coordinator lock."""
        with self._lock:
            total = len(self._pending)
            return total, list(itertools.islice(self._pending, offset, offset + limit))

    @property
    def is_stopped(self) -> bool:
        # The coordinator reaps its child before exiting its thread.
        with self._lock:
            return self._thread is None or not self._thread.is_alive()

    @property
    def active_id(self) -> str | None:
        with self._lock:
            return self._active

    def shutdown(self):
        with self._lock:
            if self._thread is None:
                return
            self._stopping = True
            if self._cancel is not None:
                self._cancel.set()
            self._wake.set()
            thread = self._thread
        thread.join(timeout=15)
        if thread.is_alive():
            raise RuntimeError("queue shutdown timed out; worker needs explicit cleanup")

    def _loop(self):
        while True:
            with self._lock:
                if self._stopping:
                    return
                if self._pending:
                    identifier = self._pending.popleft()
                    self._active = identifier
                    self._cancel = self._ctx.Event()
                else:
                    self._wake.clear()
                    identifier = None
            if identifier is None:
                self._wake.wait()
                continue
            try:
                self._run_experiment(identifier)
            except Exception as exc:
                # One best-effort status transition, never retry on a broken store.
                self._fail(identifier, exc, stop=True)
            finally:
                with self._lock:
                    self._active = None
                    self._cancel = None

    def _fail(self, identifier, exc, *, stop=False, active=True):
        persistence_error = None
        persisted = False
        if active:
            try:
                self.repo.finish_incomplete(identifier, ExperimentStatus.FAILED)
                persisted = True
            except Exception as failure:
                persistence_error = failure
                stop = True
        with self._lock:
            self.last_error = exc
            self.last_failure = QueueFailure(identifier, exc, persisted, persistence_error)
            if stop:
                self._stopping = True

    def _admit(self, identifier):
        try:
            self.repo.require_capacity(
                self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
        except QuotaExceeded as exc:
            saved = self.repo.get_experiment(identifier)
            if saved is not None and saved.status is ExperimentStatus.PENDING:
                try:
                    self.repo.mark_experiment(identifier, ExperimentStatus.HELD)
                except Exception as failure:
                    with self._lock:
                        self.last_failure = QueueFailure(identifier, exc, False, failure)
                        self.last_error = exc
                        self._stopping = True
                    return False
            if saved is not None and saved.status is ExperimentStatus.RUNNING:
                self._fail(identifier, exc, stop=True)
            else:
                self._fail(identifier, exc, stop=True, active=False)
            return False
        return True

    def _prepare_profile(self, saved):
        """Authenticate complete all_rows/v1 input in the parent before spawning."""
        try:
            return self._load_profile_input(saved)
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise SharedWorkerFailure("invalid profile input or immutable binding") from exc

    def _load_profile_input(self, saved):
        request = saved.request
        expected = (
            ProfileExperimentRequest
            if saved.request_schema_version == 1
            else ProfileCyclingRequest
            if saved.request_schema_version == 2
            else ProfileAudazRequest
            if saved.request_schema_version == 3
            else ProfileRecoveryRequest
            if saved.request_schema_version == 4
            else None
        )
        if expected is None or type(request) is not expected or len(saved.runs) != 1:
            raise SharedWorkerFailure("malformed profile request or run count")
        request.__post_init__()
        if saved.runs[0].ordinal != 0 or saved.runs[0].result_kind != "profile":
            raise SharedWorkerFailure("malformed profile run")
        registered = self.repo.get_game_profile(request.profile_id, request.profile_revision)
        if (
            registered is None
            or registered != saved.profile
            or profile_sha256(registered) != request.profile_sha256
        ):
            raise SharedWorkerFailure("profile snapshot differs from registered profile")
        if isinstance(request, ProfileExperimentRequest):
            dataset = self.repo.preflight_profile_dataset(
                request.dataset_sha256,
                registered,
                request.conditions,
                request.selector,
                request.staking,
            )
        else:
            # Cycling staking has no v1 flat-stake preflight. The persisted artifact
            # authenticates every row, including those before the session start.
            dataset = self.repo.get_dataset(request.dataset_sha256)
            if dataset is None:
                raise SharedWorkerFailure("profile dataset missing")
        try:
            embedded = GameProfile.model_validate(json.loads(dataset.canonical_json)["profile"])
        except (ValueError, TypeError, KeyError) as exc:
            raise SharedWorkerFailure("corrupt dataset profile snapshot") from exc
        if (
            embedded != saved.profile
            or saved.history_id != request.dataset_sha256
            or saved.history_sha256 != request.dataset_sha256
            or saved.rankings_id != ""
            or saved.rankings_sha256 != ""
            or saved.code_version != f"profile-v{saved.request_schema_version}"
        ):
            raise SharedWorkerFailure("profile dataset/request binding mismatch")
        records = dataset.preview.records
        if len(records) > MAX_SESSION_ROWS:
            raise SharedWorkerFailure("profile draw row budget exceeded")
        draws = tuple(
            ProfileDraw(
                1,
                f"{row.date} {row.time}",
                _minute(f"{row.date} {row.time}"),
                row.numbers,
                True,
            )
            for row in records
        )
        return registered, request, draws

    def _run_experiment(self, identifier):
        saved = self.repo.get_experiment(identifier)
        if saved is None:
            return
        if (
            (saved.request_kind == "legacy" and saved.request_schema_version != 1)
            or (
                saved.request_kind == "profile" and saved.request_schema_version not in (1, 2, 3, 4)
            )
            or saved.request_kind not in ("legacy", "profile")
        ):
            raise SharedWorkerFailure("stored experiment kind/version is not executable")
        if not self._admit(identifier):
            return
        assert self._cancel is not None
        local_failure = None
        for run in saved.runs:
            if self._stopping:
                break
            if self._cancel.is_set():
                break
            if not self._admit(identifier):
                return
            try:
                prepared = self._prepare_profile(saved) if saved.request_kind == "profile" else None
                self.repo.start_run(identifier, run.ordinal)
                result = self._calculate(saved, run.ordinal, prepared)
            except StrategyLocalFailure as exc:
                try:
                    self.repo.fail_run(identifier, run.ordinal)
                except Exception as failure:
                    self._fail(identifier, failure, stop=True)
                    return
                local_failure = exc
                continue
            except Exception as exc:
                self._fail(
                    identifier,
                    exc,
                    stop=isinstance(exc, (OSError, sqlite3.Error, SharedWorkerFailure)),
                )
                return
            with self._lock:
                if self._stopping or self._cancel.is_set():
                    break
                if result is None:
                    error = self.last_error or RuntimeError("worker returned no result")
                    self._fail(identifier, error)
                    return
                try:
                    complete = (
                        self.repo.complete_profile_cycling_run
                        if saved.request_kind == "profile" and saved.request_schema_version == 2
                        else self.repo.complete_profile_audaz_run
                        if saved.request_kind == "profile" and saved.request_schema_version == 3
                        else self.repo.complete_profile_recovery_run
                        if saved.request_kind == "profile" and saved.request_schema_version == 4
                        else self.repo.complete_profile_run
                        if saved.request_kind == "profile"
                        else self.repo.complete_run
                    )
                    complete(
                        identifier,
                        run.ordinal,
                        result,
                        quota_bytes=self.settings.quota_bytes,
                        quota_explicit=self.settings.is_quota_explicit,
                        disk_usage=self.disk_usage,
                    )
                except Exception as exc:
                    self._fail(
                        identifier,
                        exc,
                        stop=(
                            saved.request_kind == "profile"
                            or isinstance(exc, (QuotaExceeded, OSError, sqlite3.Error))
                        ),
                    )
                    return
        with self._lock:
            if self._stopping:
                # A dequeued but not started job remains pending for recovery.
                current = self.repo.get_experiment(identifier)
                if current is not None and current.status is ExperimentStatus.RUNNING:
                    self.repo.finish_incomplete(identifier, ExperimentStatus.INTERRUPTED)
            elif self._cancel.is_set():
                self.repo.finish_incomplete(identifier, ExperimentStatus.CANCELLED)
            elif local_failure is not None:
                self.repo.fail_experiment_after_runs(identifier)
                self.last_error = local_failure
                self.last_failure = QueueFailure(identifier, local_failure, True)
            else:
                self.repo.complete_experiment(identifier)

    def _calculate(self, saved, ordinal, prepared=None):
        assert self._cancel is not None
        recv, send = self._ctx.Pipe(duplex=False)
        if saved.request_kind == "profile":
            if prepared is None:
                raise SharedWorkerFailure("profile input not prepared")
            target = (
                profile_cycling_process_entry
                if saved.request_schema_version == 2
                else profile_audaz_process_entry
                if saved.request_schema_version == 3
                else profile_recovery_process_entry
                if saved.request_schema_version == 4
                else profile_process_entry
            )
            args = (send, *prepared, self._cancel)
        elif saved.request_kind == "legacy":
            target = process_entry
            args = (
                send,
                self.settings,
                saved.request.conditions,
                saved.request.strategies[ordinal],
                self._cancel,
                self.runner,
                self.runner_args,
            )
        else:
            raise SharedWorkerFailure(f"unsupported request kind: {saved.request_kind!r}")
        process = self._ctx.Process(target=target, args=args, daemon=True)
        try:
            process.start()
            with self._lock:
                self._process = process
            send.close()
            deadline = None
            message = None
            while process.is_alive():
                if self._stopping or self._cancel.is_set():
                    if deadline is None:
                        deadline = time.monotonic() + _STOP_GRACE_SECONDS
                    if time.monotonic() >= deadline:
                        process.terminate()
                if message is None:
                    try:
                        if recv.poll(_POLL_SECONDS):
                            message = recv.recv()
                    except (EOFError, OSError):
                        message = None  # Reap before classifying abnormal exit versus bad IPC.
                process.join(_POLL_SECONDS)
            process.join()
            if self._stopping or self._cancel.is_set():
                return None
            # Only an observed abnormal exit is an independent legacy run failure.
            # A clean exit with no final IPC is a malformed protocol for both kinds.
            exitcode = process.exitcode
            if exitcode is None:
                raise SharedWorkerFailure("worker exit status unavailable after join")
            if exitcode != 0:
                error = RuntimeError(f"worker exited with code {exitcode}")
                if saved.request_kind == "profile":
                    raise SharedWorkerFailure(str(error))
                self.last_error = error
                return None
            if message is None:
                try:
                    if recv.poll(0.1):
                        message = recv.recv()
                except (EOFError, OSError):
                    message = None  # EOF is not a final message, even after a clean exit.
            if message is None:
                raise SharedWorkerFailure("worker exited without a final result")
            if not isinstance(message, tuple) or len(message) != 2:
                raise SharedWorkerFailure("malformed worker message")
            status, value = message
            if status == "completed":
                try:
                    if saved.request_kind == "profile":
                        value = (
                            load_profile_cycling_result(value)
                            if saved.request_schema_version == 2
                            else load_profile_audaz_result(value)
                            if saved.request_schema_version == 3
                            else load_profile_recovery_result(value)
                            if saved.request_schema_version == 4
                            else load_profile_result(value)
                        )
                    else:
                        validate_result_payload(
                            value,
                            saved.request.conditions.capital,
                            saved.request.strategies[ordinal].coverage,
                        )
                except Exception as exc:
                    raise SharedWorkerFailure("malformed worker completed result") from exc
                return value
            if status == "cancelled" and value is None:
                return None
            if status == "failed" and isinstance(value, tuple) and len(value) == 2:
                kind, text = value
                if type(text) is str and text:
                    if kind == "shared":
                        raise SharedWorkerFailure(text)
                    if saved.request_kind == "legacy":
                        if kind == "strategy_local":
                            raise StrategyLocalFailure(text)
                        if kind == "unknown":
                            self.last_error = RuntimeError(text)
                            return None
            raise SharedWorkerFailure("malformed worker failure classification")
        finally:
            if process.pid is not None and process.is_alive():
                process.terminate()
                process.join(1)
                if process.is_alive():
                    process.kill()
                    process.join(1)
            with self._lock:
                self._process = None
            send.close()
            recv.close()
