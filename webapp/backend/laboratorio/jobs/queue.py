"""One in-process coordinator; one spawned calculation process at a time.

Create only one JobQueue per database. start() reconciles an unowned database before
serving API requests; enqueue() is for newly created pending rows, start_held()
for explicit action after restart. Neither a browser connection nor a request
thread owns the worker lifecycle.
"""

import hashlib
import itertools
import json
import multiprocessing
import queue as thread_queue
import shutil
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path

from laboratorio.domain.batch_admission import (
    ProfileBatchSubmission,
    _conditions_dict,
    admit_profile_batch,
)
from laboratorio.domain.contracts import ExperimentStatus, GameProfile, RunStatus
from laboratorio.domain.profile_archive import bind_archived_dataset
from laboratorio.domain.profile_request import ProfileExperimentRequest, profile_sha256
from laboratorio.domain.profile_request_v2 import ProfileCyclingRequest
from laboratorio.domain.profile_request_v3 import ProfileAudazRequest
from laboratorio.domain.profile_request_v4 import ProfileRecoveryRequest
from laboratorio.domain.profile_request_v5 import ProfileBatchRequestV5
from laboratorio.domain.profile_result import load_profile_result
from laboratorio.domain.profile_result_v2 import load_profile_cycling_result
from laboratorio.domain.profile_result_v3 import load_profile_audaz_result
from laboratorio.domain.profile_result_v4 import load_profile_recovery_result
from laboratorio.domain.profile_result_v5 import load_profile_batch_result_v5
from laboratorio.domain.profile_session import MAX_SESSION_ROWS, ProfileDraw, _minute
from laboratorio.jobs.worker import (
    calculate_run,
    process_entry,
    profile_audaz_process_entry,
    profile_batch_process_entry,
    profile_cycling_process_entry,
    profile_process_entry,
    profile_recovery_process_entry,
)
from laboratorio.settings import Settings
from laboratorio.storage.quota import QuotaExceeded
from laboratorio.storage.repository import (
    Repository,
    _batch_identity_hash,
    validate_result_payload,
)

_POLL_SECONDS = 0.05
_STOP_GRACE_SECONDS = 0.5
# Bounds decoded v5 results before parsing; legacy pipe payloads remain unchanged.
_MAX_PROFILE_BATCH_FRAME_BYTES = 16 * 1024 * 1024


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


def _decode_profile_batch_frame(frame: bytes) -> tuple[str, object]:
    """Decode a bounded primitive-only v5 frame into the coordinator protocol."""
    try:
        decoded = json.loads(frame.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid profile batch worker JSON frame") from exc
    if (
        type(decoded) is not dict
        or type(decoded.get("version")) is not int
        or decoded["version"] != 5
    ):
        raise ValueError("unsupported profile batch worker frame")
    status = decoded.get("status")
    if status == "completed" and set(decoded) == {"version", "status", "value"}:
        return status, decoded["value"]
    if status == "cancelled" and set(decoded) == {"version", "status"}:
        return status, None
    if (
        status == "failed"
        and set(decoded) == {"version", "status", "kind", "reason"}
        and decoded["kind"] in ("shared", "strategy_local")
        and type(decoded["reason"]) is str
        and decoded["reason"]
    ):
        return status, (decoded["kind"], decoded["reason"])
    raise ValueError("malformed profile batch worker frame")


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

    def submit_profile_batch(self, submission: ProfileBatchSubmission) -> str:
        """Admit and enqueue one immutable v5 batch without duplicating retries."""
        if type(submission) is not ProfileBatchSubmission:
            raise TypeError("submission must be a closed ProfileBatchSubmission")
        submission.__post_init__()
        requested = {
            **_conditions_dict(submission.conditions),
            "max_draws": submission.max_draws,
        }
        digest = _batch_identity_hash(
            submission.profile_id,
            submission.profile_revision,
            submission.profile_sha256,
            submission.dataset_sha256,
            tuple(reference.as_dict() for reference in submission.strategy_refs),
            requested,
        )
        with self._lock:
            self._require_open()
            existing = self.repo.find_profile_batch_request(submission.client_request_id, digest)
            if existing is not None:
                return existing
            identifier = admit_profile_batch(
                self.repo,
                submission,
                settings=self.settings,
                quota_bytes=self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            # Admission can return an identity created concurrently by another caller.
            saved = self.repo.get_experiment(identifier)
            if saved is None or saved.status is not ExperimentStatus.PENDING:
                return identifier
            try:
                self._enqueue_profile_batch(identifier)
            except Exception:
                if identifier in self._pending:
                    self._pending.remove(identifier)
                self.repo.discard_pending(identifier)
                raise
            return identifier

    def _enqueue_profile_batch(self, identifier: str):
        with self._lock:
            self._require_open()
            saved = self.repo.get_experiment(identifier)
            if (
                saved is None
                or saved.request_kind != "profile"
                or saved.request_schema_version != 5
                or type(saved.request) is not ProfileBatchRequestV5
                or saved.status not in (ExperimentStatus.PENDING, ExperimentStatus.HELD)
                or len(saved.runs) != len(saved.request.strategies)
                or any(
                    run.ordinal != ordinal
                    or run.result_kind != "profile"
                    or run.status is not RunStatus.PENDING
                    for ordinal, run in enumerate(saved.runs)
                )
            ):
                raise ValueError("only a pending profile batch with ordered runs can be enqueued")
            if identifier in self._pending or identifier == self._active:
                raise ValueError("experiment already enqueued")
            self.repo.require_capacity(
                self.settings.quota_bytes,
                quota_explicit=self.settings.is_quota_explicit,
                disk_usage=self.disk_usage,
            )
            self._pending.append(identifier)
            self._wake.set()

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
                    and saved.request_schema_version in (2, 3, 4, 5)
                    and type(saved.request)
                    in (
                        ProfileCyclingRequest,
                        ProfileAudazRequest,
                        ProfileRecoveryRequest,
                        ProfileBatchRequestV5,
                    )
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

    def _prepare_profile_batch(self, saved):
        """Authenticate complete v5 snapshots and frozen source identity before spawn."""
        from laboratorio.domain.profile_request import profile_sha256
        from laboratorio.importing.datasets import SavedDataset

        request = saved.request
        if (
            saved.request_kind != "profile"
            or saved.request_schema_version != 5
            or type(request) is not ProfileBatchRequestV5
            or len(saved.runs) != len(request.strategies)
            or saved.batch_admission is None
        ):
            raise SharedWorkerFailure("malformed profile batch request or run count")
        request.__post_init__()
        registered = self.repo.get_game_profile(request.profile_id, request.profile_revision)
        dataset = self.repo.get_dataset(request.dataset_sha256)
        if (
            registered is None
            or registered != saved.profile
            or profile_sha256(registered) != request.profile_sha256
            or type(dataset) is not SavedDataset
            or saved.history_id != request.dataset_sha256
            or saved.history_sha256 != request.dataset_sha256
            or saved.rankings_id != ""
            or saved.rankings_sha256 != ""
            or saved.code_version != "profile-v5"
        ):
            raise SharedWorkerFailure("profile batch registered context mismatch")
        admission = saved.batch_admission
        identity = admission.get("source_identity")
        if (
            type(identity) is not dict
            or identity.get("dataset_sha256") != dataset.dataset_sha256
            or identity.get("source_sha256") != dataset.source_sha256
            or identity.get("canonical_sha256")
            != hashlib.sha256(dataset.canonical_json).hexdigest()
            or identity.get("profile_id") != registered.profile_id
            or identity.get("profile_revision") != registered.revision
            or identity.get("profile_sha256") != request.profile_sha256
            or type(identity.get("row_count")) is not int
            or identity["row_count"] != len(dataset.preview.records)
        ):
            raise SharedWorkerFailure("profile batch frozen source identity mismatch")
        needs_archive = any(item.selector.startswith("archived-") for item in request.strategies)
        binding = bind_archived_dataset(dataset, self.settings) if needs_archive else None
        if identity.get("archive_bound") != (binding is not None) or (
            binding is not None
            and (
                identity.get("archive_history_sha256") != binding.history.sha256
                or identity.get("archive_rank_row_ids") != list(binding.rank_row_ids)
            )
        ):
            raise SharedWorkerFailure("profile batch archive differs from frozen admission")
        return registered, dataset, binding, identity

    def _run_experiment(self, identifier):
        saved = self.repo.get_experiment(identifier)
        if saved is None:
            return
        if (
            (saved.request_kind == "legacy" and saved.request_schema_version != 1)
            or (
                saved.request_kind == "profile"
                and saved.request_schema_version not in (1, 2, 3, 4, 5)
            )
            or saved.request_kind not in ("legacy", "profile")
        ):
            raise SharedWorkerFailure("stored experiment kind/version is not executable")
        if not self._admit(identifier):
            return
        assert self._cancel is not None
        local_failure = None
        batch_prepared = (
            self._prepare_profile_batch(saved) if saved.request_schema_version == 5 else None
        )
        for run in saved.runs:
            if self._stopping:
                break
            if self._cancel.is_set():
                break
            if not self._admit(identifier):
                return
            try:
                prepared = (
                    batch_prepared
                    if saved.request_schema_version == 5
                    else self._prepare_profile(saved)
                    if saved.request_kind == "profile"
                    else None
                )
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
                        else self.repo.complete_profile_batch_run
                        if saved.request_kind == "profile" and saved.request_schema_version == 5
                        else self.repo.complete_profile_run
                        if saved.request_kind == "profile"
                        else self.repo.complete_run
                    )
                    complete(
                        identifier,
                        run.ordinal,
                        result,
                        **(
                            {"settings": self.settings} if saved.request_schema_version == 5 else {}
                        ),
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
            if saved.request_schema_version == 5:
                profile, dataset, _binding, source_identity = prepared
                single = replace(
                    saved.request,
                    strategies=(saved.request.strategies[ordinal],),
                )
                target = profile_batch_process_entry
                args = (
                    send,
                    self.settings,
                    profile,
                    dataset,
                    single,
                    source_identity,
                    self._cancel,
                    saved.request.max_draws,
                )
            else:
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
        reader_thread = None
        try:
            process.start()
            with self._lock:
                self._process = process
            send.close()
            stop_deadline = None
            batch_policy = (
                saved.batch_admission.get("policy", {})
                if saved.request_schema_version == 5 and saved.batch_admission
                else {}
            )
            timeout_seconds = batch_policy.get("run_timeout_seconds")
            worker_deadline = (
                time.monotonic() + timeout_seconds
                if type(timeout_seconds) is int and timeout_seconds > 0
                else None
            )
            timed_out = False
            message = None
            reader_result = thread_queue.Queue(maxsize=1)

            def start_profile_batch_reader():
                def receive_frame():
                    try:
                        reader_result.put(
                            (True, recv.recv_bytes(maxlength=_MAX_PROFILE_BATCH_FRAME_BYTES))
                        )
                    except Exception as exc:
                        reader_result.put((False, exc))

                nonlocal reader_thread
                reader_thread = threading.Thread(
                    target=receive_frame,
                    name="laboratorio-profile-batch-reader",
                    daemon=True,
                )
                reader_thread.start()

            def collect_profile_batch_frame():
                nonlocal message
                try:
                    received, value = reader_result.get_nowait()
                except thread_queue.Empty:
                    return
                if received:
                    try:
                        message = _decode_profile_batch_frame(value)
                    except (ValueError, UnicodeDecodeError) as exc:
                        raise SharedWorkerFailure(
                            "malformed or oversized profile batch worker frame"
                        ) from exc
                elif isinstance(value, EOFError):
                    message = None
                elif isinstance(value, (OSError, ValueError, UnicodeDecodeError)):
                    raise SharedWorkerFailure(
                        "malformed or oversized profile batch worker frame"
                    ) from value
                else:
                    raise SharedWorkerFailure(
                        "profile batch worker frame receive failed"
                    ) from value

            while process.is_alive():
                if self._stopping or self._cancel.is_set():
                    if stop_deadline is None:
                        stop_deadline = time.monotonic() + _STOP_GRACE_SECONDS
                    if time.monotonic() >= stop_deadline:
                        process.terminate()
                elif worker_deadline is not None and time.monotonic() >= worker_deadline:
                    timed_out = True
                    process.terminate()
                if message is None:
                    try:
                        if saved.request_schema_version == 5:
                            if reader_thread is None and recv.poll(_POLL_SECONDS):
                                start_profile_batch_reader()
                            elif reader_thread is not None:
                                collect_profile_batch_frame()
                        elif recv.poll(_POLL_SECONDS):
                            message = recv.recv()
                    except EOFError:
                        # Cancellation/timeout may intentionally terminate the child.
                        message = None
                    except (OSError, ValueError, UnicodeDecodeError) as exc:
                        if saved.request_schema_version == 5:
                            raise SharedWorkerFailure(
                                "malformed or oversized profile batch worker frame"
                            ) from exc
                        message = None  # Reap before classifying abnormal exit versus bad IPC.
                process.join(_POLL_SECONDS)
            process.join()
            if self._stopping or self._cancel.is_set():
                return None
            if timed_out:
                raise StrategyLocalFailure("profile batch run exceeded its frozen wall limit")
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
                    if saved.request_schema_version == 5:
                        if reader_thread is None and recv.poll(0.1):
                            start_profile_batch_reader()
                        if reader_thread is not None:
                            reader_thread.join(1)
                            collect_profile_batch_frame()
                            if reader_thread.is_alive():
                                raise SharedWorkerFailure(
                                    "profile batch worker frame reader did not stop after exit"
                                )
                    elif recv.poll(0.1):
                        message = recv.recv()
                except EOFError:
                    message = None  # EOF is not a final message, even after a clean exit.
                except (OSError, ValueError, UnicodeDecodeError) as exc:
                    if saved.request_schema_version == 5:
                        raise SharedWorkerFailure(
                            "malformed or oversized profile batch worker frame"
                        ) from exc
                    message = None  # Legacy receives still defer classification until child reap.
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
                            else load_profile_batch_result_v5(value)
                            if saved.request_schema_version == 5
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
                    elif saved.request_schema_version == 5 and kind == "strategy_local":
                        raise StrategyLocalFailure(text)
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
            if reader_thread is not None:
                reader_thread.join(1)
                if reader_thread.is_alive():
                    raise SharedWorkerFailure(
                        "profile batch worker frame reader leaked after pipe close"
                    )
