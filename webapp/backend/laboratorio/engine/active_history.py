"""Catalog of immutable history snapshots: the frozen base plus app-imported extensions."""

import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal

import numpy as np

from laboratorio.engine.adapter import (
    DataError,
    LabData,
    parity_votes_for,
    parse_history,
)
from laboratorio.engine.history_merge import (
    HistoryConflict,
    MergeResult,
    canonical_history_bytes,
    merge_histories,
)
from laboratorio.engine.run_data import RunSource, source_from_history, source_from_lab
from laboratorio.settings import Settings
from laboratorio.storage.quota import QuotaExceeded
from laboratorio.storage.repository import Repository

_IMPORT_CACHE_SIZE = 2


class HistoryImportError(ValueError):
    """An import failed; ``kind`` is 'invalid', 'conflict' or 'quota' and ``message`` is Spanish."""

    def __init__(self, kind: Literal["invalid", "conflict", "quota"], message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True, slots=True)
class HistorySnapshot:
    sha256: str
    origin: Literal["frozen", "import"]
    history: object  # History
    source: RunSource
    ranked_draws: int
    created_at: str | None
    added_draws: int


@dataclass(frozen=True, slots=True)
class ImportOutcome:
    created: bool
    snapshot: HistorySnapshot
    added: int


class HistoryCatalog:
    def __init__(self, repo: Repository, lab_data: LabData, settings: Settings):
        self._repo = repo
        self._lab = lab_data
        self._settings = settings
        self._lock = threading.RLock()
        self._frozen: HistorySnapshot | None = None
        self._imports: OrderedDict[str, HistorySnapshot] = OrderedDict()

    # ------------------------------------------------------------------ snapshots

    def _frozen_snapshot(self) -> HistorySnapshot:
        if self._frozen is None:
            lab = self._lab
            self._frozen = HistorySnapshot(
                sha256=lab.history.sha256,
                origin="frozen",
                history=lab.history,
                source=source_from_lab(lab),
                ranked_draws=len(lab.rankings.row_ids),
                created_at=None,
                added_draws=0,
            )
        return self._frozen

    def _imported_snapshot(self, sha256: str) -> HistorySnapshot | None:
        cached = self._imports.get(sha256)
        if cached is not None:
            self._imports.move_to_end(sha256)
            return cached
        row = self._repo.get_history_source(sha256)
        if row is None:
            return None
        raw = row["raw_bytes"]
        if hashlib.sha256(raw).hexdigest() != sha256:
            raise DataError(f"stored history {sha256} does not match its hash")
        history = parse_history(raw)
        if canonical_history_bytes(history.labels, history.nums) != raw:
            raise DataError(f"stored history {sha256} is not canonical")
        source = source_from_history(history, self._lab.history, self._lab.rankings)
        snapshot = HistorySnapshot(
            sha256=sha256,
            origin="import",
            history=history,
            source=source,
            ranked_draws=int((source.rank_pos >= 0).sum()),
            created_at=row["created_at"],
            added_draws=row["added_draws"],
        )
        self._imports[sha256] = snapshot
        while len(self._imports) > _IMPORT_CACHE_SIZE:
            self._imports.popitem(last=False)
        return snapshot

    def active(self) -> HistorySnapshot:
        with self._lock:
            sha = self._repo.get_active_history_sha()
            if sha is None or sha == self._lab.history.sha256:
                return self._frozen_snapshot()
            snapshot = self._imported_snapshot(sha)
            if snapshot is None:
                raise DataError(f"active history {sha} is missing")
            return snapshot

    def snapshot(self, sha256: str) -> HistorySnapshot | None:
        with self._lock:
            if sha256 == self._lab.history.sha256:
                return self._frozen_snapshot()
            return self._imported_snapshot(sha256)

    def parity_votes(self, snapshot: HistorySnapshot) -> np.ndarray:
        if snapshot.origin == "frozen":
            return self._lab.parity_votes()
        return parity_votes_for(snapshot.history, self._settings)

    # -------------------------------------------------------------------- imports

    def import_history(self, raw: bytes) -> ImportOutcome:
        with self._lock:
            try:
                upload = parse_history(raw)
            except DataError:
                raise HistoryImportError(
                    "invalid", "El archivo no tiene el formato de historial esperado."
                ) from None
            if len(upload.labels) == 0:
                raise HistoryImportError(
                    "invalid", "El archivo no tiene el formato de historial esperado."
                )
            active = self.active()
            try:
                merged = merge_histories(active.history, upload)
            except HistoryConflict as exc:
                shown = ", ".join(exc.labels[:5])
                raise HistoryImportError(
                    "conflict", f"Hay sorteos que contradicen el historial actual: {shown}."
                ) from None
            except ValueError:
                raise HistoryImportError(
                    "invalid", "El historial combinado supera el máximo de sorteos permitido."
                ) from None
            if merged.added == 0:
                return ImportOutcome(False, active, 0)
            return self._persist(merged)

    def _persist(self, merged: MergeResult) -> ImportOutcome:
        history = merged.history
        try:
            created = self._repo.import_history_source(
                history.sha256,
                merged.history_bytes,
                draws=merged.total,
                added_draws=merged.added,
                first_label=history.labels[0],
                last_label=history.labels[-1],
                quota_bytes=self._settings.quota_bytes,
                quota_explicit=self._settings.is_quota_explicit,
            )
        except QuotaExceeded:
            raise HistoryImportError("quota", "No hay espacio suficiente en la cuota.") from None
        snapshot = self._imported_snapshot(history.sha256)
        assert snapshot is not None
        return ImportOutcome(created, snapshot, merged.added)

    def list_sources(self) -> list[dict]:
        with self._lock:
            frozen = self._frozen_snapshot()
            active_sha = self.active().sha256
            entries = [
                {
                    "sha256": frozen.sha256,
                    "origin": "frozen",
                    "draws": len(frozen.history.labels),
                    "added_draws": 0,
                    "first_label": frozen.history.labels[0],
                    "last_label": frozen.history.labels[-1],
                    "created_at": None,
                    "active": frozen.sha256 == active_sha,
                }
            ]
            for item in self._repo.list_history_sources():
                entries.append({**item, "origin": "import", "active": item["sha256"] == active_sha})
            return entries
