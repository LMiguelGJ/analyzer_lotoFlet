"""Pure, bounded parser for compatible immutable quiniela history sources."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from laboratorio.domain.configurable_laboratories import SourceReference
from laboratorio.domain.configurable_runs import QuinielaDraw
from laboratorio.domain.quiniela_profiles import QuinielaProfile

MAX_RAW_BYTES = 64 * 1024 * 1024
MAX_INPUT_ROWS = 400_000
_ISO_OFFSET = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d)$")
_ISO_NAIVE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")
_TOP_KEYS = {"schema_version", "timezone", "draws"}
_DRAW_KEYS = {"schema_version", "draw_id", "timestamp", "results"}


class HistoryImportError(ValueError):
    """An uploaded or configured history is invalid or incompatible."""


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise HistoryImportError("duplicate JSON object key")
        result[key] = value
    return result


def _constant(_value):
    raise HistoryImportError("nonfinite JSON values are forbidden")


def _loads(raw: bytes):
    try:
        text = raw.decode("utf-8", errors="strict")
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise HistoryImportError("history JSON is invalid UTF-8 or malformed") from error


def _canonical(value) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _zone(value):
    if type(value) is not str or not value or value != value.strip():
        raise HistoryImportError("timezone must be a trimmed IANA zone name")
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise HistoryImportError("timezone is not a valid IANA zone") from error


def _utc_timestamp(value, zone, confirmed):
    if type(value) is not str:
        raise HistoryImportError("timestamp must be a string")
    if _ISO_OFFSET.fullmatch(value):
        try:
            parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        except ValueError as error:
            raise HistoryImportError("timestamp is invalid") from error
        return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not _ISO_NAIVE.fullmatch(value):
        raise HistoryImportError(
            "timestamp must use ISO seconds with Z/offset or explicit local time"
        )
    if not confirmed:
        raise HistoryImportError("naive local timestamps require explicit timezone confirmation")
    try:
        naive = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError as error:
        raise HistoryImportError("timestamp is invalid") from error
    candidates = []
    for fold in (0, 1):
        local = naive.replace(tzinfo=zone, fold=fold)
        utc = local.astimezone(UTC)
        if utc.astimezone(zone).replace(tzinfo=None) == naive and utc not in candidates:
            candidates.append(utc)
    if len(candidates) != 1:
        reason = "nonexistent" if not candidates else "ambiguous"
        raise HistoryImportError(f"{reason} local timestamp; supply an explicit offset")
    return candidates[0].strftime("%Y-%m-%dT%H:%M:%SZ")


def _profile_draw(draw, profile, zone, confirmed):
    if not isinstance(draw, dict) or set(draw) != _DRAW_KEYS:
        raise HistoryImportError("draw must contain exactly the supported v2 fields")
    if type(draw["schema_version"]) is not int or draw["schema_version"] != 2:
        raise HistoryImportError("draw schema_version must be integer 2")
    try:
        parsed = QuinielaDraw.from_mapping(
            {
                "schema_version": 2,
                "draw_id": draw["draw_id"],
                "timestamp": "2000-01-01T00:00:00Z",
                "results": draw["results"],
            }
        )
    except (TypeError, ValueError) as error:
        raise HistoryImportError(f"draw is invalid: {error}") from error
    rules = profile.rules
    if len(parsed.results) != rules.positions:
        raise HistoryImportError("draw positions do not match the selected profile")
    if any(number not in rules.universe for number in parsed.results):
        raise HistoryImportError("draw result is outside the selected profile universe")
    if not rules.allows_repeats and len(set(parsed.results)) != len(parsed.results):
        raise HistoryImportError("draw repeats are forbidden by the selected profile")
    timestamp = _utc_timestamp(draw["timestamp"], zone, confirmed)
    return QuinielaDraw(2, parsed.draw_id, timestamp, parsed.results)


def _source_profile(profile):
    if not isinstance(profile, QuinielaProfile):
        try:
            profile = QuinielaProfile.from_mapping(profile)
        except (TypeError, ValueError) as error:
            raise HistoryImportError("selected profile is invalid") from error
    return profile


@dataclass(frozen=True, slots=True)
class HistoryPreview:
    name: str
    profile_id: str
    profile_sha256: str
    origin: str
    timezone: str
    timezone_confirmed: bool
    raw_sha256: str
    canonical_sha256: str
    preview_sha256: str
    raw_bytes: bytes
    canonical_json: str
    draws: tuple[QuinielaDraw, ...]
    duplicate_count: int
    input_rows: int

    @property
    def draw_count(self):
        return len(self.draws)

    @property
    def first_timestamp(self):
        return self.draws[0].timestamp if self.draws else None

    @property
    def last_timestamp(self):
        return self.draws[-1].timestamp if self.draws else None

    def to_mapping(self):
        return {
            "name": self.name,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_sha256,
            "origin": self.origin,
            "timezone": self.timezone,
            "timezone_confirmed": self.timezone_confirmed,
            "raw_sha256": self.raw_sha256,
            "canonical_sha256": self.canonical_sha256,
            "preview_sha256": self.preview_sha256,
            "input_rows": self.input_rows,
            "draw_count": self.draw_count,
            "duplicate_count": self.duplicate_count,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "max_raw_bytes": MAX_RAW_BYTES,
            "max_input_rows": MAX_INPUT_ROWS,
            "sample": [draw.to_mapping() for draw in self.draws[:3]],
        }


def _build_preview(raw, rows, row_count, profile, name, origin, zone_name, zone, confirmed):
    if type(name) is not str or not name.strip() or len(name.strip().encode("utf-8")) > 120:
        raise HistoryImportError("source name must be nonempty and at most 120 UTF-8 bytes")
    if type(row_count) is not int or not 1 <= row_count <= MAX_INPUT_ROWS:
        raise HistoryImportError("draws must be a nonempty array of at most 400000 rows")
    seen_id = {}
    seen_instant = {}
    unique = []
    duplicates = 0
    for raw_draw in rows:
        draw = _profile_draw(raw_draw, profile, zone, confirmed)
        identity = (draw.timestamp, draw.results)
        prior_id = seen_id.get(draw.draw_id)
        if prior_id is not None:
            if prior_id != identity:
                raise HistoryImportError(
                    "conflict: a draw identifier has different time or results"
                )
            duplicates += 1
            continue
        prior_instant = seen_instant.get(draw.timestamp)
        if prior_instant is not None and prior_instant[1] != draw.results:
            raise HistoryImportError("conflict: one instant has different ordered results")
        seen_id[draw.draw_id] = identity
        seen_instant[draw.timestamp] = (draw.draw_id, draw.results)
        unique.append(draw)
    unique.sort(key=lambda item: (item.timestamp, item.draw_id))
    canonical_value = {
        "schema_version": 2,
        "timezone": zone_name,
        "draws": [item.to_mapping() for item in unique],
    }
    canonical_json = _canonical(canonical_value)
    raw_sha = hashlib.sha256(raw).hexdigest()
    canonical_sha = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    profile_json = _canonical(profile.to_mapping())
    profile_sha = hashlib.sha256(profile_json.encode("utf-8")).hexdigest()
    normalized_name = name.strip()
    identity = {
        "name": normalized_name,
        "profile_id": profile.id,
        "profile_sha256": profile_sha,
        "origin": origin,
        "timezone": zone_name,
        "timezone_confirmed": confirmed,
        "raw_sha256": raw_sha,
        "canonical_sha256": canonical_sha,
        "duplicate_count": duplicates,
        "input_rows": row_count,
    }
    preview_sha = hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()
    return HistoryPreview(
        normalized_name,
        profile.id,
        profile_sha,
        origin,
        zone_name,
        confirmed,
        raw_sha,
        canonical_sha,
        preview_sha,
        raw,
        canonical_json,
        tuple(unique),
        duplicates,
        row_count,
    )


def preview_history(
    raw: bytes | str,
    profile,
    *,
    name: str,
    origin: str = "imported",
    timezone: str | None = None,
    timezone_confirmed: bool = False,
) -> HistoryPreview:
    """Validate exact source bytes, normalize instants, and return an immutable preview."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8", errors="strict")
    if type(raw) is not bytes or not raw or len(raw) > MAX_RAW_BYTES:
        raise HistoryImportError("raw history must be nonempty and at most 64 MiB")
    if type(name) is not str or not name.strip() or len(name.strip().encode("utf-8")) > 120:
        raise HistoryImportError("source name must be nonempty and at most 120 UTF-8 bytes")
    if origin not in ("imported", "included"):
        raise HistoryImportError("unknown history origin")
    if type(timezone_confirmed) is not bool:
        raise HistoryImportError("timezone_confirmed must be a boolean")
    profile = _source_profile(profile)
    value = _loads(raw)
    if not isinstance(value, dict) or set(value) != _TOP_KEYS:
        raise HistoryImportError("history must contain exactly schema_version, timezone and draws")
    if type(value["schema_version"]) is not int or value["schema_version"] != 2:
        raise HistoryImportError("history schema_version must be integer 2")
    declared_zone = value["timezone"]
    if timezone is not None and timezone != declared_zone:
        raise HistoryImportError("explicit timezone conflicts with the declared source timezone")
    zone_name = declared_zone if timezone is None else timezone
    zone = _zone(zone_name)
    if type(value["draws"]) is not list:
        raise HistoryImportError("draws must be an array")
    return _build_preview(
        raw,
        value["draws"],
        len(value["draws"]),
        profile,
        name,
        origin,
        zone_name,
        zone,
        timezone_confirmed,
    )


def preview_included_history(raw: bytes, profile, *, name="Historial incluido"):
    """Adapt only the frozen legacy JSON shape; no labels or client paths are accepted."""
    if type(raw) is not bytes or len(raw) > MAX_RAW_BYTES:
        raise HistoryImportError("configured included history exceeds the raw-byte budget")
    value = _loads(raw)
    if not isinstance(value, dict) or set(value) != {"sorteos_por_fecha", "metadata"}:
        raise HistoryImportError("included history schema is invalid")
    metadata = value["metadata"]
    if not isinstance(metadata, dict) or metadata.get("zona_horaria") != "America/Santo_Domingo":
        raise HistoryImportError("included history has an unsupported declared timezone")
    dated = value["sorteos_por_fecha"]
    if not isinstance(dated, dict):
        raise HistoryImportError("included history draws must be keyed by date")
    row_count = 0
    for day, entries in dated.items():
        if type(day) is not str or type(entries) is not list:
            raise HistoryImportError("included history date records are invalid")
        row_count += len(entries)
        if row_count > MAX_INPUT_ROWS:
            raise HistoryImportError("included history exceeds 400000 rows")

    def adapted_rows():
        for day, entries in dated.items():
            for entry in entries:
                if not isinstance(entry, dict) or not {"hora", "numeros"} <= set(entry):
                    raise HistoryImportError("included draw schema is invalid")
                if set(entry) - {"hora", "numeros", "source_url"}:
                    raise HistoryImportError("included draw schema is invalid")
                if "source_url" in entry and type(entry["source_url"]) is not str:
                    raise HistoryImportError("included source_url metadata must be a string")
                hour, numbers = entry["hora"], entry["numeros"]
                if type(hour) is not str or type(numbers) is not list:
                    raise HistoryImportError("included draw fields are invalid")
                if any(
                    type(item) is not str or not item.isascii() or not item.isdecimal()
                    for item in numbers
                ):
                    raise HistoryImportError("included numbers must be exact decimal strings")
                yield {
                    "schema_version": 2,
                    "draw_id": f"{day} {hour}",
                    "timestamp": f"{day}T{hour}:00",
                    "results": [int(item) for item in numbers],
                }

    profile = _source_profile(profile)
    if profile.rules.universe != tuple(range(100)) or profile.rules.positions != 5:
        raise HistoryImportError(
            "included history requires the original 100-number, five-position structure"
        )
    zone_name = "America/Santo_Domingo"
    return _build_preview(
        raw,
        adapted_rows(),
        row_count,
        profile,
        name,
        "included",
        zone_name,
        _zone(zone_name),
        True,
    )


def source_reference(preview: HistoryPreview, identifier: str | None = None) -> SourceReference:
    """Return the immutable profile/hash binding used in Q2 storage/API responses."""
    import uuid

    return SourceReference(
        schema_version=2,
        id=identifier or str(uuid.uuid4()),
        sha256=preview.canonical_sha256,
        profile_sha256=preview.profile_sha256,
        origin=preview.origin,
        raw_sha256=preview.raw_sha256,
        rankings_sha256=None,
    )
