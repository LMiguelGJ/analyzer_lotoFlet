"""Replay validated user definitions without resolving an archived catalog identity."""

from dataclasses import dataclass
from typing import Literal

from laboratorio.domain.laboratories import LaboratoryDefinition
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.engine.adapter import LabData
from laboratorio.engine.reference_labs import ReferenceResult, run_reference_lab
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256


class OwnedLaboratoryServiceError(ValueError):
    def __init__(self, kind: Literal["invalid", "conflict"], message: str):
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True, slots=True)
class OwnedLaboratoryExecution:
    snapshot: OwnedLaboratoryRunSnapshot
    result: ReferenceResult


def execute_owned_laboratory(
    definition: LaboratoryDefinition, required_history_sha256: str, data: LabData
) -> OwnedLaboratoryExecution:
    """Caller holds the shared rankings lock, including parity-cache initialization."""
    try:
        if type(definition) is not LaboratoryDefinition:
            raise ValueError("definition must be a validated LaboratoryDefinition")
        definition = LaboratoryDefinition.from_mapping(definition.to_mapping())
        if (
            type(required_history_sha256) is not str
            or len(required_history_sha256) != 64
            or any(char not in "0123456789abcdef" for char in required_history_sha256)
        ):
            raise ValueError("history_sha256 must be 64 lowercase ASCII hex characters")
    except (ValueError, TypeError, AttributeError, OverflowError, RecursionError) as exc:
        raise OwnedLaboratoryServiceError("invalid", "invalid owned laboratory inputs") from exc

    if data.history.sha256 != HISTORY_SHA256 or required_history_sha256 != data.history.sha256:
        raise OwnedLaboratoryServiceError("conflict", "loaded history does not match frozen source")
    lab = definition.to_reference_lab()
    votes = data.parity_votes() if lab.selection_kind == "parity" else None
    result = run_reference_lab(lab, data.history, data.rankings, parity_votes=votes)
    return OwnedLaboratoryExecution(
        snapshot=OwnedLaboratoryRunSnapshot(definition, data.history.sha256, RANKINGS_SHA256),
        result=result,
    )
