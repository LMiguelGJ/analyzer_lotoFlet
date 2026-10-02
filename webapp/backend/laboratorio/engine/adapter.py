"""Frozen data access: history JSON, ranking NPZ and cached parity votes.

This is the only module that reads the two frozen inputs on disk. Everything
here is written from scratch; the archived reference implementation was only
read as behavioral reference, never imported (decision D1).
"""

import contextlib
import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np

from laboratorio.domain.contracts import (
    DRAW_FORMAT,
    SYSTEMS,
    Conditions,
    SelectorKind,
    Strategy,
)
from laboratorio.domain.selection import PARITY_ALGORITHM, blend_order, parity_numbers, random_order
from laboratorio.domain.selection import parity_votes as compute_parity_votes
from laboratorio.domain.session import Draw
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256, Settings

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_HORA_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
_NUM_RE = re.compile(r"[0-9]{2}")
_EPOCH = datetime(1970, 1, 1)


class DataError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class History:
    labels: tuple[str, ...]
    nums: np.ndarray
    minutes: np.ndarray
    sha256: str


@dataclass(frozen=True, slots=True)
class Rankings:
    row_ids: np.ndarray
    path: Path
    _verified_bytes: bytes = field(default=b"", repr=False, compare=False)

    def family(self, system: str) -> np.ndarray:
        if system not in SYSTEMS:
            raise DataError(f"ranking system unavailable: {system}")
        key = f"ranking100__{system}"
        # Never reopen the path: it may have been replaced since SHA validation.
        with np.load(io.BytesIO(self._verified_bytes), allow_pickle=False) as archive:
            if key not in archive.files:
                raise DataError(f"ranking system unavailable: {system}")
            ranks = archive[key]
        n = len(self.row_ids)
        if ranks.shape != (n, 100) or ranks.dtype != np.uint8:
            raise DataError(
                f"{key} has shape/dtype {ranks.shape}/{ranks.dtype}, expected ({n}, 100)/uint8"
            )
        expected_row = np.arange(100, dtype=np.uint8)
        for start in range(0, n, 4096):
            chunk = ranks[start : start + 4096]
            if not np.all(np.sort(chunk, axis=1) == expected_row):
                raise DataError(f"{key} contains a row that is not a permutation")
        return ranks


@dataclass(frozen=True, slots=True)
class LabData:
    history: History
    rankings: Rankings
    settings: Settings
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    def parity_votes(self) -> np.ndarray:
        if "parity" in self._cache:
            return self._cache["parity"]
        cache_path = (
            self.settings.cache_dir / f"parity-{self.history.sha256[:16]}-{PARITY_ALGORITHM}.npz"
        )
        n = len(self.history.labels)
        votes = _load_cached_parity(cache_path, n, self.history.sha256)
        if votes is None:
            votes = compute_parity_votes(self.history.nums[:, 0])
            _write_cached_parity(cache_path, votes, self.history.sha256)
        self._cache["parity"] = votes
        return votes


def _validated_records(date_key: str, records: list) -> list[tuple[str, tuple[int, ...]]]:
    normalized = []
    for rec in records:
        if not isinstance(rec, dict):
            raise DataError(f"draw record at {date_key} must be a dict: {rec!r}")
        hora = rec.get("hora")
        if not isinstance(hora, str) or not _HORA_RE.fullmatch(hora):
            raise DataError(f"invalid hora at {date_key}: {hora!r}")
        numeros = rec.get("numeros")
        if not isinstance(numeros, list) or len(numeros) != 5:
            raise DataError(f"invalid numeros count at {date_key} {hora}: {numeros!r}")
        numbers = []
        for x in numeros:
            if not isinstance(x, str) or not _NUM_RE.fullmatch(x):
                raise DataError(f"invalid number at {date_key} {hora}: {x!r}")
            numbers.append(int(x))
        normalized.append((hora, tuple(numbers)))
    normalized.sort(key=lambda item: item[0])
    return normalized


def _merge_duplicates(
    date_key: str, normalized: list[tuple[str, tuple[int, ...]]]
) -> list[tuple[str, tuple[int, ...]]]:
    merged = []
    i = 0
    while i < len(normalized):
        hora, numbers = normalized[i]
        j = i + 1
        while j < len(normalized) and normalized[j][0] == hora:
            if normalized[j][1] != numbers:
                raise DataError(
                    f"Conflicting duplicate at {date_key} {hora}: {numbers} vs {normalized[j][1]}"
                )
            j += 1
        merged.append((hora, numbers))
        i = j
    return merged


def _minutes_since_epoch(label: str) -> int:
    return int((datetime.strptime(label, DRAW_FORMAT) - _EPOCH).total_seconds() // 60)


def parse_history(raw: bytes) -> History:
    sha256 = hashlib.sha256(raw).hexdigest()
    try:
        data = json.loads(raw)
        sorteos_por_fecha = data["sorteos_por_fecha"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DataError(f"cannot read draw history: {exc}") from exc
    if not isinstance(sorteos_por_fecha, dict):
        raise DataError("sorteos_por_fecha must be a dict")

    rows: list[tuple[str, tuple[int, ...]]] = []
    for date_key in sorted(sorteos_por_fecha):
        if not isinstance(date_key, str) or not _DATE_RE.fullmatch(date_key):
            raise DataError(f"invalid date key: {date_key!r}")
        try:
            date.fromisoformat(date_key)
        except ValueError as exc:
            raise DataError(f"invalid date key: {date_key}") from exc

        records = sorteos_por_fecha[date_key]
        if not isinstance(records, list):
            raise DataError(f"draw list for {date_key} must be a list")
        if not records:
            continue

        normalized = _validated_records(date_key, records)
        for hora, numbers in _merge_duplicates(date_key, normalized):
            rows.append((f"{date_key} {hora}", numbers))

    labels = tuple(label for label, _ in rows)
    nums = np.asarray([numbers for _, numbers in rows], dtype=np.uint8).reshape(-1, 5)
    minutes = np.asarray([_minutes_since_epoch(label) for label in labels], dtype=np.int64)
    return History(labels=labels, nums=nums, minutes=minutes, sha256=sha256)


def _read_bytes_verified(path: Path, expected_sha: str | None, label: str) -> bytes:
    path = Path(path)
    if not path.is_file():
        raise DataError(f"{label} file not found: {path}")
    raw = path.read_bytes()
    if expected_sha is not None:
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected_sha:
            raise DataError(f"{label} SHA-256 mismatch: expected {expected_sha}, got {actual}")
    return raw


def load_history(path: Path, expected_sha: str | None) -> History:
    raw = _read_bytes_verified(Path(path), expected_sha, "History")
    return parse_history(raw)


def load_rankings(path: Path, expected_sha: str | None, history: History) -> Rankings:
    path = Path(path)
    raw = _read_bytes_verified(path, expected_sha, "Rankings")
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        row_ids = archive["row_ids"]
        timestamps = archive["timestamps"]

    if row_ids.dtype != np.int64:
        raise DataError(f"row_ids must be int64, got {row_ids.dtype}")
    if row_ids.ndim != 1 or len(row_ids) == 0:
        raise DataError("row_ids must be a non-empty 1-D array")
    if np.any(np.diff(row_ids) <= 0):
        raise DataError("row_ids must be strictly increasing")
    if np.any(row_ids < 0) or np.any(row_ids >= len(history.labels)):
        raise DataError("row_ids must be within the bounds of the history")

    expected_timestamps = np.asarray([history.labels[i] for i in row_ids])
    if not np.array_equal(np.asarray(timestamps), expected_timestamps):
        raise DataError("rankings timestamps do not align with the history")

    return Rankings(row_ids=row_ids.copy(), path=path, _verified_bytes=raw)


def _votes_digest(votes: np.ndarray) -> str:
    return hashlib.sha256(votes.tobytes()).hexdigest()


def _load_cached_parity(path: Path, n: int, history_sha256: str) -> np.ndarray | None:
    if not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=False) as archive:
            votes = archive["votes"]
            history = archive["history_sha256"]
            algorithm = archive["algorithm"]
            digest = archive["votes_sha256"]
    except (OSError, ValueError, EOFError, KeyError, zipfile.BadZipFile):
        return None
    if (
        votes.shape != (n,)
        or votes.dtype != np.int8
        or not np.all((votes == 0) | (votes == 1))
        or history.shape != ()
        or algorithm.shape != ()
        or digest.shape != ()
        or history.item() != history_sha256
        or algorithm.item() != PARITY_ALGORITHM
        or digest.item() != _votes_digest(votes)
    ):
        return None
    return votes


def _write_cached_parity(path: Path, votes: np.ndarray, history_sha256: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            np.savez(
                fh,
                votes=votes,
                history_sha256=history_sha256,
                algorithm=PARITY_ALGORITHM,
                votes_sha256=_votes_digest(votes),
            )
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp_name)
        raise


def load_verified_archive(settings: Settings) -> tuple[History, Rankings]:
    """Load trusted frozen assets from Settings paths, verifying both pinned hashes."""
    if type(settings) is not Settings:
        raise TypeError("settings must be the trusted Settings instance")
    history = load_history(settings.history_path, HISTORY_SHA256)
    rankings = load_rankings(settings.rankings_path, RANKINGS_SHA256, history)
    return history, rankings


def open_lab_data(settings: Settings) -> LabData:
    history, rankings = load_verified_archive(settings)
    return LabData(history=history, rankings=rankings, settings=settings)


def session_draws(data: LabData, strategy: Strategy, conditions: Conditions):
    """Prepare chronological domain rows from verified snapshots, never source paths.

    A ranked starting draw is required. Later unranked history rows remain in
    the stream so the pure session clock sees them, but have no selection.
    """
    history, rankings = data.history, data.rankings
    start = int(np.searchsorted(history.labels, conditions.start_draw))
    if start >= len(history.labels) or history.labels[start] != conditions.start_draw:
        raise DataError("start draw does not exist")
    rank_index = int(np.searchsorted(rankings.row_ids, start))
    if rank_index >= len(rankings.row_ids) or rankings.row_ids[rank_index] != start:
        raise DataError("start draw has no ranking")

    families = {}
    components = strategy.components or ()
    if strategy.selector is SelectorKind.SYSTEM:
        assert strategy.system is not None  # validated by Strategy
        systems = (strategy.system,)
    elif strategy.selector is SelectorKind.BLEND:
        systems = tuple(component.system for component in components)
    else:
        systems = ()
    for system in systems:
        key = f"ranking:{system}"
        if key not in data._cache:
            data._cache[key] = rankings.family(system)
        families[system] = data._cache[key]
    weights = {component.system: component.weight for component in components}
    votes = data.parity_votes() if strategy.selector is SelectorKind.PARITY else None

    def rows():
        cursor = rank_index
        for index in range(start, len(history.labels)):
            order = None
            if cursor < len(rankings.row_ids) and rankings.row_ids[cursor] == index:
                if strategy.selector is SelectorKind.SYSTEM:
                    assert strategy.system is not None
                    order = families[strategy.system][cursor]
                elif strategy.selector is SelectorKind.BLEND:
                    order = blend_order(
                        {key: value[cursor] for key, value in families.items()}, weights
                    )
                elif strategy.selector is SelectorKind.RANDOM:
                    order = random_order(conditions.seed, history.labels[index])
                else:
                    assert votes is not None
                    order = parity_numbers(int(votes[index]))
                cursor += 1
            result = history.nums[index]
            yield Draw(
                history.labels[index],
                int(history.minutes[index]),
                (int(result[0]), int(result[1]), int(result[2]), int(result[3]), int(result[4])),
                None if order is None else tuple(int(n) for n in order[: strategy.coverage]),
            )

    return rows()
