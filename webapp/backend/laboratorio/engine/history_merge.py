"""Pure history merging: canonical serialization plus a conflict-checked union by draw label."""

import json
from dataclasses import dataclass

import numpy as np

from laboratorio.engine.adapter import History, parse_history

MAX_DRAWS = 400_000
MAX_CONFLICTS_SHOWN = 5
_METADATA = {"schema_version": 1, "juego": "Quiniela 80", "origen": "laboratorio"}


class HistoryConflict(ValueError):
    """The upload contradicts the base history for one or more draw labels."""

    def __init__(self, labels: list[str]):
        self.labels = labels
        super().__init__("conflicting draws: " + ", ".join(labels[:MAX_CONFLICTS_SHOWN]))


@dataclass(frozen=True, slots=True)
class MergeResult:
    history_bytes: bytes
    history: History
    added: int
    total: int


def canonical_history_bytes(labels, nums) -> bytes:
    """Deterministic UTF-8 JSON of a history, sorted by label, ready for ``parse_history``."""
    by_date: dict[str, list[dict]] = {}
    for label, row in sorted(zip(labels, np.asarray(nums).tolist(), strict=True)):
        day, hora = label.split(" ")
        by_date.setdefault(day, []).append({"hora": hora, "numeros": [f"{n:02d}" for n in row]})
    document = {"metadata": _METADATA, "sorteos_por_fecha": by_date}
    return json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _rows(history: History) -> dict[str, tuple[int, ...]]:
    return {
        label: tuple(row) for label, row in zip(history.labels, history.nums.tolist(), strict=True)
    }


def merge_histories(base: History, upload: History) -> MergeResult:
    rows = _rows(base)
    new_rows = _rows(upload)
    conflicts = sorted(label for label, row in new_rows.items() if rows.get(label, row) != row)
    if conflicts:
        raise HistoryConflict(conflicts)
    added = sum(1 for label in new_rows if label not in rows)
    if len(rows) + added > MAX_DRAWS:
        raise ValueError(f"the merged history would exceed {MAX_DRAWS} draws")
    if added == 0:
        raw = canonical_history_bytes(base.labels, base.nums)
        return MergeResult(raw, parse_history(raw), 0, len(rows))
    rows.update(new_rows)
    labels = sorted(rows)
    raw = canonical_history_bytes(labels, [rows[label] for label in labels])
    return MergeResult(raw, parse_history(raw), added, len(labels))
