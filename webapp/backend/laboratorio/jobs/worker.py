"""Spawn-safe worker entrypoint; never opens SQLite or persists a partial session."""

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
from laboratorio.domain.profile_session import run_profile_session
from laboratorio.domain.session import preflight_initial_stake, run_session
from laboratorio.engine.adapter import DataError, open_lab_data, session_draws


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
