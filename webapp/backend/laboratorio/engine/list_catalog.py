"""Loads the histories of the selectable number lists, lazily and cached per list id."""

import threading
from dataclasses import dataclass
from pathlib import Path

from laboratorio.domain.number_lists import CATALOG, DEFAULT_LIST_ID, NumberList, get_list
from laboratorio.engine.adapter import DataError, History, LabData, load_history
from laboratorio.engine.causal_rankings import CausalRankings
from laboratorio.settings import Settings
from laboratorio.storage.repository import Repository


class ListError(Exception):
    """A list request failed; ``kind`` is 'unknown' or 'unavailable' and ``message`` is Spanish."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True, slots=True)
class ListSummary:
    definition: NumberList
    available: bool
    draws: int | None
    first_label: str | None
    last_label: str | None


class ListCatalog:
    """Resolves list files, caches each parsed history and tracks the persisted active list."""

    def __init__(self, repo: Repository, lab_data, settings: Settings):
        self._repo = repo
        self._lab = lab_data
        self._settings = settings
        self._lock = threading.RLock()
        # list id -> (file signature, history); the signature invalidates on file changes.
        self._cache: dict[str, tuple[tuple[int, int], History]] = {}
        # list id -> LabData built over the cached history (rankings computed on the fly).
        self._lab_cache: dict[str, LabData] = {}

    # ------------------------------------------------------------------- paths

    def history_path(self, definition: NumberList) -> Path:
        if definition.id == DEFAULT_LIST_ID:
            return self._settings.history_path  # honors LABORATORIO_HISTORY
        return self._settings.repo_root / definition.history_file

    # ----------------------------------------------------------------- loading

    def history(self, list_id: str) -> History:
        """The parsed history of a list; ``ListError`` when unknown or unusable."""
        definition = get_list(list_id)
        if definition is None:
            raise ListError("unknown", "Esa lista no existe.")
        if definition.id == DEFAULT_LIST_ID:
            # Loaded and SHA-verified at startup; never re-parsed.
            return self._lab.history
        path = self.history_path(definition)
        try:
            stat = path.stat()
        except OSError:
            raise self._unavailable(definition) from None
        signature = (stat.st_mtime_ns, stat.st_size)
        with self._lock:
            cached = self._cache.get(definition.id)
            if cached is not None and cached[0] == signature:
                return cached[1]
            try:
                history = load_history(path, definition.history_sha256, definition.positions)
            except (DataError, OSError):
                self._cache.pop(definition.id, None)
                raise self._unavailable(definition) from None
            self._cache[definition.id] = (signature, history)
            return history

    def lab_data(self, list_id: str) -> LabData:
        """Laboratory inputs of a list: Chance gets the frozen data, others on-the-fly rankings.

        The returned object is the same one for as long as the list file is unchanged, so its
        parity votes and ranking matrices are computed once.
        """
        definition = get_list(list_id)
        if definition is None:
            raise ListError("unknown", "Esa lista no existe.")
        if definition.id == DEFAULT_LIST_ID:
            return self._lab
        history = self.history(list_id)
        with self._lock:
            cached = self._lab_cache.get(list_id)
            if cached is not None and cached.history is history:
                return cached
            data = LabData(
                history=history,
                rankings=CausalRankings(history.nums),  # type: ignore[arg-type]
                settings=self._settings,
            )
            self._lab_cache[list_id] = data
            return data

    @staticmethod
    def _unavailable(definition: NumberList) -> ListError:
        return ListError(
            "unavailable",
            f"La lista «{definition.name}» no está disponible en este equipo: "
            "falta su archivo de historial.",
        )

    # ------------------------------------------------------------- active list

    def active_id(self) -> str:
        stored = self._repo.get_active_list_id()
        return stored if get_list(stored) is not None else DEFAULT_LIST_ID

    def active(self) -> NumberList:
        definition = get_list(self.active_id())
        assert definition is not None
        return definition

    def set_active(self, list_id: str) -> None:
        self.history(list_id)  # rejects unknown and unavailable lists before persisting
        self._repo.set_active_list_id(list_id)

    # ----------------------------------------------------------------- listing

    def summaries(self) -> list[ListSummary]:
        result = []
        for definition in CATALOG:
            try:
                labels = self.history(definition.id).labels
            except ListError:
                result.append(ListSummary(definition, False, None, None, None))
                continue
            result.append(
                ListSummary(
                    definition,
                    True,
                    len(labels),
                    labels[0] if labels else None,
                    labels[-1] if labels else None,
                )
            )
        return result
