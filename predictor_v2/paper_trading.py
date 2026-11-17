"""In-memory, auditable paper ledger with post-decision settlement only."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from .decision_policy import (
    PaperDecision,
    PaperPolicyConfig,
    build_risk_manager,
    decide_paper,
)
from .risk_manager import RiskManager


@dataclass
class PaperBet:
    sequence_index: int
    side: str
    point_probability: float
    stake: float
    decision_reason: str
    warnings: tuple[str, ...]
    capital_before: float
    outcome: str | None = None
    net_result: float | None = None
    capital_after: float | None = None
    settled: bool = False


@dataclass
class PaperLedger:
    bets: list[PaperBet] = field(default_factory=list)
    no_bet_count: int = 0
    no_bet_reasons: Counter[str] = field(default_factory=Counter)

    @property
    def settled_count(self) -> int:
        return sum(1 for bet in self.bets if bet.settled)

    @property
    def unsettled_count(self) -> int:
        return sum(1 for bet in self.bets if not bet.settled)

    @property
    def net_result(self) -> float:
        return sum(bet.net_result or 0.0 for bet in self.bets)

    @property
    def win_count(self) -> int:
        return sum(
            1 for bet in self.bets if bet.net_result is not None and bet.net_result > 0
        )

    @property
    def loss_count(self) -> int:
        return sum(
            1 for bet in self.bets if bet.net_result is not None and bet.net_result < 0
        )

    def summary(self, risk_manager: RiskManager) -> dict[str, object]:
        return {
            "bets": len(self.bets),
            "settled": self.settled_count,
            "unsettled": self.unsettled_count,
            "no_bet_count": self.no_bet_count,
            "wins": self.win_count,
            "losses": self.loss_count,
            "net_result": self.net_result,
            "capital": risk_manager.current_capital,
            "stop_reason": risk_manager.stopped_reason,
            "no_bet_reasons": dict(self.no_bet_reasons),
        }


class PaperTrader:
    """Paper-only trader; ``place`` cannot receive the target outcome."""

    def __init__(
        self,
        config: PaperPolicyConfig,
        risk_manager: RiskManager | None = None,
        *,
        data_available: bool = True,
        data_valid: bool = True,
        data_stale: bool = False,
        record_no_bets: bool = False,
    ) -> None:
        self.config = config
        self.risk_manager = (
            risk_manager if risk_manager is not None else build_risk_manager(config)
        )
        if self.risk_manager is None:
            # A safe manager is not fabricated.  Decisions will remain NO_BET.
            self._capital = 0.0
        else:
            self._capital = self.risk_manager.current_capital
        self.data_available = data_available
        self.data_valid = data_valid
        self.data_stale = data_stale
        self.record_no_bets = record_no_bets
        self.ledger = PaperLedger()
        self._pending: PaperBet | None = None
        self.last_decision: PaperDecision | None = None

    def place(
        self, sequence_index: int, side: str, point_probability: float
    ) -> PaperBet | None:
        """Make a decision before any outcome is supplied; no real execution occurs."""

        decision = decide_paper(
            side=side,
            point_probability=point_probability,
            config=self.config,
            risk_manager=self.risk_manager,
            data_available=self.data_available,
            data_stale=self.data_stale,
            data_valid=self.data_valid,
        )
        self.last_decision = decision
        if not decision.is_bet or decision.stake is None or self.risk_manager is None:
            self.ledger.no_bet_count += 1
            self.ledger.no_bet_reasons[decision.reason] += 1
            return None
        if self._pending is not None:
            raise RuntimeError("settle the pending paper bet before placing another")
        bet = PaperBet(
            sequence_index=sequence_index,
            side=side,
            point_probability=point_probability,
            stake=decision.stake,
            decision_reason=decision.reason,
            warnings=decision.warnings,
            capital_before=self.risk_manager.current_capital,
        )
        self.ledger.bets.append(bet)
        self._pending = bet
        return bet

    def settle(self, bet: PaperBet, outcome: str) -> PaperBet:
        """Settle only after the caller reveals the actual outcome."""

        if bet is not self._pending or bet.settled:
            raise ValueError("bet is not the current unsettled paper bet")
        if outcome not in {"PAR", "IMPAR"}:
            raise ValueError("outcome must be PAR or IMPAR")
        if self.risk_manager is None:
            raise RuntimeError("cannot settle without explicit risk configuration")
        net_result = bet.stake * 0.4 if outcome == bet.side else -bet.stake
        self.risk_manager.record_settlement(net_result, bet.stake)
        bet.outcome = outcome
        bet.net_result = net_result
        bet.capital_after = self.risk_manager.current_capital
        bet.settled = True
        self._pending = None
        return bet

    def simulate(
        self,
        predictions: Iterable[tuple[int, str, float, str]],
    ) -> PaperLedger:
        """Process ``(index, side, probability, revealed_outcome)`` chronologically."""

        for sequence_index, side, probability, outcome in predictions:
            bet = self.place(sequence_index, side, probability)
            if bet is not None:
                self.settle(bet, outcome)
            if self.risk_manager is not None and self.risk_manager.is_stopped:
                break
        return self.ledger
