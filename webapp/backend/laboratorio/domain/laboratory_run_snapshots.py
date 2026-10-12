"""Immutable metadata snapshots for runs owned by mutable laboratories.

This codec is deliberately separate from the legacy reference-run metadata
codec: its top-level kind identifies the owned-laboratory namespace.
"""

import re
from dataclasses import dataclass

from laboratorio.domain.laboratories import LaboratoryDefinition

SNAPSHOT_VERSION = 1
SNAPSHOT_KIND = "owned_laboratory_run"
_HISTORY_ORIGIN = "frozen"
_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_ROOT_KEYS = {"schema_version", "kind", "definition", "provenance"}
_PROVENANCE_KEYS = {"history_sha256", "rankings_sha256", "history_origin"}


def _validate_digest(value, field):
    if type(value) is not str or _DIGEST_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class OwnedLaboratoryRunSnapshot:
    """Validated owned-run metadata: a strict definition and frozen source pins."""

    definition: LaboratoryDefinition
    history_sha256: str
    rankings_sha256: str

    def __post_init__(self):
        if type(self.definition) is not LaboratoryDefinition:
            raise ValueError("definition must be a validated LaboratoryDefinition")
        _validate_digest(self.history_sha256, "history_sha256")
        _validate_digest(self.rankings_sha256, "rankings_sha256")

    def to_mapping(self):
        """Return a new plain mapping in the owned metadata namespace."""
        return {
            "schema_version": SNAPSHOT_VERSION,
            "kind": SNAPSHOT_KIND,
            "definition": self.definition.to_mapping(),
            "provenance": {
                "history_sha256": self.history_sha256,
                "rankings_sha256": self.rankings_sha256,
                "history_origin": _HISTORY_ORIGIN,
            },
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
