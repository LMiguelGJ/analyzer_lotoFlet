"""Structural validation for normalized lottery observations."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationSummary:
    """Machine-readable validation result for a flat 0..99 sequence."""

    total_records: int
    valid_records: int
    invalid_records: int
    empty: bool
    in_range: bool
    distinct_values: int
    repeated_draws: int
    order_semantics: str = (
        "input sequence order is preserved; repeated numeric values are observations"
    )


@dataclass(frozen=True)
class ValidationIssue:
    index: int
    code: str
    message: str
    value_preview: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    summary: ValidationSummary
    issues: tuple[ValidationIssue, ...]


def validate_numbers(numbers: Iterable[int], issue_limit: int = 50) -> ValidationResult:
    """Validate range and emptiness without treating repeated draws as duplicates."""

    if issue_limit < 0:
        raise ValueError("issue_limit must be non-negative")

    values = list(numbers)
    issues: list[ValidationIssue] = []
    valid = 0
    for index, value in enumerate(values):
        code: str | None = None
        message: str | None = None
        if isinstance(value, bool) or not isinstance(value, int):
            code = "TYPE_BOUNDARY"
            message = "value must be an integer, not a boolean or another type"
        elif not 0 <= value <= 99:
            code = "OUT_OF_RANGE"
            message = "value must be within inclusive range 0..99"
        else:
            valid += 1
        if code is not None and len(issues) < issue_limit:
            issues.append(
                ValidationIssue(
                    index=index,
                    code=code,
                    message=message or "invalid value",
                    value_preview=repr(value)[:80],
                )
            )

    distinct = len(
        {
            value
            for value in values
            if isinstance(value, int)
            and not isinstance(value, bool)
            and 0 <= value <= 99
        }
    )
    repeated_draws = valid - distinct if valid else 0
    summary = ValidationSummary(
        total_records=len(values),
        valid_records=valid,
        invalid_records=len(values) - valid,
        empty=len(values) == 0,
        in_range=valid == len(values) and bool(values),
        distinct_values=distinct,
        repeated_draws=repeated_draws,
    )
    return ValidationResult(ok=summary.in_range, summary=summary, issues=tuple(issues))


def require_valid_numbers(numbers: Sequence[int]) -> None:
    """Raise a concise error when a caller requires a completely valid sequence."""

    result = validate_numbers(numbers)
    if not result.ok:
        first = result.issues[0] if result.issues else None
        detail = f" at index {first.index}: {first.message}" if first else ""
        raise ValueError(f"number sequence is empty or invalid{detail}")
