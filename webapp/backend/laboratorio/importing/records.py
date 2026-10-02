"""Deterministic, in-memory CSV/JSON draw import validation (no promotion).

No application path, network or persistence I/O; ZoneInfo may read the trusted
local timezone database while validating an explicitly declared IANA zone.
The limits are admission limits, not a promise to accept every valid GameProfile:
profiles with more than 30 positions cannot fit date, time and positions in the
32-column import envelope. Callers must explicitly disclose this rejection.
"""

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from laboratorio.domain.contracts import GameProfile

MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10_000
MAX_COLUMNS = 32
MAX_ERRORS = 100
DATASET_SCHEMA_VERSION = 1
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_TIME = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]\Z")
_NUMBER = re.compile(r"[0-9]+\Z")


@dataclass(frozen=True)
class ColumnMapping:
    date: str
    time: str
    positions: tuple[str, ...]  # ordered, one named field per result position


@dataclass(frozen=True)
class ClockDeclaration:
    mode: Literal["naive_legacy", "iana"]
    zone: str | None = None


@dataclass(frozen=True)
class SourceMetadata:
    source_id: str
    kind: Literal["historical", "artificial"]
    revision: str
    provenance: str


@dataclass(frozen=True)
class ImportedRecord:
    date: str
    time: str
    numbers: tuple[int, ...]


@dataclass(frozen=True)
class ImportErrorDetail:
    row: int | None  # 1-based data row, not counting a CSV header
    code: str
    message: str


@dataclass(frozen=True)
class ImportPreview:
    records: tuple[ImportedRecord, ...]
    source_sha256: str
    dataset_sha256: str | None
    rows_seen: int
    duplicates_merged: int
    errors: tuple[ImportErrorDetail, ...]
    error_count: int
    errors_truncated: bool
    promotable: bool


class _Issues:
    def __init__(self) -> None:
        self.items: list[ImportErrorDetail] = []
        self.count = 0

    def add(self, row: int | None, code: str, message: str) -> None:
        self.count += 1
        if len(self.items) < MAX_ERRORS:
            self.items.append(ImportErrorDetail(row, code, message))


def _valid_unicode(value: str) -> bool:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return False
    return True


def _metadata_valid(source: SourceMetadata, clock: ClockDeclaration, issues: _Issues) -> bool:
    if (
        not isinstance(source, SourceMetadata)
        or not all(
            isinstance(value, str)
            and 0 < len(value) <= 256
            and value.strip() == value
            and _valid_unicode(value)
            for value in (
                source.source_id,
                source.revision,
                source.provenance,
            )
        )
        or source.kind not in ("historical", "artificial")
    ):
        issues.add(None, "source", "source_id, kind, revision and provenance are required")
        return False
    if not isinstance(clock, ClockDeclaration):
        issues.add(None, "clock", "an explicit clock declaration is required")
        return False
    if clock.mode == "naive_legacy" and clock.zone is None:
        return True
    if (
        clock.mode == "iana"
        and isinstance(clock.zone, str)
        and clock.zone
        and _valid_unicode(clock.zone)
    ):
        try:
            ZoneInfo(clock.zone)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            issues.add(None, "clock_zone", "IANA zone invalid or zoneinfo data unavailable")
            return False
        return True
    if clock.mode == "iana":
        issues.add(None, "clock_zone", "IANA zone invalid or zoneinfo data unavailable")
    else:
        issues.add(None, "clock", "declare naive_legacy without a zone or iana with a valid zone")
    return False


def _profile_text_valid(profile: GameProfile, issues: _Issues) -> None:
    # Normal Pydantic validation constrains these to ASCII regexes/literals. Check
    # again at this boundary so even a model_construct bypass cannot poison the hash.
    if any(
        not isinstance(value, str) or not _valid_unicode(value)
        for value in (profile.profile_id, profile.currency, profile.best_rule)
    ):
        issues.add(None, "profile", "profile text must be valid Unicode")


def _mapped_fields(
    mapping: ColumnMapping, profile: GameProfile, issues: _Issues
) -> tuple[str, ...]:
    if not isinstance(mapping, ColumnMapping) or not isinstance(mapping.positions, tuple):
        issues.add(None, "mapping", "date, time and ordered position fields are required")
        return ()
    fields = (mapping.date, mapping.time, *mapping.positions)
    if len(mapping.positions) != profile.positions:
        issues.add(None, "positions", "mapping must cover every profile position")
    if len(fields) > MAX_COLUMNS:
        issues.add(None, "column_limit", "profile and mapped fields exceed 32 columns")
    valid_names = all(
        isinstance(field, str) and bool(field) and field.strip() == field and _valid_unicode(field)
        for field in fields
    )
    if not valid_names:
        issues.add(None, "mapping", "mapped field names must be nonempty exact strings")
    elif len(set(fields)) != len(fields):
        issues.add(None, "mapping_duplicate", "mapped field names must be distinct")
    return fields


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _read_rows(text: str, format: str, fields: tuple[str, ...], issues: _Issues):
    if format == "json":
        try:
            parsed = json.loads(
                text,
                object_pairs_hook=_json_object,
                parse_constant=_reject_constant,
            )
        except (ValueError, RecursionError) as exc:
            issues.add(None, "json", f"invalid JSON: {exc}")
            return None
        if not isinstance(parsed, list):
            issues.add(None, "shape", "JSON must be a flat array of objects")
            return None
        if len(parsed) > MAX_ROWS:
            issues.add(None, "row_limit", "JSON exceeds 10000 rows")
            return None
        return parsed
    if format == "csv":
        try:
            reader = csv.reader(io.StringIO(text, newline=""), strict=True)
            header = next(reader)
        except (StopIteration, csv.Error) as exc:
            issues.add(None, "csv", f"invalid CSV header: {exc}")
            return None
        if len(header) > MAX_COLUMNS:
            issues.add(None, "column_limit", "CSV exceeds 32 columns")
            return None
        if any(header.count(field) != 1 for field in fields) or len(set(header)) != len(header):
            issues.add(None, "header", "CSV header needs unique mapped columns exactly once")
            return None

        def rows():
            for values in reader:
                if len(values) != len(header):
                    yield None
                else:
                    yield dict(zip(header, values, strict=True))

        return rows()
    issues.add(None, "format", "format must be csv or json")
    return None


def _number_value(value: object, format: str, universe: int) -> int | None:
    if format == "json" and type(value) is int:
        number = value
    elif isinstance(value, str) and _NUMBER.fullmatch(value):
        digits = value.lstrip("0") or "0"
        # Also avoids Python's integer-string conversion limit on huge CSV cells.
        if len(digits) > len(str(universe)):
            return None
        number = int(digits)
    else:
        return None
    return number if 0 <= number < universe else None


def canonical_bytes(
    records: tuple[ImportedRecord, ...],
    format: str,
    mapping: ColumnMapping,
    clock: ClockDeclaration,
    source: SourceMetadata,
    profile: GameProfile,
) -> bytes:
    """Canonical UTF-8 artifact; context is intentionally part of identity."""
    envelope = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "format": format,
        "mapping": {"date": mapping.date, "time": mapping.time, "positions": mapping.positions},
        "clock": {"mode": clock.mode, "zone": clock.zone},
        "source": {
            "source_id": source.source_id,
            "kind": source.kind,
            "revision": source.revision,
            "provenance": source.provenance,
        },
        "profile": profile.model_dump(mode="json"),
        "records": [(record.date, record.time, record.numbers) for record in records],
    }
    encoded = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return encoded.encode("utf-8")


def parse_records(
    data: bytes,
    *,
    format: Literal["csv", "json"],
    mapping: ColumnMapping,
    source: SourceMetadata,
    clock: ClockDeclaration,
    profile: GameProfile,
) -> ImportPreview:
    """Preview one source only. Any error empties records and forbids promotion.

    No timezone conversion is performed: date/time remain wall-clock labels in the
    declared zone. `source_sha256` hashes original bytes, including formatting;
    `dataset_sha256` hashes sorted deduplicated values plus versioned context.
    """
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if not isinstance(profile, GameProfile):
        raise TypeError("profile must be a validated GameProfile")
    source_sha256 = hashlib.sha256(data).hexdigest()
    issues = _Issues()
    fields = _mapped_fields(mapping, profile, issues)
    _metadata_valid(source, clock, issues)
    _profile_text_valid(profile, issues)
    if format not in ("csv", "json"):
        issues.add(None, "format", "format must be csv or json")
    if len(data) > MAX_INPUT_BYTES:
        issues.add(None, "input_limit", "input exceeds 2 MiB before decoding")
    if issues.count:
        return _preview((), source_sha256, None, 0, 0, issues)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        issues.add(None, "encoding", "input must be UTF-8")
        return _preview((), source_sha256, None, 0, 0, issues)
    rows = _read_rows(text, format, fields, issues)
    if rows is None:
        return _preview((), source_sha256, None, 0, 0, issues)
    unique: dict[tuple[str, str], ImportedRecord] = {}
    merged = 0
    seen = 0
    try:
        for seen, row in enumerate(rows, 1):
            if seen > MAX_ROWS:
                issues.add(None, "row_limit", "input exceeds 10000 rows")
                break
            if not isinstance(row, dict):
                issues.add(seen, "shape", "row must be an object with the mapped fields")
                continue
            if len(row) > MAX_COLUMNS:
                issues.add(seen, "column_limit", "row exceeds 32 columns")
                continue
            if format == "json" and any(isinstance(value, (dict, list)) for value in row.values()):
                issues.add(seen, "shape", "JSON rows must be flat objects")
                continue
            if any(field not in row for field in fields):
                issues.add(seen, "missing_field", "row is missing a mapped field")
                continue
            day, hour = row[fields[0]], row[fields[1]]
            if not isinstance(day, str) or not _DATE.fullmatch(day):
                issues.add(seen, "date", "date must be YYYY-MM-DD")
                continue
            try:
                date.fromisoformat(day)
            except ValueError:
                issues.add(seen, "date", "date is not a real calendar date")
                continue
            if not isinstance(hour, str) or not _TIME.fullmatch(hour):
                issues.add(seen, "time", "time must be HH:MM (00:00-23:59)")
                continue
            values = tuple(
                _number_value(row[field], format, profile.universe_size) for field in fields[2:]
            )
            if any(number is None for number in values):
                issues.add(seen, "number", "position must be an integer within profile range")
                continue
            numbers = tuple(number for number in values if number is not None)
            if not profile.allows_repeats and len(set(numbers)) != len(numbers):
                issues.add(seen, "repeats", "profile forbids repeated numbers in a draw")
                continue
            record = ImportedRecord(day, hour, numbers)
            key = (day, hour)
            previous = unique.get(key)
            if previous is None:
                unique[key] = record
            elif previous == record:
                merged += 1
            else:
                issues.add(seen, "conflict", "same date/time has conflicting results")
    except csv.Error as exc:
        issues.add(seen + 1, "csv", f"invalid CSV row: {exc}")
    if not seen and not issues.count:
        issues.add(None, "empty", "dataset must contain at least one draw")
    if issues.count:
        return _preview((), source_sha256, None, seen, merged, issues)
    records = tuple(unique[key] for key in sorted(unique))
    return _preview(
        records,
        source_sha256,
        hashlib.sha256(
            canonical_bytes(records, format, mapping, clock, source, profile)
        ).hexdigest(),
        seen,
        merged,
        issues,
    )


def _preview(
    records: tuple[ImportedRecord, ...],
    source_hash: str,
    dataset_hash: str | None,
    rows_seen: int,
    merged: int,
    issues: _Issues,
) -> ImportPreview:
    return ImportPreview(
        records,
        source_hash,
        dataset_hash,
        rows_seen,
        merged,
        tuple(issues.items),
        issues.count,
        issues.count > MAX_ERRORS,
        not issues.count,
    )
