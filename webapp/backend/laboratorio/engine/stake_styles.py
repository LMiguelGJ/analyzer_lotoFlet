"""Progression stake styles for laboratories: one small state machine per session.

``b`` is the stake on every played number; the draw stake is ``b x coverage``. A draw is "won"
only when what it paid is strictly greater than what it cost. The stake actually placed is
``min(b, max_stake_per_number, balance // coverage)`` (the middle bound only when the laboratory
sets one); when that is 0 the session is a ruin. When a cap binds, the progression state is
lowered to the stake that was really placed, so ``b`` never outgrows the balance or the bank cap.
Flat, ladder and bold are not progressions and keep their original engine path.
"""

from abc import ABC, abstractmethod
from bisect import bisect_right

PROGRESSION_STYLES = ("martingale", "paroli", "dalembert", "fibonacci", "oscars_grind")
_PAROLI_WINS = 3


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


class _Progression(ABC):
    """Common shape: ``bet`` places the next stake, ``settle`` learns the draw outcome."""

    def __init__(self, coverage: int, max_stake: int | None = None):
        self.coverage = coverage
        self.max_stake = max_stake
        self.b = 1

    def _affordable(self, balance: int) -> int:
        """Largest stake per number allowed by the balance and the optional bank cap."""
        cap = balance // self.coverage
        return cap if self.max_stake is None else min(cap, self.max_stake)

    def bet(self, balance: int) -> int:
        per_number = min(self.b, self._affordable(balance))
        self.b = per_number
        return per_number

    @abstractmethod
    def settle(self, wagered: int, paid: int) -> None:
        """Update the state from what the draw cost and what it paid."""


class _Martingale(_Progression):
    def settle(self, wagered, paid):
        self.b = 1 if paid > wagered else self.b * 2


class _Paroli(_Progression):
    def __init__(self, coverage, max_stake=None):
        super().__init__(coverage, max_stake)
        self.streak = 0

    def settle(self, wagered, paid):
        if paid <= wagered:
            self.b, self.streak = 1, 0
            return
        self.streak += 1
        if self.streak >= _PAROLI_WINS:
            self.b, self.streak = 1, 0
        else:
            self.b *= 2


class _DAlembert(_Progression):
    def settle(self, wagered, paid):
        self.b = max(1, self.b - 1) if paid > wagered else self.b + 1


class _Fibonacci(_Progression):
    """Index ``i`` over the terms 1, 1, 2, 3, 5, 8...: lose ``i + 1``, win ``max(0, i - 2)``."""

    def __init__(self, coverage, max_stake=None):
        super().__init__(coverage, max_stake)
        self.terms = [1, 1]
        self.index = 0

    def _term(self, index: int) -> int:
        while len(self.terms) <= index:
            self.terms.append(self.terms[-1] + self.terms[-2])
        return self.terms[index]

    def bet(self, balance):
        cap = self._affordable(balance)
        if self._term(self.index) > cap and cap > 0:
            # Largest index whose term fits: the state follows the stake really placed.
            while self.terms[-1] <= cap:
                self._term(len(self.terms))
            self.index = bisect_right(self.terms, cap) - 1
        return min(self._term(self.index), cap)

    def settle(self, wagered, paid):
        self.index = max(0, self.index - 2) if paid > wagered else self.index + 1


class _OscarsGrind(_Progression):
    """A cycle aims at ``+coverage``; a loss keeps ``b``; a win raises it only as far as needed."""

    def __init__(self, coverage, first_prize, max_stake=None):
        super().__init__(coverage, max_stake)
        self.gain_per_number = first_prize - coverage
        self.profit = 0

    def settle(self, wagered, paid):
        self.profit += paid - wagered
        if paid <= wagered:
            return
        objective = self.coverage
        if self.profit >= objective:
            self.b, self.profit = 1, 0
            return
        needed = max(1, _ceil_div(objective - self.profit, self.gain_per_number))
        self.b = min(self.b + 1, needed)


def make_progression(
    style: str, coverage: int, first_prize: int, goal: int, max_stake: int | None = None
) -> _Progression:
    """Fresh state for one session. ``goal`` is part of the engine contract of every style.

    ``max_stake`` is the optional bank cap on the stake per number (``None`` = no cap).
    """
    del goal  # progressions never size a stake from the goal (bold does)
    if style == "martingale":
        return _Martingale(coverage, max_stake)
    if style == "paroli":
        return _Paroli(coverage, max_stake)
    if style == "dalembert":
        return _DAlembert(coverage, max_stake)
    if style == "fibonacci":
        return _Fibonacci(coverage, max_stake)
    if style == "oscars_grind":
        if first_prize <= coverage:
            raise ValueError("Oscar's Grind necesita un primer premio mayor que la cobertura.")
        return _OscarsGrind(coverage, first_prize, max_stake)
    raise ValueError(f"{style} is not a progression stake style")
