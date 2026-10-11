"""Immutable catalog for the fourteen archived reference laboratories."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

SelectionKind = Literal["ranking", "parity"]
StakeStyle = Literal["bold", "ladder", "flat"]


@dataclass(frozen=True, slots=True)
class ReferenceLab:
    lab_id: str
    system: str
    coverage: int
    stake_style: StakeStyle
    selection_kind: SelectionKind = "ranking"
    capital: int = 2000
    goal: int = 2800
    prizes: tuple[int, ...] = (80, 8, 4, 2, 1)
    window_start: str = "2025-09-02 05:10"
    window_end: str = "2026-09-25 18:20"


REFERENCE_LABS = (
    ReferenceLab("transicion_1_audaz", "transition", 1, "bold"),
    ReferenceLab("frios_1_audaz", "cold", 1, "bold"),
    ReferenceLab("selector_1_audaz", "select_interpretable", 1, "bold"),
    ReferenceLab("mezclas_1_audaz", "mix", 1, "bold"),
    ReferenceLab("ensemble_5_audaz", "ensemble", 5, "bold"),
    ReferenceLab("ensemble_10_audaz", "ensemble", 10, "bold"),
    ReferenceLab("ensemble_20_audaz", "ensemble", 20, "bold"),
    ReferenceLab("frios_25_escalera", "cold", 25, "ladder"),
    ReferenceLab("mezclas_50_audaz", "mix", 50, "bold"),
    ReferenceLab("transicion_50_audaz", "transition", 50, "bold"),
    ReferenceLab("paridad_50_audaz", "parity", 50, "bold", "parity"),
    ReferenceLab("frios_50_escalera", "cold", 50, "ladder"),
    ReferenceLab("paridad_50_escalera", "parity", 50, "ladder", "parity"),
    ReferenceLab("paridad_50_plana", "parity", 50, "flat", "parity"),
)

_BY_ID = MappingProxyType({lab.lab_id: lab for lab in REFERENCE_LABS})


def get_reference_lab(lab_id: str) -> ReferenceLab:
    """Return a catalog entry or raise ``ValueError`` for an unknown id."""
    try:
        return _BY_ID[lab_id]
    except KeyError:
        raise ValueError(f"unknown reference laboratory: {lab_id}") from None
