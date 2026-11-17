"""Past-only features used by the transparent candidate models."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

PAR = "PAR"
IMPAR = "IMPAR"


def parity_label(number: int) -> str:
    """Return the product's stable target labels."""

    return PAR if number % 2 == 0 else IMPAR


def is_par(number_or_label: int | str) -> bool:
    if isinstance(number_or_label, str):
        return number_or_label.upper() == PAR
    return number_or_label % 2 == 0


@dataclass(frozen=True)
class PastFeatures:
    """Features computable from observations strictly before a target."""

    history_length: int
    last_number: int | None
    last_parity: str | None
    run_length: int
    run_bucket: int
    par_count: int
    impar_count: int
    par_rate: float
    recent_numbers: tuple[int, ...]
    recent_parities: tuple[str, ...]

    @property
    def context_description(self) -> str:
        if self.history_length == 0:
            return "no_prior_observations"
        return (
            f"last_number={self.last_number};last_parity={self.last_parity};"
            f"run_bucket={self.run_bucket}"
        )


def _run_length(history: Sequence[int]) -> int:
    if not history:
        return 0
    last = parity_label(history[-1])
    length = 0
    for number in reversed(history):
        if parity_label(number) != last:
            break
        length += 1
    return length


def extract_past_features(
    history: Iterable[int], recent_window: int = 8
) -> PastFeatures:
    """Extract only prefix features; callers must pass the target-exclusive history."""

    if recent_window <= 0:
        raise ValueError("recent_window must be positive")
    values = tuple(history)
    length = len(values)
    last_number = values[-1] if values else None
    last_parity = parity_label(last_number) if last_number is not None else None
    run_length = _run_length(values)
    run_bucket = min(run_length, 4)
    par_count = sum(1 for value in values if value % 2 == 0)
    impar_count = length - par_count
    par_rate = par_count / length if length else 0.5
    recent_numbers = values[-recent_window:]
    recent_parities = tuple(parity_label(value) for value in recent_numbers)
    return PastFeatures(
        history_length=length,
        last_number=last_number,
        last_parity=last_parity,
        run_length=run_length,
        run_bucket=run_bucket,
        par_count=par_count,
        impar_count=impar_count,
        par_rate=par_rate,
        recent_numbers=recent_numbers,
        recent_parities=recent_parities,
    )


def context_keys(features: PastFeatures) -> tuple[tuple[object, ...], ...]:
    """Return hierarchical exact-number and derived-feature contexts.

    The exact-number context is deliberately the prior number, never the target.
    Contexts are ordered from broad to specific for support-aware shrinkage.
    """

    if features.last_number is None:
        return (("GLOBAL",),)
    return (
        ("DERIVED_PARITY_RUN", features.last_parity, features.run_bucket),
        ("DERIVED_PARITY", features.last_parity),
        ("EXACT_NUMBER_RUN", features.last_number, features.run_bucket),
        ("EXACT_NUMBER", features.last_number),
    )


def update_recent_state(
    recent_numbers: deque[int],
    number: int,
    maxlen: int = 8,
) -> None:
    """Small helper for streaming callers that do not want full history storage."""

    if maxlen <= 0:
        raise ValueError("maxlen must be positive")
    recent_numbers.maxlen  # Access documents the bounded-state contract.
    recent_numbers.append(number)
