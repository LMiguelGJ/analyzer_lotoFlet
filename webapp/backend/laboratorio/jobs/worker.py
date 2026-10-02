"""Spawn-safe worker entrypoint; never opens SQLite or persists a partial session."""

import hashlib
import json

from laboratorio.domain.contracts import GameProfile
from laboratorio.domain.profile_archive import bind_archived_dataset
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.profile_request_v5 import ProfileBatchRequestV5
from laboratorio.domain.profile_result import serialize_profile_result
from laboratorio.domain.profile_result_v2 import (
    ProfileCyclingResult,
    serialize_profile_cycling_result,
)
from laboratorio.domain.profile_result_v3 import (
    ProfileAudazResult,
    serialize_profile_audaz_result,
)
from laboratorio.domain.profile_result_v4 import (
    ProfileRecoveryResult,
    serialize_profile_recovery_result,
)
from laboratorio.domain.profile_result_v5 import serialize_profile_batch_result_v5
from laboratorio.domain.profile_session import run_profile_session
from laboratorio.domain.profile_session_v5 import (
    StrategyCalculationFailure,
    run_profile_batch_v5,
)
from laboratorio.domain.profile_strategy import StrategyDefinition
from laboratorio.domain.session import preflight_initial_stake, run_session
from laboratorio.engine.adapter import DataError, open_lab_data, session_draws
from laboratorio.importing.datasets import SavedDataset
from laboratorio.settings import Settings


class CalculationCancelled(Exception):
    """The parent requested cancellation at a draw boundary."""


class StrategyLocalError(Exception):
    """A strategy cannot place its first bet; other strategies are independent."""


class SharedCalculationError(Exception):
    """The verified draw stream or engine invariants are not trustworthy."""


def calculate_run(settings, conditions, strategy, cancel):
    data = open_lab_data(settings)
    # The pure preflight has two strategy-specific ValueError paths: ladder margin
    # and first-bet affordability. Draw/integrity ValueErrors are never localized.
    try:
        preflight_initial_stake(conditions, strategy)
    except ValueError as exc:
        raise StrategyLocalError(str(exc)) from exc

    def checked_draws():
        rows = iter(session_draws(data, strategy, conditions))
        while True:
            if cancel.is_set():
                raise CalculationCancelled
            try:
                draw = next(rows)
            except StopIteration:
                return
            if cancel.is_set():
                raise CalculationCancelled
            yield draw

    try:
        return run_session(conditions, strategy, checked_draws())
    except ValueError as exc:
        # All known ValueErrors past the first-bet preflight concern draw/order
        # integrity. Treat any new engine ValueError conservatively as shared.
        raise SharedCalculationError(str(exc)) from exc


def profile_process_entry(send, profile, request, draws, cancel):
    """Profile calculation consumes only the parent's immutable prepared snapshot.

    The pure runner has no cancellation callback. The coordinator discards a result
    after cancellation and terminates an unresponsive process after its grace period.
    """
    try:
        result = run_profile_session(
            profile, request.conditions, request.selector, request.staking, draws
        )
        if cancel.is_set():
            send.send(("cancelled", None))
        else:
            send.send(("completed", serialize_profile_result(result)))
    except Exception as exc:
        send.send(("failed", ("shared", f"{type(exc).__name__}: {exc}")))
    finally:
        send.close()


def profile_cycling_process_entry(send, profile, request, draws, cancel):
    """Private schema-2 calculation; the parent authenticates and replays the artifact."""
    try:
        session = run_profile_session(
            profile, request.conditions, request.selector, request.staking, draws
        )
        if cancel.is_set():
            send.send(("cancelled", None))
        else:
            result = ProfileCyclingResult("profile", 2, session)
            send.send(("completed", serialize_profile_cycling_result(result)))
    except Exception as exc:
        send.send(("failed", ("shared", f"{type(exc).__name__}: {exc}")))
    finally:
        send.close()


def profile_audaz_process_entry(send, profile, request, draws, cancel):
    """Spawn-safe schema-3 execution; parent independently authenticates replay."""
    try:
        session = run_profile_session(
            profile, request.conditions, request.selector, request.staking, draws
        )
        if cancel.is_set():
            send.send(("cancelled", None))
        else:
            result = ProfileAudazResult("profile", 3, session)
            send.send(("completed", serialize_profile_audaz_result(result)))
    except Exception as exc:
        send.send(("failed", ("shared", f"{type(exc).__name__}: {exc}")))
    finally:
        send.close()


def profile_recovery_process_entry(send, profile, request, draws, cancel):
    """Spawn-safe schema-4 execution; the parent authenticates and replays the artifact."""
    try:
        session = run_profile_session(
            profile, request.conditions, request.selector, request.staking, draws
        )
        if cancel.is_set():
            send.send(("cancelled", None))
        else:
            send.send(
                (
                    "completed",
                    serialize_profile_recovery_result(ProfileRecoveryResult("profile", 4, session)),
                )
            )
    except Exception as exc:
        send.send(("failed", ("shared", f"{type(exc).__name__}: {exc}")))
    finally:
        send.close()


def profile_batch_process_entry(
    send, settings, profile, dataset, request, expected_identity, cancel, operation_budget
):
    """Run exactly one frozen strategy; authenticate all shared context in the child."""
    try:
        if (
            type(settings) is not Settings
            or type(profile) is not GameProfile
            or type(dataset) is not SavedDataset
            or type(request) is not ProfileBatchRequestV5
            or type(expected_identity) is not dict
            or type(request.strategies) is not tuple
            or len(request.strategies) != 1
            or type(request.strategies[0]) is not StrategyDefinition
        ):
            raise SharedCalculationError("profile batch worker context is malformed")
        request.__post_init__()
        if (
            profile.profile_id != request.profile_id
            or profile.revision != request.profile_revision
            or profile_sha256(profile) != request.profile_sha256
            or dataset.dataset_sha256 != request.dataset_sha256
            or hashlib.sha256(dataset.canonical_json).hexdigest() != dataset.dataset_sha256
            or hashlib.sha256(dataset.raw_bytes).hexdigest() != dataset.source_sha256
            or expected_identity.get("dataset_sha256") != dataset.dataset_sha256
            or expected_identity.get("source_sha256") != dataset.source_sha256
            or expected_identity.get("canonical_sha256")
            != hashlib.sha256(dataset.canonical_json).hexdigest()
            or expected_identity.get("profile_id") != profile.profile_id
            or expected_identity.get("profile_revision") != profile.revision
            or expected_identity.get("profile_sha256") != request.profile_sha256
            or expected_identity.get("row_count") != len(dataset.preview.records)
        ):
            raise SharedCalculationError("profile batch frozen source or profile identity mismatch")
        envelope = json.loads(dataset.canonical_json)
        embedded = GameProfile.model_validate(envelope["profile"])
        if embedded != profile:
            raise SharedCalculationError("profile batch dataset profile snapshot mismatch")
        archive_bound = expected_identity.get("archive_bound")
        needs_archive = (type(archive_bound) is bool and archive_bound) or any(
            strategy.selector.startswith("archived-") for strategy in request.strategies
        )
        binding = bind_archived_dataset(dataset, settings) if needs_archive else None
        if expected_identity.get("archive_bound") != (binding is not None) or (
            binding is not None
            and (
                expected_identity.get("archive_history_sha256") != binding.history.sha256
                or expected_identity.get("archive_rank_row_ids") != list(binding.rank_row_ids)
            )
        ):
            raise SharedCalculationError(
                "profile batch archive binding differs from frozen admission"
            )
        try:
            result = run_profile_batch_v5(
                request, profile, dataset, binding, operation_budget=operation_budget
            )
        except StrategyCalculationFailure as exc:
            raise StrategyLocalError(str(exc)) from exc
        if cancel.is_set():
            _send_profile_batch_frame(send, "cancelled")
        else:
            _send_profile_batch_frame(send, "completed", serialize_profile_batch_result_v5(result))
    except StrategyLocalError as exc:
        _send_profile_batch_frame(send, "failed", kind="strategy_local", reason=str(exc))
    except Exception as exc:
        _send_profile_batch_frame(
            send, "failed", kind="shared", reason=f"{type(exc).__name__}: {exc}"
        )
    finally:
        send.close()


def _send_profile_batch_frame(send, status, value=None, *, kind=None, reason=None):
    """Send a JSON-only v5 frame; no Python object or exception crosses the pipe."""
    frame = {"version": 5, "status": status}
    if status == "completed":
        frame["value"] = value
    elif status == "failed":
        frame["kind"] = kind
        frame["reason"] = reason
    send.send_bytes(json.dumps(frame, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def process_entry(send, settings, conditions, strategy, cancel, runner, runner_args):
    """Only a final result crosses IPC; the parent alone writes SQLite."""
    try:
        result = runner(settings, conditions, strategy, cancel, *runner_args)
        if cancel.is_set():
            send.send(("cancelled", None))
        else:
            # A runner returning None without cancellation is not a valid result.
            # Let the parent reject it through the completed-payload validator.
            send.send(("completed", result))
    except CalculationCancelled:
        send.send(("cancelled", None))
    except Exception as exc:
        if isinstance(exc, StrategyLocalError):
            kind = "strategy_local"
        elif isinstance(exc, (DataError, SharedCalculationError, OSError)):
            kind = "shared"
        else:
            kind = "unknown"
        # Primitive-only IPC contract; never pickle exceptions or tracebacks.
        send.send(("failed", (kind, f"{type(exc).__name__}: {exc}")))
    finally:
        send.close()
