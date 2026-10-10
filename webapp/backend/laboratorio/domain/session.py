"""Draw and bet rows shared by the backtest."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Draw:
    label: str
    minute: int
    results: tuple[int, int, int, int, int]
    order: tuple[int, ...] | None


@dataclass(frozen=True, slots=True)
class Bet:
    label: str
    numbers: tuple[int, ...]
    per_number: int
    wagered: int
    results: tuple[int, int, int, int, int]
    paid: int
    balance: int
