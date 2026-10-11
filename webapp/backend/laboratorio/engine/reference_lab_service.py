"""Bounded in-memory execution for immutable historical laboratory contracts."""

from dataclasses import dataclass
from typing import Literal

from laboratorio.domain.reference_labs import ReferenceLab, get_reference_lab
from laboratorio.engine.adapter import LabData
from laboratorio.engine.reference_labs import ReferenceResult, run_reference_lab
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256


@dataclass(frozen=True, slots=True)
class ReferenceLabProvenance:
    history_sha256: str
    history_origin: Literal["frozen"]
    rankings_sha256: str


@dataclass(frozen=True, slots=True)
class ReferenceLabExecution:
    result: ReferenceResult
    provenance: ReferenceLabProvenance
    contract_version: int = 1


class ReferenceLabServiceError(ValueError):
    """Expected request/source failure; ``kind`` maps to an HTTP status at the API edge."""

    def __init__(self, kind: Literal["invalid", "not_found", "conflict"], message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def execute_reference_lab(
    lab_id: str, required_history_sha256: str, data: LabData
) -> ReferenceLabExecution:
    """Replay one fixed lab against the already-loaded, pinned frozen source only."""
    if not isinstance(lab_id, str):
        raise ReferenceLabServiceError("invalid", "lab_id must be a string")
    try:
        lab: ReferenceLab = get_reference_lab(lab_id)
    except ValueError:
        raise ReferenceLabServiceError(
            "not_found", f"unknown reference laboratory: {lab_id}"
        ) from None

    if (
        not isinstance(required_history_sha256, str)
        or len(required_history_sha256) != 64
        or any(char not in "0123456789abcdef" for char in required_history_sha256)
    ):
        raise ReferenceLabServiceError(
            "invalid", "history_sha256 must be 64 lowercase ASCII hex characters"
        )
    if data.history.sha256 != HISTORY_SHA256:
        raise ReferenceLabServiceError(
            "conflict", "loaded reference history is not the pinned frozen source"
        )
    if required_history_sha256 != data.history.sha256:
        raise ReferenceLabServiceError(
            "conflict", "requested history is not the loaded frozen reference source"
        )

    parity_votes = data.parity_votes() if lab.selection_kind == "parity" else None
    result = run_reference_lab(lab, data.history, data.rankings, parity_votes=parity_votes)
    return ReferenceLabExecution(
        result=result,
        provenance=ReferenceLabProvenance(
            history_sha256=data.history.sha256,
            history_origin="frozen",
            rankings_sha256=RANKINGS_SHA256,
        ),
    )
