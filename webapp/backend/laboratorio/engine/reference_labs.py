"""Isolated historical replay for the archived reference-laboratory contracts."""

import json
from dataclasses import dataclass
from hashlib import sha256

import numpy as np

from laboratorio.domain.laboratories import LaboratoryConfig
from laboratorio.domain.reference_labs import ReferenceLab


@dataclass(frozen=True, slots=True)
class ReferenceSession:
    outcome: str
    start_index: int
    end_index: int
    draws: int
    final_balance: int
    wagered: int
    paid: int


@dataclass(frozen=True, slots=True)
class ReferenceTotals:
    completed: int
    incomplete: int
    goals: int
    ruins: int
    sessions_total: int
    total_wagered: int
    total_paid: int
    total_net: int
    total_steps: int
    mean_net_closed: float | None


@dataclass(frozen=True, slots=True)
class ReferenceResult:
    lab_id: str
    sessions: tuple[ReferenceSession, ...]
    totals: ReferenceTotals
    eligible_draws: int
    gaps: int
    first: str | None
    last: str | None
    session_sha256: str


def _ladder(coverage: int, first_prize: int) -> tuple[int, ...]:
    """Reference first-prize recovery ladder; ceiling division per round."""
    gain_per_number = first_prize - coverage
    if gain_per_number <= 0:
        raise ValueError("first prize must exceed coverage for ladder recovery")
    stakes = []
    invested = 0
    for _ in range(10):
        stake = max(1, (invested + 10 + gain_per_number - 1) // gain_per_number)
        stakes.append(stake)
        invested += coverage * stake
    return tuple(stakes)


def _bet_per_number(
    style: str,
    coverage: int,
    first_prize: int,
    balance: int,
    round_index: int,
    goal: int,
    ladder: tuple[int, ...],
) -> int:
    if style == "flat":
        return 1
    if style == "ladder":
        return ladder[round_index]
    return min(
        (goal - balance + first_prize - coverage - 1) // (first_prize - coverage),
        balance // coverage,
    )


def _selected_payments(
    results: np.ndarray, orders: np.ndarray, coverage: int, prizes: tuple[int, ...]
) -> tuple[np.ndarray, np.ndarray]:
    chosen = orders[:, :coverage]
    payments = np.zeros(len(results), dtype=np.int64)
    for position, prize in enumerate(prizes):
        payments += (chosen == results[:, position, None]).any(axis=1) * prize
    first_hits = (chosen == results[:, 0, None]).any(axis=1)
    return payments, first_hits


def run_reference_lab(
    lab: ReferenceLab, history, rankings, *, parity_votes=None
) -> ReferenceResult:
    """Replay a frozen lab from adapter-shaped history and ranking records.

    ``history`` supplies labels and ``nums``; ``rankings`` supplies aligned
    ``row_ids`` and ``family(system)``. Parity labs require causal votes supplied
    by the caller, preserving the adapter's cached parity implementation.
    """
    if type(lab.system) is not str:
        raise ValueError("system is not supported by the archived reference family")
    # The isolated engine also supports parity fixtures with partial coverage;
    # user-created domain configs separately enforce all-50 parity selection.
    config = LaboratoryConfig(
        system="cold" if lab.system == "parity" else lab.system,
        coverage=lab.coverage,
        stake_style=lab.stake_style,
        capital=lab.capital,
        goal=lab.goal,
        prizes=lab.prizes,
        window_start=lab.window_start,
        window_end=lab.window_end,
    )
    expected_selection = "parity" if lab.system == "parity" else config.selection_kind
    if lab.selection_kind != expected_selection:
        raise ValueError("selection kind does not match the laboratory system")
    labels = history.labels
    row_ids = np.asarray(rankings.row_ids, dtype=np.int64)
    timestamps = np.asarray(labels, dtype=str)
    inside = np.asarray(
        [lab.window_start <= label <= lab.window_end for label in labels], dtype=bool
    )
    eligible = row_ids[inside[row_ids]]
    if lab.selection_kind == "parity":
        if parity_votes is None:
            raise ValueError("parity laboratory requires one causal vote per history draw")
        votes = np.asarray(parity_votes)
        if votes.shape != (len(labels),) or not np.all((votes == 0) | (votes == 1)):
            raise ValueError("parity votes must be one binary value per history draw")
        orders = np.where(
            votes[eligible, None] == 0,
            np.arange(0, 100, 2, dtype=np.uint8)[None, :],
            np.arange(1, 100, 2, dtype=np.uint8)[None, :],
        )
    else:
        family = rankings.family(lab.system)
        ranking_positions = {int(row_id): position for position, row_id in enumerate(row_ids)}
        positions = np.asarray([ranking_positions[int(index)] for index in eligible], dtype=np.intp)
        orders = family[positions]

    payments, first_hits = _selected_payments(
        np.asarray(history.nums)[eligible], orders, lab.coverage, lab.prizes
    )
    first_prize = lab.prizes[0]
    ladder = _ladder(lab.coverage, first_prize) if lab.stake_style == "ladder" else ()
    sessions: list[ReferenceSession] = []
    balance, round_index = lab.capital, 0
    start = 0
    draws = wagered = paid = 0
    outcomes = zip(payments.tolist(), first_hits.tolist(), strict=True)
    for index, (payment, first_hit) in enumerate(outcomes):
        per_number = _bet_per_number(
            lab.stake_style,
            lab.coverage,
            first_prize,
            balance,
            round_index,
            lab.goal,
            ladder,
        )
        stake = lab.coverage * per_number
        if balance < stake:
            if draws:
                sessions.append(
                    ReferenceSession("ruin", start, index - 1, draws, balance, wagered, paid)
                )
            balance, round_index = lab.capital, 0
            start = index
            draws = wagered = paid = 0
            per_number = _bet_per_number(
                lab.stake_style,
                lab.coverage,
                first_prize,
                balance,
                round_index,
                lab.goal,
                ladder,
            )
            stake = lab.coverage * per_number
            if balance < stake:
                raise ValueError("initial stake is unaffordable")
        winnings = per_number * payment
        balance += winnings - stake
        draws += 1
        wagered += stake
        paid += winnings
        if lab.stake_style == "ladder":
            round_index = 0 if first_hit else (round_index + 1) % len(ladder)
        outcome = "goal" if balance >= lab.goal else None
        if outcome is None:
            next_per_number = _bet_per_number(
                lab.stake_style,
                lab.coverage,
                first_prize,
                balance,
                round_index,
                lab.goal,
                ladder,
            )
            if balance < lab.coverage or balance < lab.coverage * next_per_number:
                outcome = "ruin"
        if outcome is not None:
            sessions.append(ReferenceSession(outcome, start, index, draws, balance, wagered, paid))
            balance, round_index = lab.capital, 0
            start = index + 1
            draws = wagered = paid = 0
    if draws:
        sessions.append(
            ReferenceSession("incomplete", start, len(eligible) - 1, draws, balance, wagered, paid)
        )

    complete = [session for session in sessions if session.outcome in ("goal", "ruin")]
    wagered_total = sum(session.wagered for session in sessions)
    paid_total = sum(session.paid for session in sessions)
    net_closed = sum(session.final_balance - lab.capital for session in complete)
    totals = ReferenceTotals(
        completed=len(complete),
        incomplete=sum(session.outcome == "incomplete" for session in sessions),
        goals=sum(session.outcome == "goal" for session in complete),
        ruins=sum(session.outcome == "ruin" for session in complete),
        sessions_total=len(sessions),
        total_wagered=wagered_total,
        total_paid=paid_total,
        total_net=sum(session.final_balance - lab.capital for session in sessions),
        total_steps=sum(session.draws for session in sessions),
        mean_net_closed=(net_closed / len(complete) if complete else None),
    )
    digest_payload = [
        (s.outcome, s.start_index, s.end_index, s.draws, s.final_balance, s.wagered, s.paid)
        for s in sessions
    ]
    digest = sha256(json.dumps(digest_payload, separators=(",", ":")).encode()).hexdigest()
    first = timestamps[eligible[0]].item() if len(eligible) else None
    last = timestamps[eligible[-1]].item() if len(eligible) else None
    gaps = int(eligible[-1] - eligible[0] + 1 - len(eligible)) if len(eligible) else 0
    return ReferenceResult(
        lab.lab_id, tuple(sessions), totals, len(eligible), gaps, first, last, digest
    )
