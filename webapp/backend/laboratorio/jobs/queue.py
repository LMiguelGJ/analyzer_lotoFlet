"""One in-process coordinator; one spawned calculation process at a time.

Create only one JobQueue per database. start() reconciles an unowned database before
serving API requests; enqueue() is for newly created pending rows, start_held()
for explicit action after restart. Neither a browser connection nor a request
thread owns the worker lifecycle.
"""

import itertools
import multiprocessing
import shutil
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from laboratorio.domain.contracts import ExperimentStatus
from laboratorio.jobs.worker import calculate_run, process_entry
from laboratorio.settings import Settings
from laboratorio.storage.quota import QuotaExceeded
from laboratorio.storage.repository import Repository

_POLL_SECONDS = 0.05
_STOP_GRACE_SECONDS = 0.5


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
            if identifier in self._pending or identifier == self._active:
                raise ValueError("experiment already enqueued")
            self.repo.require_capacity(
                self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
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

    def _run_experiment(self, identifier):
        saved = self.repo.get_experiment(identifier)
        if saved is None or not self._admit(identifier):
            return
        assert self._cancel is not None
        for run in saved.runs:
            if self._stopping:
                break
            if self._cancel.is_set():
                break
            if not self._admit(identifier):
                return
            try:
                self.repo.start_run(identifier, run.ordinal)
                result = self._calculate(saved, run.ordinal)
            except Exception as exc:
                self._fail(identifier, exc, stop=isinstance(exc, (OSError, sqlite3.Error)))
                return
            with self._lock:
                if self._stopping or self._cancel.is_set():
                    break
                if result is None:
                    error = self.last_error or RuntimeError("worker returned no result")
                    self._fail(identifier, error)
                    return
                try:
                    self.repo.complete_run(
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
                        stop=isinstance(exc, (QuotaExceeded, OSError, sqlite3.Error)),
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
            else:
                self.repo.complete_experiment(identifier)

    def _calculate(self, saved, ordinal):
        assert self._cancel is not None
        recv, send = self._ctx.Pipe(duplex=False)
        process = self._ctx.Process(
            target=process_entry,
            args=(
                send,
                self.settings,
                saved.request.conditions,
                saved.request.strategies[ordinal],
                self._cancel,
                self.runner,
                self.runner_args,
            ),
            daemon=True,
        )
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
                if message is None and recv.poll(_POLL_SECONDS):
                    try:
                        message = recv.recv()
                    except (EOFError, OSError):
                        pass
                process.join(_POLL_SECONDS)
            process.join()
            if self._stopping or self._cancel.is_set():
                return None
            if process.exitcode != 0:
                self.last_error = RuntimeError(f"worker exited with code {process.exitcode}")
                return None
            if message is None and recv.poll(0.1):
                try:
                    message = recv.recv()
                except (EOFError, OSError):
                    return None
            if message is None:
                self.last_error = RuntimeError("worker exited without a final result")
                return None
            status, value = message
            if status != "completed":
                if status == "failed":
                    self.last_error = RuntimeError(value)
                return None
            return value
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
