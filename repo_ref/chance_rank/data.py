"""Validated loading and canonical chronology of Chance Express draws.

A row is eligible when its immediate predecessor is in the same observed day
and exactly ``STEP_MINUTES`` earlier; a segment is a maximal chain of rows
linked by exact 5-minute steps within a day, starting at a non-eligible head
row (decisions D1/D2). Duplicate timestamps with identical numbers are merged
into one row and every source_url is kept in ``provenance``; a duplicate
timestamp with different numbers is a conflict and stops the load.
"""

import hashlib
import json
import re
from bisect import bisect_left
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

from chance_rank.protocol import EXPECTED_SHA256, STEP_MINUTES

_HORA_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
_NUM_RE = re.compile(r"[0-9]{2}")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class DataError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class History:
    """Canonical chronology; ``day`` and ``source`` index into ``dates``/``sources``."""

    nums: np.ndarray       # (N, 5) int64, values 0-99
    day: np.ndarray        # (N,) int64, index into `dates`
    dates: tuple           # ISO dates that have at least one row, ascending
    slot: np.ndarray       # (N,) int64, minutes since midnight
    hour: np.ndarray       # (N,) int64
    weekday: np.ndarray    # (N,) int64, 0 = Monday
    day_pos: np.ndarray    # (N,) int64, 0-based order within its day
    source: np.ndarray     # (N,) int64, index into `sources`
    sources: tuple         # host names, ordered by first appearance
    eligible: np.ndarray   # (N,) bool
    segment: np.ndarray    # (N,) int64
    sha256: str
    empty_dates: tuple     # ISO dates present with an empty draw list
    provenance: dict       # row_index -> list[source_url], merged duplicates only

    @property
    def n(self):
        return self.nums.shape[0]

    def label(self, i):
        return f"{self.dates[self.day[i]]} {self.hour[i]:02d}:{self.slot[i] % 60:02d}"

    def with_nums(self, new_nums):
        """Copy with different numbers but the same calendar/eligibility/sources."""
        new_nums = np.asarray(new_nums)
        if new_nums.shape != self.nums.shape:
            raise DataError(f"with_nums shape {new_nums.shape} != {self.nums.shape}")
        if new_nums.min(initial=0) < 0 or new_nums.max(initial=0) > 99:
            raise DataError("with_nums values must be within 0..99")
        return replace(self, nums=new_nums.astype(np.int64))


def fmt(v):
    return f"{v:02d}"


def _host_of(url):
    if not url:
        return "unknown"
    netloc = urlparse(url).netloc.removeprefix("www.")
    return netloc or "unknown"


def _validated_records(date_key, records):
    normalized = []
    for rec in records:
        if not isinstance(rec, dict):
            raise DataError(f"Draw record at {date_key} must be a dict: {rec!r}")
        hora = rec.get("hora")
        if not isinstance(hora, str) or not _HORA_RE.fullmatch(hora):
            raise DataError(f"Invalid hora at {date_key}: {hora!r}")
        numeros = rec.get("numeros")
        if not isinstance(numeros, list) or len(numeros) != 5:
            raise DataError(f"Invalid numeros count at {date_key} {hora}: {numeros!r}")
        for x in numeros:
            if not isinstance(x, str) or not _NUM_RE.fullmatch(x):
                raise DataError(f"Invalid number at {date_key} {hora}: {x!r}")
        source_url = rec.get("source_url")
        if source_url is not None and not isinstance(source_url, str):
            raise DataError(f"Invalid source_url at {date_key} {hora}: {source_url!r}")
        normalized.append({"hora": hora, "numeros": numeros, "source_url": source_url})
    normalized.sort(key=lambda r: r["hora"])
    return normalized


def _merge_duplicates(date_key, normalized):
    """Group consecutive same-``hora`` records; identical numbers merge, else conflict."""
    merged = []
    i = 0
    while i < len(normalized):
        j = i
        while j + 1 < len(normalized) and normalized[j + 1]["hora"] == normalized[i]["hora"]:
            j += 1
        group = normalized[i:j + 1]
        if len(group) > 1:
            base_numeros = group[0]["numeros"]
            for other in group[1:]:
                if other["numeros"] != base_numeros:
                    raise DataError(f"Conflicting duplicate at {date_key} {group[0]['hora']}: "
                                     f"{base_numeros} vs {other['numeros']}")
            urls = [g["source_url"] for g in group if g.get("source_url")]
            merged.append((group[0], urls))
        else:
            merged.append((group[0], None))
        i = j + 1
    return merged


def _build_history(sorteos_por_fecha, sha, sources_override=None):
    if not isinstance(sorteos_por_fecha, dict):
        raise DataError("sorteos_por_fecha must be a dict")
    dates, empty_dates, rows, provenance = [], [], [], {}
    for date_key in sorted(sorteos_por_fecha):
        if not isinstance(date_key, str) or not _DATE_RE.fullmatch(date_key):
            raise DataError(f"Invalid date key: {date_key!r}")
        try:
            weekday = date.fromisoformat(date_key).weekday()
        except ValueError as exc:
            raise DataError(f"Invalid date key: {date_key}") from exc
        records = sorteos_por_fecha[date_key]
        if not isinstance(records, list):
            raise DataError(f"Draw list for {date_key} must be a list")
        if not records:
            empty_dates.append(date_key)
            continue
        day_idx = len(dates)
        dates.append(date_key)
        normalized = _validated_records(date_key, records)
        for day_pos, (rec, urls) in enumerate(_merge_duplicates(date_key, normalized)):
            hour, minute = map(int, rec["hora"].split(":"))
            nums5 = [int(x) for x in rec["numeros"]]
            host = _host_of(rec.get("source_url"))
            row_index = len(rows)
            if urls is not None:
                provenance[row_index] = urls
            rows.append((nums5, day_idx, hour * 60 + minute, hour, weekday, day_pos, host))

    if sources_override is not None:
        sources = tuple(sources_override)
    else:
        sources = tuple(dict.fromkeys(r[6] for r in rows))
    source_index = {name: i for i, name in enumerate(sources)}

    nums = np.array([r[0] for r in rows], dtype=np.int64).reshape(-1, 5)
    day = np.array([r[1] for r in rows], dtype=np.int64)
    slot = np.array([r[2] for r in rows], dtype=np.int64)
    hour = np.array([r[3] for r in rows], dtype=np.int64)
    weekday_arr = np.array([r[4] for r in rows], dtype=np.int64)
    day_pos = np.array([r[5] for r in rows], dtype=np.int64)
    source = np.array([source_index[r[6]] for r in rows], dtype=np.int64)

    eligible = np.zeros(len(rows), dtype=bool)
    if len(rows) > 1:
        eligible[1:] = (day[1:] == day[:-1]) & (slot[1:] - slot[:-1] == STEP_MINUTES)
    segment = np.cumsum(~eligible).astype(np.int64) - 1

    return History(nums=nums, day=day, dates=tuple(dates), slot=slot, hour=hour,
                   weekday=weekday_arr, day_pos=day_pos, source=source, sources=sources,
                   eligible=eligible, segment=segment, sha256=sha,
                   empty_dates=tuple(empty_dates), provenance=provenance)


def load_history(path, expected_sha: str | None = EXPECTED_SHA256):
    """``expected_sha=None`` is an explicit opt-out of the protocol SHA check."""
    raw = Path(path).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if expected_sha is not None and sha != expected_sha:
        raise DataError(f"SHA-256 mismatch: expected {expected_sha}, got {sha}")
    try:
        data = json.loads(raw.decode("utf-8"))
        sorteos_por_fecha = data["sorteos_por_fecha"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DataError(f"Cannot read draw history from {path}: {exc}") from exc
    return _build_history(sorteos_por_fecha, sha)


def make_history(dates_slots_nums, sources=None):
    """Test/synthetic constructor sharing ``_build_history`` with ``load_history``.

    ``dates_slots_nums``: list of (iso_date, "HH:MM", [5 ints], host).
    ``sources``: optional fixed host order, overriding first-appearance discovery.
    """
    sorteos_por_fecha = {}
    for iso_date, hora, nums, host in dates_slots_nums:
        record = {"hora": hora, "numeros": [fmt(n) for n in nums],
                  "source_url": f"https://{host}/synthetic"}
        sorteos_por_fecha.setdefault(iso_date, []).append(record)
    return _build_history(sorteos_por_fecha, "synthetic", sources_override=sources)


def validation_report(h):
    same_day = h.day[1:] == h.day[:-1]
    diffs = (h.slot[1:] - h.slot[:-1])[same_day]
    step_histogram = {}
    values, counts = np.unique(diffs, return_counts=True)
    for value, count in zip(values, counts, strict=True):
        step_histogram[str(int(value))] = int(count)

    per_source = {}
    for i, name in enumerate(h.sources):
        mask = h.source == i
        rows = int(mask.sum())
        per_source[name] = {
            "rows": rows,
            "first_date": h.dates[h.day[mask][0]] if rows else None,
            "last_date": h.dates[h.day[mask][-1]] if rows else None,
        }

    counts_per_day = np.bincount(h.day, minlength=len(h.dates)) if h.dates else np.array([])
    eligible_count = int(h.eligible.sum())

    return {
        "sha256": h.sha256,
        "rows": h.n,
        "observed_days": len(h.dates),
        "empty_dates": list(h.empty_dates),
        "first_date": h.dates[0] if h.dates else None,
        "last_date": h.dates[-1] if h.dates else None,
        "per_source": per_source,
        "step_histogram": step_histogram,
        "eligible_count": eligible_count,
        "non_eligible_count": h.n - eligible_count,
        "segments_count": int(h.segment.max()) + 1 if h.n else 0,
        "merged_duplicates": len(h.provenance),
        "rows_per_day_min": int(counts_per_day.min()) if len(counts_per_day) else None,
        "rows_per_day_median": float(np.median(counts_per_day)) if len(counts_per_day) else None,
        "rows_per_day_max": int(counts_per_day.max()) if len(counts_per_day) else None,
    }


def row_at(h, label):
    date_str, _, time_str = label.partition(" ")
    if date_str in h.dates:
        day_idx = h.dates.index(date_str)
        hour, minute = map(int, time_str.split(":"))
        target_slot = hour * 60 + minute
        start = int(np.searchsorted(h.day, day_idx, side="left"))
        end = int(np.searchsorted(h.day, day_idx, side="right"))
        pos = int(np.searchsorted(h.slot[start:end], target_slot))
        if pos < end - start and h.slot[start + pos] == target_slot:
            return start + pos
    labels = [h.label(i) for i in range(h.n)]
    pos = bisect_left(labels, label)
    before = labels[max(0, pos - 2):pos]
    after = labels[pos:pos + 2]
    raise DataError(f"No row at {label}; nearest before: {before}; nearest after: {after}")
