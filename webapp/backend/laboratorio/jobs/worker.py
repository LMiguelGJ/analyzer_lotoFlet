"""Spawn-safe worker entrypoint; never opens SQLite or persists a partial session."""

from laboratorio.domain.session import run_session
from laboratorio.engine.adapter import open_lab_data, session_draws


class CalculationCancelled(Exception):
    """The parent requested cancellation at a draw boundary."""


def calculate_run(settings, conditions, strategy, cancel):
    data = open_lab_data(settings)

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

    return run_session(conditions, strategy, checked_draws())


def process_entry(send, settings, conditions, strategy, cancel, runner, runner_args):
    """Only a final result crosses IPC; the parent alone writes SQLite."""
    try:
        result = runner(settings, conditions, strategy, cancel, *runner_args)
        if cancel.is_set() or result is None:
            send.send(("cancelled", None))
        else:
            send.send(("completed", result))
    except CalculationCancelled:
        send.send(("cancelled", None))
    except Exception as exc:
        send.send(("failed", f"{type(exc).__name__}: {exc}"))
    finally:
        send.close()
