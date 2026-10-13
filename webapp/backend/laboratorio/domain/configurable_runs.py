"""Strict immutable values for configurable-run traces.

These values prove structural consistency only. They do not prove profile
compatibility, strategy validity, or replay correctness.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import ClassVar

from laboratorio.domain.contracts import MAX_MONEY

MAX_JS_SAFE_INTEGER = 2**53 - 1
_MAX_DRAW_ID_BYTES = 120
_MAX_ENGINE_VERSION_BYTES = 80
_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _exact_mapping(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    if set(value) != keys:
        missing = keys - set(value)
        extra = set(value) - keys
        raise ValueError(
            f"{label} keys mismatch (missing={sorted(missing)}, extra={sorted(extra)})"
        )
    return value


def _integer(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def _text(value: object, label: str, *, max_bytes: int, trim: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    result = value.strip() if trim else value
    if not result or result != result.strip():
        raise ValueError(f"{label} must be nonempty and trimmed")
    try:
        size = len(result.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise ValueError(f"{label} must be valid UTF-8") from error
    if size > max_bytes:
        raise ValueError(f"{label} exceeds {max_bytes} UTF-8 bytes")
    return result


def _timestamp(value: object, label: str = "timestamp") -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not _TIMESTAMP_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must use canonical UTC YYYY-MM-DDTHH:MM:SSZ")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ValueError(f"{label} is not a valid UTC timestamp") from error
    return value


def _integer_tuple(
    value: object, label: str, *, minimum_length: int, maximum_length: int
) -> tuple[int, ...]:
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{label} must be an array")
    if not minimum_length <= len(value) <= maximum_length:
        raise ValueError(f"{label} length must be between {minimum_length} and {maximum_length}")
    values = tuple(
        _integer(item, f"{label}[{index}]", minimum=0, maximum=MAX_JS_SAFE_INTEGER)
        for index, item in enumerate(value)
    )
    return values


def _version(value: object) -> int:
    return _integer(value, "schema_version", minimum=2, maximum=2)


def _draw_id(value: object) -> str:
    return _text(value, "draw_id", max_bytes=_MAX_DRAW_ID_BYTES, trim=True)


def _rules_used(value: object) -> Mapping[str, str]:
    source = _exact_mapping(
        value,
        {"profile_sha256", "strategy_sha256", "engine_version"},
        "rules_used",
    )
    profile_hash = source["profile_sha256"]
    strategy_hash = source["strategy_sha256"]
    engine_version = source["engine_version"]
    if not isinstance(profile_hash, str) or not _HASH_PATTERN.fullmatch(profile_hash):
        raise ValueError("rules_used.profile_sha256 must be a lowercase SHA-256 hex digest")
    if not isinstance(strategy_hash, str) or not _HASH_PATTERN.fullmatch(strategy_hash):
        raise ValueError("rules_used.strategy_sha256 must be a lowercase SHA-256 hex digest")
    version = _text(
        engine_version,
        "rules_used.engine_version",
        max_bytes=_MAX_ENGINE_VERSION_BYTES,
    )
    if version != engine_version:
        raise ValueError("rules_used.engine_version must be trimmed")
    return MappingProxyType(
        {
            "profile_sha256": profile_hash,
            "strategy_sha256": strategy_hash,
            "engine_version": version,
        }
    )


@dataclass(frozen=True)
class QuinielaDraw:
    """A version-2 draw value; repeated results are structurally permitted."""

    schema_version: int
    draw_id: str
    timestamp: str
    results: tuple[int, ...]

    _MAPPING_KEYS: ClassVar[set[str]] = {"schema_version", "draw_id", "timestamp", "results"}

    def __post_init__(self) -> None:
        _version(self.schema_version)
        object.__setattr__(self, "draw_id", _draw_id(self.draw_id))
        _timestamp(self.timestamp)
        if not isinstance(self.results, tuple):
            raise TypeError("results must be a tuple")
        _integer_tuple(self.results, "results", minimum_length=1, maximum_length=16)

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "draw_id": self.draw_id,
            "timestamp": self.timestamp,
            "results": list(self.results),
        }

    @classmethod
    def from_mapping(cls, value: object) -> "QuinielaDraw":
        source = _exact_mapping(value, cls._MAPPING_KEYS, "draw")
        results = _integer_tuple(source["results"], "results", minimum_length=1, maximum_length=16)
        return cls(
            schema_version=_version(source["schema_version"]),
            draw_id=_draw_id(source["draw_id"]),
            timestamp=_timestamp(source["timestamp"]),
            results=results,
        )


@dataclass(frozen=True)
class RunWindow:
    """An inclusive UTC window for a configurable run."""

    schema_version: int
    start: str
    end: str

    _MAPPING_KEYS: ClassVar[set[str]] = {"schema_version", "start", "end"}

    def __post_init__(self) -> None:
        _version(self.schema_version)
        _timestamp(self.start, "start")
        _timestamp(self.end, "end")
        if self.start > self.end:
            raise ValueError("start must not be after end")

    def to_mapping(self) -> dict[str, object]:
        return {"schema_version": self.schema_version, "start": self.start, "end": self.end}

    @classmethod
    def from_mapping(cls, value: object) -> "RunWindow":
        source = _exact_mapping(value, cls._MAPPING_KEYS, "window")
        return cls(
            schema_version=_version(source["schema_version"]),
            start=_timestamp(source["start"], "start"),
            end=_timestamp(source["end"], "end"),
        )


@dataclass(frozen=True)
class QuinielaBet:
    """A version-2 wager trace row with exact structural money reconciliation."""

    schema_version: int
    ordinal: int
    session_ordinal: int
    draw_ordinal: int
    draw_id: str
    timestamp: str
    numbers: tuple[int, ...]
    per_number: int
    wagered: int
    results: tuple[int, ...]
    paid: int
    balance_before: int
    balance_after: int
    rules_used: Mapping[str, str]

    _MAPPING_KEYS: ClassVar[set[str]] = {
        "schema_version",
        "ordinal",
        "session_ordinal",
        "draw_ordinal",
        "draw_id",
        "timestamp",
        "numbers",
        "per_number",
        "wagered",
        "results",
        "paid",
        "balance_before",
        "balance_after",
        "rules_used",
    }

    def __post_init__(self) -> None:
        _version(self.schema_version)
        for field_name in ("ordinal", "session_ordinal", "draw_ordinal"):
            _integer(
                getattr(self, field_name),
                field_name,
                minimum=0,
                maximum=MAX_JS_SAFE_INTEGER,
            )
        object.__setattr__(self, "draw_id", _draw_id(self.draw_id))
        _timestamp(self.timestamp)
        if not isinstance(self.numbers, tuple):
            raise TypeError("numbers must be a tuple")
        numbers = _integer_tuple(self.numbers, "numbers", minimum_length=1, maximum_length=1_000)
        if len(set(numbers)) != len(numbers):
            raise ValueError("numbers must be distinct")
        if not isinstance(self.results, tuple):
            raise TypeError("results must be a tuple")
        _integer_tuple(self.results, "results", minimum_length=1, maximum_length=16)

        per_number = _integer(self.per_number, "per_number", minimum=1, maximum=MAX_MONEY)
        wagered = _integer(self.wagered, "wagered", minimum=1, maximum=MAX_MONEY)
        paid = _integer(self.paid, "paid", minimum=0, maximum=MAX_MONEY)
        balance_before = _integer(
            self.balance_before, "balance_before", minimum=0, maximum=MAX_MONEY
        )
        balance_after = _integer(self.balance_after, "balance_after", minimum=0, maximum=MAX_MONEY)
        if len(numbers) * per_number > MAX_MONEY:
            raise ValueError("aggregate wager exceeds MAX_MONEY")
        if wagered != len(numbers) * per_number:
            raise ValueError("wagered must equal len(numbers) * per_number")
        if balance_before < wagered:
            raise ValueError("balance_before must fund wagered")
        if balance_after != balance_before - wagered + paid:
            raise ValueError("balance_after does not reconcile with wagered and paid")
        object.__setattr__(self, "rules_used", _rules_used(self.rules_used))

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "ordinal": self.ordinal,
            "session_ordinal": self.session_ordinal,
            "draw_ordinal": self.draw_ordinal,
            "draw_id": self.draw_id,
            "timestamp": self.timestamp,
            "numbers": list(self.numbers),
            "per_number": self.per_number,
            "wagered": self.wagered,
            "results": list(self.results),
            "paid": self.paid,
            "balance_before": self.balance_before,
            "balance_after": self.balance_after,
            "rules_used": dict(self.rules_used),
        }

    @classmethod
    def from_mapping(cls, value: object) -> "QuinielaBet":
        source = _exact_mapping(value, cls._MAPPING_KEYS, "bet")
        numbers = _integer_tuple(
            source["numbers"], "numbers", minimum_length=1, maximum_length=1_000
        )
        results = _integer_tuple(source["results"], "results", minimum_length=1, maximum_length=16)
        if len(set(numbers)) != len(numbers):
            raise ValueError("numbers must be distinct")
        return cls(
            schema_version=_version(source["schema_version"]),
            ordinal=_integer(source["ordinal"], "ordinal", minimum=0, maximum=MAX_JS_SAFE_INTEGER),
            session_ordinal=_integer(
                source["session_ordinal"],
                "session_ordinal",
                minimum=0,
                maximum=MAX_JS_SAFE_INTEGER,
            ),
            draw_ordinal=_integer(
                source["draw_ordinal"],
                "draw_ordinal",
                minimum=0,
                maximum=MAX_JS_SAFE_INTEGER,
            ),
            draw_id=_draw_id(source["draw_id"]),
            timestamp=_timestamp(source["timestamp"]),
            numbers=numbers,
            per_number=_integer(source["per_number"], "per_number", minimum=1, maximum=MAX_MONEY),
            wagered=_integer(source["wagered"], "wagered", minimum=1, maximum=MAX_MONEY),
            results=results,
            paid=_integer(source["paid"], "paid", minimum=0, maximum=MAX_MONEY),
            balance_before=_integer(
                source["balance_before"], "balance_before", minimum=0, maximum=MAX_MONEY
            ),
            balance_after=_integer(
                source["balance_after"], "balance_after", minimum=0, maximum=MAX_MONEY
            ),
            rules_used=_rules_used(source["rules_used"]),
        )
