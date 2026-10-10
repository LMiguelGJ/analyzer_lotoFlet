"""Row builder for consecutive-session runs: history + rankings + strategy -> ``Draw`` rows.

Everything here takes a ``RunSource`` (labels, results and where each draw sits in the frozen
rankings), never the frozen history itself, so extended histories can reuse the same builder.
Orderings never read the draw they are used for, so no future information leaks into a bet.
"""

from collections.abc import MutableMapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np

from laboratorio.domain.contracts import SYSTEMS
from laboratorio.domain.runs import MAX_COVERAGE, NUMBERS
from laboratorio.domain.session import Draw
from laboratorio.engine.adapter import History, LabData, Rankings

SYSTEM_LABELS = dict(SYSTEMS)
MAX_COMPONENTS = len(SYSTEMS)
_POINTS = np.arange(NUMBERS, 0, -1, dtype=np.int64)  # column 0 earns 100 points, the last 1
_PARITY_ORDERS = (
    np.arange(0, NUMBERS, 2, dtype=np.int64),
    np.arange(1, NUMBERS, 2, dtype=np.int64),
)


def _is_int(value: object) -> bool:
    return type(value) is int


@dataclass(frozen=True, slots=True)
class RunSource:
    """Chronological draws; ``rank_pos`` is -1 without a ranking, else the rankings row index."""

    labels: tuple[str, ...]
    minutes: np.ndarray
    results: np.ndarray
    rank_pos: np.ndarray
    sha256: str


def source_from_lab(data: LabData) -> RunSource:
    history = data.history
    rank_pos = np.full(len(history.labels), -1, dtype=np.int32)
    rank_pos[np.asarray(data.rankings.row_ids, dtype=np.int64)] = np.arange(
        len(data.rankings.row_ids), dtype=np.int32
    )
    return RunSource(
        labels=history.labels,
        minutes=np.asarray(history.minutes, dtype=np.int64),
        results=np.asarray(history.nums, dtype=np.uint8),
        rank_pos=rank_pos,
        sha256=history.sha256,
    )


def source_from_history(history: History, frozen_history: History, rankings: Rankings) -> RunSource:
    """Source for a possibly extended history; rankings are matched to draws by label."""
    index_of = {label: index for index, label in enumerate(history.labels)}
    rank_pos = np.full(len(history.labels), -1, dtype=np.int32)
    for position, row_id in enumerate(np.asarray(rankings.row_ids, dtype=np.int64).tolist()):
        target = index_of.get(frozen_history.labels[row_id])
        if target is not None:
            rank_pos[target] = position
    return RunSource(
        labels=history.labels,
        minutes=np.asarray(history.minutes, dtype=np.int64),
        results=np.asarray(history.nums, dtype=np.uint8),
        rank_pos=rank_pos,
        sha256=history.sha256,
    )


@dataclass(frozen=True, slots=True)
class RunStrategy:
    kind: Literal["mix", "parity"]
    components: tuple[tuple[str, int], ...]
    coverage: int

    def __post_init__(self) -> None:
        if self.kind not in ("mix", "parity"):
            raise ValueError("strategy kind must be 'mix' or 'parity'")
        if not _is_int(self.coverage) or not 1 <= self.coverage <= MAX_COVERAGE:
            raise ValueError(f"coverage must be an integer between 1 and {MAX_COVERAGE}")
        if not isinstance(self.components, tuple):
            raise ValueError("components must be a tuple")
        if self.kind == "parity":
            if self.components:
                raise ValueError("a parity strategy takes no components")
            return
        if not 1 <= len(self.components) <= MAX_COMPONENTS:
            raise ValueError(f"a mix needs between 1 and {MAX_COMPONENTS} systems")
        names = set()
        for component in self.components:
            if not isinstance(component, tuple) or len(component) != 2:
                raise ValueError("each component must be a (system, percent) pair")
            name, percent = component
            if not isinstance(name, str) or name not in SYSTEMS:
                raise ValueError(f"unknown ranking system: {name!r}")
            if name in names:
                raise ValueError(f"duplicate ranking system: {name}")
            names.add(name)
            if not _is_int(percent) or not 1 <= percent <= 100:
                raise ValueError("percents must be integers between 1 and 100")
        if sum(percent for _, percent in self.components) != 100:
            raise ValueError("percents must add up to exactly 100")


def _valid_date(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD)")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD)") from None
    return value


@dataclass(frozen=True, slots=True)
class RunWindow:
    start_date: str | None
    end_date: str | None

    def __post_init__(self) -> None:
        start = _valid_date(self.start_date, "start_date")
        end = _valid_date(self.end_date, "end_date")
        if start is not None and end is not None and start > end:
            raise ValueError("start_date must not be after end_date")


_FULL_WINDOW = RunWindow(None, None)


@dataclass(frozen=True, slots=True)
class RunRows:
    rows: list[Draw]
    draws: int
    ranked_draws: int
    first_label: str
    last_label: str


def _window_indexes(source: RunSource, window: RunWindow) -> np.ndarray:
    start, end = window.start_date, window.end_date
    keep = [
        index
        for index, label in enumerate(source.labels)
        if (start is None or label[:10] >= start) and (end is None or label[:10] <= end)
    ]
    return np.asarray(keep, dtype=np.int64)


def _family(rankings, system: str, cache: MutableMapping[str, np.ndarray] | None) -> np.ndarray:
    if cache is None:
        return rankings.family(system)
    if system not in cache:
        cache[system] = rankings.family(system)
    return cache[system]


def _mix_orders(
    source: RunSource,
    rankings,
    strategy: RunStrategy,
    ranked: np.ndarray,
    cache: MutableMapping[str, np.ndarray] | None,
) -> np.ndarray:
    """Top ``coverage`` numbers of the blended ranking for each ranked row, shape (m, k)."""
    positions = source.rank_pos[ranked].astype(np.int64)
    score = np.zeros((len(ranked), NUMBERS), dtype=np.int64)
    lines = np.arange(len(ranked))[:, None]
    for system, percent in strategy.components:
        family = _family(rankings, system, cache)[positions].astype(np.int64)
        score[lines, family] += percent * _POINTS
    # Highest score first; equal scores go to the lower number (keys are unique per row).
    key = -score * NUMBERS + np.arange(NUMBERS, dtype=np.int64)
    return np.argsort(key, axis=1)[:, : strategy.coverage]


def _parity_orders(votes: np.ndarray, rows: np.ndarray, coverage: int) -> np.ndarray:
    chosen = votes[rows]
    return np.where((chosen == 1)[:, None], _PARITY_ORDERS[1], _PARITY_ORDERS[0])[:, :coverage]


def build_run_rows(
    source: RunSource,
    rankings,
    strategy: RunStrategy,
    window: RunWindow = _FULL_WINDOW,
    *,
    parity_votes: np.ndarray | None = None,
    ranked_only: bool = False,
    cache: MutableMapping[str, np.ndarray] | None = None,
) -> RunRows:
    indexes = _window_indexes(source, window)
    if len(indexes) == 0:
        raise ValueError("the selected window has no draws")
    ranked_mask = source.rank_pos[indexes] >= 0

    orders: dict[int, tuple[int, ...]] = {}
    if strategy.kind == "mix":
        ordered = indexes[ranked_mask]
        table = _mix_orders(source, rankings, strategy, ordered, cache) if len(ordered) else None
    else:
        if parity_votes is None or len(parity_votes) != len(source.labels):
            raise ValueError("parity needs one vote per draw of the source")
        ordered = indexes[ranked_mask] if ranked_only else indexes
        table = _parity_orders(np.asarray(parity_votes), ordered, strategy.coverage)
    if table is not None:
        orders = dict(zip(ordered.tolist(), map(tuple, table.tolist()), strict=True))

    labels = source.labels
    minutes = source.minutes[indexes].tolist()
    results = [tuple(row) for row in source.results[indexes].tolist()]
    rows = [
        Draw(labels[index], minute, result, orders.get(index))
        for index, minute, result in zip(indexes.tolist(), minutes, results, strict=True)
    ]
    return RunRows(
        rows=rows,
        draws=len(rows),
        ranked_draws=int(ranked_mask.sum()),
        first_label=rows[0].label,
        last_label=rows[-1].label,
    )
