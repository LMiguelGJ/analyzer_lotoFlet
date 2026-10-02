"""Immutable dataset value and integrity checks; transaction ownership stays in Repository."""

import hashlib
import json
from dataclasses import dataclass

from laboratorio.domain.contracts import GameProfile
from laboratorio.importing.history import history_options, parse_history
from laboratorio.importing.records import (
    ClockDeclaration,
    ColumnMapping,
    ImportPreview,
    SourceMetadata,
    canonical_bytes,
    parse_records,
)


@dataclass(frozen=True)
class SavedDataset:
    dataset_sha256: str
    source_sha256: str
    canonical_json: bytes
    raw_bytes: bytes
    created_at: str
    preview: ImportPreview


@dataclass(frozen=True)
class Promotion:
    dataset: SavedDataset
    created: bool
    duplicate_source_differs: bool
    submitted_source_sha256: str


def checked_dataset(row) -> SavedDataset:
    """Reject corrupt bytes, context or hashes instead of trusting stored metadata."""
    dataset_hash, source_hash, text, raw, created = row
    try:
        if not isinstance(text, str) or not isinstance(raw, bytes):
            raise ValueError("invalid stored dataset types")
        encoded = text.encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != dataset_hash:
            raise ValueError("canonical hash mismatch")
        if hashlib.sha256(raw).hexdigest() != source_hash:
            raise ValueError("source hash mismatch")
        envelope = json.loads(text)
        mapping = envelope["mapping"]
        clock = envelope["clock"]
        source = envelope["source"]
        profile = GameProfile.model_validate(envelope["profile"])
        opts = {
            "format": envelope["format"],
            "mapping": ColumnMapping(mapping["date"], mapping["time"], tuple(mapping["positions"])),
            "clock": ClockDeclaration(clock["mode"], clock["zone"]),
            "source": SourceMetadata(
                source["source_id"], source["kind"], source["revision"], source["provenance"]
            ),
            "profile": profile,
        }
        if envelope["format"] == "history_json":
            preview = parse_history(raw, profile)
            opts = history_options(json.loads(raw), profile)
        else:
            preview = parse_records(raw, **opts)
        if not preview.promotable or preview.dataset_sha256 != dataset_hash:
            raise ValueError("stored dataset cannot be reparsed")
        if encoded != canonical_bytes(preview.records, **opts):
            raise ValueError("stored canonical context differs from source")
        if preview.source_sha256 != source_hash:
            raise ValueError("source hash mismatch")
    except (KeyError, TypeError, ValueError, UnicodeError, AttributeError) as exc:
        raise ValueError("corrupt stored dataset") from exc
    return SavedDataset(dataset_hash, source_hash, encoded, raw, created, preview)
