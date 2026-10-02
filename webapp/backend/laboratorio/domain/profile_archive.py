"""Authenticated binding between imported canonical history and frozen rankings."""

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from laboratorio.domain.contracts import SYSTEMS, GameProfile
from laboratorio.domain.selection import parity_numbers, parity_votes
from laboratorio.engine.adapter import DataError, History, Rankings, load_verified_archive
from laboratorio.importing.datasets import SavedDataset
from laboratorio.settings import Settings


@dataclass(frozen=True, slots=True)
class ArchivedBinding:
    """A full-row identity binding; indices are canonical draw indices, not bet ordinals."""

    history: History
    rankings: Rankings
    _orders: dict[str, np.ndarray]
    _parity: np.ndarray

    @property
    def canonical_draw_count(self) -> int:
        return len(self.history.labels)

    @property
    def rank_row_ids(self) -> tuple[int, ...]:
        return tuple(int(row_id) for row_id in self.rankings.row_ids)

    def canonical_draw_index(self, draw_index: int) -> int:
        _draw_index(draw_index, self.canonical_draw_count)
        return draw_index

    def prior_cutoff(self, draw_index: int) -> str | None:
        """Latest canonical row available before selection on this draw."""
        _draw_index(draw_index, self.canonical_draw_count)
        return self.history.labels[draw_index - 1] if draw_index else None

    def select(
        self, kind: str, draw_index: int, coverage: int, *, system: str | None = None
    ) -> tuple[int, ...]:
        _draw_index(draw_index, self.canonical_draw_count)
        if type(coverage) is not int or not 1 <= coverage <= 100:
            raise DataError("coverage must be an exact integer from 1 to 100")
        if kind == "parity":
            if coverage != 50:
                raise DataError("parity_50 selection requires coverage 50")
            return tuple(int(number) for number in parity_numbers(int(self._parity[draw_index])))
        if kind in ("cold", "transition"):
            if system is not None and system != kind:
                raise DataError("archived kind and requested system differ")
            system = kind
        elif kind == "topk":
            if type(system) is not str or system not in SYSTEMS:
                raise DataError("topk requires a registered archived system")
        else:
            raise DataError("unsupported archived selection kind")

        position = int(np.searchsorted(self.rankings.row_ids, draw_index))
        if position >= len(self.rankings.row_ids) or self.rankings.row_ids[position] != draw_index:
            raise DataError("draw has no archived ranking")
        if system not in self._orders:
            self._orders[system] = self.rankings.family(system)
        order = self._orders[system]
        return tuple(int(number) for number in order[position, :coverage])


def _draw_index(draw_index: int, count: int) -> None:
    if type(draw_index) is not int or not 0 <= draw_index < count:
        raise DataError("canonical draw index is outside the bound history")


def bind_archived_dataset(dataset: SavedDataset, settings: Settings) -> ArchivedBinding:
    """Bind only an authenticated full import to the frozen archive in trusted Settings."""
    if type(dataset) is not SavedDataset:
        raise TypeError("dataset must be a checked SavedDataset")
    if type(settings) is not Settings:
        raise TypeError("settings must be the trusted Settings instance")
    if not dataset.preview.promotable:
        raise DataError("dataset preview is not promotable")
    if hashlib.sha256(dataset.canonical_json).hexdigest() != dataset.dataset_sha256:
        raise DataError("dataset canonical hash does not authenticate its profile context")
    try:
        envelope = json.loads(dataset.canonical_json)
        profile = GameProfile.model_validate(envelope["profile"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise DataError("dataset canonical profile context is invalid") from exc
    if profile.universe_size != 100 or profile.positions != 5 or not profile.allows_repeats:
        raise DataError("dataset profile is incompatible with archived 100/5/repeat data")
    if hashlib.sha256(dataset.raw_bytes).hexdigest() != dataset.source_sha256:
        raise DataError("dataset source hash does not authenticate raw bytes")

    history, rankings = load_verified_archive(settings)
    if dataset.source_sha256 != history.sha256:
        raise DataError("dataset source is not the authenticated canonical history")
    if len(dataset.preview.records) != len(history.labels):
        raise DataError("dataset does not contain the complete canonical history")
    for index, (record, label, numbers) in enumerate(
        zip(dataset.preview.records, history.labels, history.nums, strict=True)
    ):
        if f"{record.date} {record.time}" != label or record.numbers != tuple(
            int(number) for number in numbers
        ):
            raise DataError(f"dataset canonical row identity differs at draw {index}")

    orders = {system: rankings.family(system) for system in ("cold", "transition")}
    parity = parity_votes(history.nums[:, 0])
    return ArchivedBinding(history, rankings, orders, parity)
