"""Load and normalize the legacy flat number list without inventing chronology."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QualityWarning:
    """A bounded, human-readable description of one input-quality issue."""

    index: int
    code: str
    message: str
    raw_type: str
    raw_preview: str


@dataclass(frozen=True)
class DataQualitySummary:
    """Counts describing normalization without retaining every invalid value."""

    total_records: int
    valid_records: int
    invalid_records: int
    converted_records: int
    type_boundary_warnings: int
    out_of_range_warnings: int
    parse_warnings: int
    warning_count: int
    order_semantics: str = (
        "list order is the only temporal order; dates and IDs are absent"
    )

    @property
    def has_warnings(self) -> bool:
        return self.warning_count > 0

    @property
    def is_usable(self) -> bool:
        return self.valid_records > 0 and self.invalid_records == 0


@dataclass(frozen=True)
class NormalizationResult:
    """Normalized valid values plus bounded warnings and aggregate quality data."""

    numbers: list[int]
    warnings: tuple[QualityWarning, ...]
    summary: DataQualitySummary


class DataLoadError(ValueError):
    """Raised when the JSON document cannot be interpreted as a flat list."""


def _preview(value: Any, limit: int = 80) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _normalize_one(value: Any) -> tuple[int | None, str | None, str | None, bool]:
    """Return ``(number, code, message, converted)`` for one raw JSON value."""

    if isinstance(value, bool):
        return None, "TYPE_BOUNDARY", "boolean values are not draw numbers", False

    if isinstance(value, int):
        normalized = value
        converted = False
    elif isinstance(value, float):
        if not math.isfinite(value):
            return None, "PARSE_ERROR", "non-finite float cannot be normalized", False
        if not value.is_integer():
            return (
                None,
                "TYPE_BOUNDARY",
                "non-integral float cannot be normalized safely",
                False,
            )
        normalized = int(value)
        converted = True
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None, "PARSE_ERROR", "empty string cannot be normalized", False
        try:
            normalized = int(stripped)
        except (TypeError, ValueError):
            return None, "PARSE_ERROR", "string is not an integer", False
        converted = True
    else:
        try:
            normalized = int(value)
        except (TypeError, ValueError, OverflowError):
            return None, "TYPE_BOUNDARY", "value is not integer-like", False
        converted = True

    if not 0 <= normalized <= 99:
        return (
            None,
            "OUT_OF_RANGE",
            "normalized number is outside the inclusive range 0..99",
            converted,
        )
    return normalized, None, None, converted


def normalize_values(
    values: Iterable[Any], warning_limit: int = 50
) -> NormalizationResult:
    """Normalize values with ``int``, retain valid order, and report bad records.

    Invalid values are excluded from the model input but are represented by
    aggregate counts and bounded warning samples.  Repeated valid values are
    intentionally retained: a repeated number is a draw observation, not a
    duplicate record.
    """

    if warning_limit < 0:
        raise ValueError("warning_limit must be non-negative")

    numbers: list[int] = []
    warnings: list[QualityWarning] = []
    total = valid = invalid = converted = type_boundary = out_of_range = parse = 0

    for index, raw_value in enumerate(values):
        total += 1
        normalized, code, message, was_converted = _normalize_one(raw_value)
        if normalized is not None:
            numbers.append(normalized)
            valid += 1
            converted += int(was_converted)
            continue

        invalid += 1
        if was_converted:
            converted += 1
        if code == "TYPE_BOUNDARY":
            type_boundary += 1
        elif code == "OUT_OF_RANGE":
            out_of_range += 1
        else:
            parse += 1
        if len(warnings) < warning_limit:
            warnings.append(
                QualityWarning(
                    index=index,
                    code=code or "UNKNOWN",
                    message=message or "value was rejected",
                    raw_type=type(raw_value).__name__,
                    raw_preview=_preview(raw_value),
                )
            )

    summary = DataQualitySummary(
        total_records=total,
        valid_records=valid,
        invalid_records=invalid,
        converted_records=converted,
        type_boundary_warnings=type_boundary,
        out_of_range_warnings=out_of_range,
        parse_warnings=parse,
        warning_count=type_boundary + out_of_range + parse,
    )
    return NormalizationResult(
        numbers=numbers, warnings=tuple(warnings), summary=summary
    )


def load_flat_json(path: str | Path, warning_limit: int = 50) -> NormalizationResult:
    """Load the existing flat JSON list and normalize it deterministically."""

    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise DataLoadError(f"could not read data file {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DataLoadError(f"invalid JSON in {source}: {exc}") from exc

    if not isinstance(payload, list):
        raise DataLoadError(
            f"expected a flat JSON list, received {type(payload).__name__}"
        )
    return normalize_values(payload, warning_limit=warning_limit)


def format_quality_warnings(result: NormalizationResult) -> str:
    """Render a compact quality warning block for console reports."""

    summary = result.summary
    lines = [
        f"records: total={summary.total_records} valid={summary.valid_records} invalid={summary.invalid_records}",
        f"normalization: converted={summary.converted_records} warnings={summary.warning_count}",
        f"temporal assumption: {summary.order_semantics}",
    ]
    for warning in result.warnings:
        lines.append(
            f"warning[{warning.index}] {warning.code}: {warning.message} "
            f"({warning.raw_type} {warning.raw_preview})"
        )
    if summary.warning_count > len(result.warnings):
        lines.append(
            f"... {summary.warning_count - len(result.warnings)} additional warnings omitted"
        )
    return "\n".join(lines)
