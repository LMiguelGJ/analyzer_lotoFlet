"""Parser for the canonical metadata/sorteos_por_fecha history archive."""

import hashlib
import json
from datetime import date

from laboratorio.domain.contracts import GameProfile
from laboratorio.importing.records import (
    _DATE,
    _TIME,
    ClockDeclaration,
    ColumnMapping,
    ImportPreview,
    SourceMetadata,
    _Issues,
    _metadata_valid,
    _number_value,
    _preview,
    _profile_text_valid,
    _valid_unicode,
    canonical_bytes,
)

MAX_HISTORY_BYTES = 32 * 1024 * 1024
MAX_HISTORY_ROWS = 200_000


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"non-standard JSON constant: {value}")


def history_options(document, profile):
    metadata = document["metadata"]
    source = SourceMetadata(
        metadata["origen"], "historical", str(metadata["schema_version"]), metadata["endpoint"]
    )
    clock = ClockDeclaration("iana", metadata["zona_horaria"])
    mapping = ColumnMapping(
        "fecha", "hora", tuple(f"numero_{n}" for n in range(1, profile.positions + 1))
    )
    return {
        "format": "history_json",
        "mapping": mapping,
        "clock": clock,
        "source": source,
        "profile": profile,
    }


def parse_history(data: bytes, profile: GameProfile) -> ImportPreview:
    if not isinstance(data, bytes) or not isinstance(profile, GameProfile):
        raise TypeError("history data and a validated game profile are required")
    source_hash = hashlib.sha256(data).hexdigest()
    issues = _Issues()
    if len(data) > MAX_HISTORY_BYTES:
        issues.add(None, "input_limit", "history exceeds 32 MiB")
        return _preview((), source_hash, None, 0, 0, issues)
    try:
        document = json.loads(
            data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
        if not isinstance(document, dict) or set(document) != {"metadata", "sorteos_por_fecha"}:
            raise ValueError("expected metadata and sorteos_por_fecha")
        metadata, days = document["metadata"], document["sorteos_por_fecha"]
        if not isinstance(metadata, dict) or not isinstance(days, dict):
            raise ValueError("metadata and dated draws must be objects")
        options = history_options(document, profile)
    except (ValueError, UnicodeError, RecursionError, KeyError, TypeError) as exc:
        issues.add(None, "json", f"invalid history JSON: {exc}")
        return _preview((), source_hash, None, 0, 0, issues)

    for key in (
        "schema_version",
        "juego",
        "origen",
        "endpoint",
        "zona_horaria",
        "cantidad_sorteos",
    ):
        if key not in metadata:
            issues.add(None, "metadata", f"metadata is missing {key}")
    if type(metadata.get("schema_version")) is not int or metadata.get("schema_version") != 1:
        issues.add(None, "metadata", "unsupported history metadata schema")
    game_name = metadata.get("juego")
    if (
        not isinstance(game_name, str)
        or not 0 < len(game_name) <= 256
        or game_name.strip() != game_name
        or not _valid_unicode(game_name)
    ):
        issues.add(None, "metadata", "game name must be a bounded nonempty string")
    if not isinstance(metadata.get("origen"), str) or not isinstance(metadata.get("endpoint"), str):
        issues.add(None, "metadata", "source origin and endpoint are required")
    if not isinstance(metadata.get("zona_horaria"), str):
        issues.add(None, "metadata", "IANA timezone is required")
    declared_count = metadata.get("cantidad_sorteos")
    if type(declared_count) is not int or declared_count < 0:
        issues.add(None, "metadata", "declared draw count must be a nonnegative integer")
    try:
        start = metadata["rango_seleccionado"]["desde"]
        end = metadata["rango_seleccionado"]["hasta"]
        if (
            not isinstance(start, str)
            or not isinstance(end, str)
            or not _DATE.fullmatch(start)
            or not _DATE.fullmatch(end)
            or date.fromisoformat(start) > date.fromisoformat(end)
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        start = end = None
        issues.add(None, "metadata_range", "selected date range is invalid")
    if issues.count:
        return _preview((), source_hash, None, 0, 0, issues)

    _metadata_valid(options["source"], options["clock"], issues)
    _profile_text_valid(profile, issues)
    if profile.positions > 30:
        issues.add(None, "positions", "profile positions exceed history import limit")
    if len(days) > 3660:
        issues.add(None, "date_limit", "history contains too many date keys")
    if issues.count:
        return _preview((), source_hash, None, 0, 0, issues)

    unique = {}
    seen = merged = 0
    for day, entries in days.items():
        try:
            if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
                raise ValueError
        except (ValueError, TypeError):
            issues.add(None, "date", "date key must be a real YYYY-MM-DD calendar date")
            continue
        if start is not None and end is not None and not start <= day <= end:
            issues.add(None, "metadata_range", "draw date is outside the selected metadata range")
            continue
        if not isinstance(entries, list):
            issues.add(None, "shape", "each date must map to a draw list")
            continue
        for entry in entries:
            seen += 1
            if seen > MAX_HISTORY_ROWS:
                issues.add(None, "row_limit", "history exceeds 200000 draws")
                break
            allowed = {"hora", "numeros", "source_url"}
            if (
                not isinstance(entry, dict)
                or set(entry) - allowed
                or not {"hora", "numeros"} <= set(entry)
            ):
                issues.add(
                    seen, "shape", "draw must contain only hora, numeros and optional source_url"
                )
                continue
            hour, raw_numbers = entry["hora"], entry["numeros"]
            if not isinstance(hour, str) or not _TIME.fullmatch(hour):
                issues.add(seen, "time", "time must be HH:MM")
                continue
            if not isinstance(raw_numbers, list) or len(raw_numbers) != profile.positions:
                issues.add(seen, "positions", "draw must contain one number per profile position")
                continue
            numbers = tuple(
                _number_value(value, "json", profile.universe_size) for value in raw_numbers
            )
            if any(number is None for number in numbers):
                issues.add(seen, "number", "position is outside the profile number range")
                continue
            values = tuple(number for number in numbers if number is not None)
            if not profile.allows_repeats and len(set(values)) != len(values):
                issues.add(seen, "repeats", "profile forbids repeated numbers in a draw")
                continue
            record = (day, hour, values)
            key = (day, hour)
            if key in unique:
                if unique[key] == record:
                    merged += 1
                else:
                    issues.add(seen, "conflict", "same date/time has conflicting results")
            else:
                unique[key] = record
        if seen > MAX_HISTORY_ROWS:
            break
    if seen != metadata["cantidad_sorteos"]:
        issues.add(None, "declared_count", "declared draw count differs from rows actually read")
    if not seen:
        issues.add(None, "empty", "history must contain at least one draw")
    if issues.count:
        return _preview((), source_hash, None, seen, merged, issues)

    from laboratorio.importing.records import ImportedRecord

    records = tuple(ImportedRecord(*unique[key]) for key in sorted(unique))
    canonical = canonical_bytes(records, **options)
    return _preview(
        records, source_hash, hashlib.sha256(canonical).hexdigest(), seen, merged, issues
    )
