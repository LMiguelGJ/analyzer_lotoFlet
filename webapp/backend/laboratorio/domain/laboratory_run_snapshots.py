"""Immutable metadata snapshots for runs owned by mutable laboratories.

This codec is deliberately separate from the legacy reference-run metadata
codec: its top-level kind identifies the owned-laboratory namespace.
"""

import re
from dataclasses import dataclass

from laboratorio.domain.laboratories import LaboratoryDefinition
from laboratorio.domain.number_lists import DEFAULT_LIST_ID, get_list

SNAPSHOT_VERSION = 1
SNAPSHOT_KIND = "owned_laboratory_run"
_HISTORY_ORIGIN = "frozen"  # Chance Express: the pinned, SHA-verified history
_LIST_HISTORY_ORIGIN = "list"  # other lists: the list's own history file, not pinned
RANKING_METHOD = "causal-on-the-fly/v1"
_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_ROOT_KEYS = {"schema_version", "kind", "definition", "provenance"}
_PROVENANCE_KEYS = {"history_sha256", "rankings_sha256", "history_origin"}
_LIST_PROVENANCE_KEYS = {"history_sha256", "history_origin", "list_id", "ranking_method"}


def _validate_digest(value, field):
    if type(value) is not str or _DIGEST_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class OwnedLaboratoryRunSnapshot:
    """Validated owned-run metadata: a strict definition and frozen source pins."""

    definition: LaboratoryDefinition
    history_sha256: str
    # None for lists whose rankings are computed on the fly (no archived rankings to pin).
    rankings_sha256: str | None
    list_id: str = DEFAULT_LIST_ID
    history_origin: str = _HISTORY_ORIGIN

    def __post_init__(self):
        if type(self.definition) is not LaboratoryDefinition:
            raise ValueError("definition must be a validated LaboratoryDefinition")
        _validate_digest(self.history_sha256, "history_sha256")
        if get_list(self.list_id) is None or self.list_id != self.definition.config.list_id:
            raise ValueError("snapshot list must match the laboratory definition list")
        if self.list_id == DEFAULT_LIST_ID:
            _validate_digest(self.rankings_sha256, "rankings_sha256")
            if self.history_origin != _HISTORY_ORIGIN:
                raise ValueError("history_origin must be frozen")
        else:
            if self.rankings_sha256 is not None:
                raise ValueError("rankings_sha256 does not apply to this list")
            if self.history_origin != _LIST_HISTORY_ORIGIN:
                raise ValueError("history_origin must be list")

    def to_mapping(self):
        """Return a new plain mapping in the owned metadata namespace."""
        if self.list_id == DEFAULT_LIST_ID:
            provenance = {
                "history_sha256": self.history_sha256,
                "rankings_sha256": self.rankings_sha256,
                "history_origin": _HISTORY_ORIGIN,
            }
        else:
            provenance = {
                "history_sha256": self.history_sha256,
                "history_origin": _LIST_HISTORY_ORIGIN,
                "list_id": self.list_id,
                "ranking_method": RANKING_METHOD,
            }
        return {
            "schema_version": SNAPSHOT_VERSION,
            "kind": SNAPSHOT_KIND,
            "definition": self.definition.to_mapping(),
            "provenance": provenance,
        }

    @classmethod
    def from_mapping(cls, value):
        """Decode only the exact owned v1 mapping and its strict definition."""
        if type(value) is not dict or set(value) != _ROOT_KEYS:
            raise ValueError("invalid owned laboratory run snapshot")
        if (
            type(value["schema_version"]) is not int
            or value["schema_version"] != SNAPSHOT_VERSION
            or type(value["kind"]) is not str
            or value["kind"] != SNAPSHOT_KIND
        ):
            raise ValueError("unsupported owned laboratory run snapshot version or kind")

        provenance = value["provenance"]
        if type(provenance) is dict and set(provenance) == _LIST_PROVENANCE_KEYS:
            if (
                type(provenance["history_origin"]) is not str
                or provenance["history_origin"] != _LIST_HISTORY_ORIGIN
                or type(provenance["list_id"]) is not str
                or provenance["list_id"] == DEFAULT_LIST_ID
                or type(provenance["ranking_method"]) is not str
                or provenance["ranking_method"] != RANKING_METHOD
            ):
                raise ValueError("invalid owned laboratory run provenance")
            definition = LaboratoryDefinition.from_mapping(value["definition"])
            return cls(
                definition=definition,
                history_sha256=provenance["history_sha256"],
                rankings_sha256=None,
                list_id=provenance["list_id"],
                history_origin=_LIST_HISTORY_ORIGIN,
            )
        if type(provenance) is not dict or set(provenance) != _PROVENANCE_KEYS:
            raise ValueError("invalid owned laboratory run provenance")
        if (
            type(provenance["history_origin"]) is not str
            or provenance["history_origin"] != _HISTORY_ORIGIN
        ):
            raise ValueError("history_origin must be frozen")

        definition = LaboratoryDefinition.from_mapping(value["definition"])
        return cls(
            definition=definition,
            history_sha256=provenance["history_sha256"],
            rankings_sha256=provenance["rankings_sha256"],
        )
