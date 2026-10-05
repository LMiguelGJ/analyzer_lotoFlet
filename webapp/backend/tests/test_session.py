"""Session accounting, termination boundaries and the immutable reference oracle."""

import io
import json
from pathlib import Path

import numpy as np
import pytest

from laboratorio.domain.contracts import (
    BlendComponent,
    Conditions,
    Outcome,
    SelectorKind,
    SettlementMode,
    StakingStyle,
    Strategy,
)
from laboratorio.domain.selection import random_order
from laboratorio.domain.session import Draw, preflight_initial_stake, run_session
from laboratorio.engine.adapter import (
    DataError,
    History,
    LabData,
    Rankings,
    open_lab_data,
    session_draws,
)
from laboratorio.settings import Settings

FIXTURE = json.loads((Path(__file__).parent / "fixtures/reference_sessions.json").read_text())


def conditions(*, capital=200, goal=280, settlement="all", max_bets=None, max_minutes=None):
    return Conditions(
        start_draw="2025-01-01 05:10",
        capital=capital,
        goal=goal,
        settlement=SettlementMode(settlement),
        max_bets=max_bets,
        max_minutes=max_minutes,
        seed=17,
    )


def strategy(*, staking="flat", coverage=1, selector="system", **extra):
    system = extra.pop("system", "cold") if selector == "system" else None
    return Strategy(
        name="Example",
        selector=SelectorKind(selector),
        system=system,
        coverage=coverage,
        staking=StakingStyle(staking),
        **extra,
    )


def draw(label, results, order=tuple(range(7, 100)) + tuple(range(7))):
    from datetime import datetime

    epoch = datetime(1970, 1, 1)
    minute = int((datetime.strptime(label, "%Y-%m-%d %H:%M") - epoch).total_seconds() // 60)
    return Draw(label, minute, tuple(results), tuple(order) if order is not None else None)


def test_repeated_numbers_pay_each_position_or_only_best_per_number():
    """B-DOM-038: ALL/BEST settlement and immutable per-bet accounting."""
    rows = [draw("2025-01-01 05:10", (7, 7, 8, 7, 8))]
    all_result = run_session(
        conditions(capital=10, goal=100, settlement="all"), strategy(coverage=5), rows
    )
    best_result = run_session(
        conditions(capital=10, goal=100, settlement="best"), strategy(coverage=5), rows
    )
    assert (all_result.paid, best_result.paid) == (95, 84)
    assert (all_result.final_balance, best_result.final_balance) == (100, 89)
    assert all_result.outcome is Outcome.GOAL
    assert all_result.bets[0].numbers == (7, 8, 9, 10, 11)
    assert all_result.bets[0].results == (7, 7, 8, 7, 8)
    assert (
        all_result.bets[0].per_number,
        all_result.bets[0].wagered,
        all_result.bets[0].paid,
        all_result.bets[0].balance,
    ) == (1, 5, 95, 100)
    with pytest.raises((AttributeError, TypeError)):
        all_result.bets[0].balance = 0


@pytest.mark.parametrize("coverage", (20, 30, 40))
@pytest.mark.parametrize("staking,stake", (("flat", 1), ("ladder", 1), ("bold", 2)))
@pytest.mark.parametrize("mode,prize", (("all", 95), ("best", 84)))
def test_synthetic_coverage_accounting_with_repeated_numbers(coverage, staking, stake, mode, prize):
    """B-DOM-039: coverage, staking, and settlement modes reconcile exactly."""
    # Selected: 7, 8, then 20 onward; the other numbers cannot win this draw.
    selected = (7, 8, *range(20, 20 + coverage - 2))
    row = draw("2025-01-01 05:10", (7, 7, 8, 7, 8), selected)
    result = run_session(
        conditions(capital=200, goal=280, settlement=mode, max_bets=1),
        strategy(staking=staking, coverage=coverage),
        [row],
    )
    # Q80 prizes: all = 80+8+4+2+1; best = 80 for 7 and 4 for 8.
    cost = stake * coverage
    paid = stake * prize
    balance = 200 - cost + paid
    expected_outcome = Outcome.GOAL if balance >= 280 else Outcome.LIMIT
    assert result.bets_count == 1
    assert (result.wagered, result.paid, result.final_balance, result.outcome) == (
        cost,
        paid,
        balance,
        expected_outcome,
    )
    assert (
        result.bets[0].numbers,
        result.bets[0].results,
        result.bets[0].per_number,
        result.bets[0].wagered,
        result.bets[0].paid,
        result.bets[0].balance,
    ) == (selected, (7, 7, 8, 7, 8), stake, cost, paid, balance)


def test_initial_and_post_settlement_insolvency_do_not_overdraft():
    """B-DOM-040: insolvency never overdrafts and invalid ordering is rejected."""
    rows = [draw("2025-01-01 05:10", (0, 1, 2, 3, 4))]
    with pytest.raises(ValueError, match="afford"):
        run_session(conditions(capital=4), strategy(coverage=5), rows)
    result = run_session(conditions(capital=5), strategy(coverage=5), rows)
    assert (result.outcome, result.bets_count, result.final_balance) == (Outcome.RUIN, 1, 0)
    assert result.wagered == 5 and result.paid == 0
    with pytest.raises(ValueError, match="afford"):
        run_session(conditions(capital=4), strategy(coverage=5, staking="bold"), rows)
    with pytest.raises(ValueError, match="ordering"):
        run_session(
            conditions(capital=5),
            strategy(coverage=5),
            [draw("2025-01-01 05:10", (0, 1, 2, 3, 4), (7, 8))],
        )


@pytest.mark.parametrize("staking", ("flat", "ladder", "bold"))
@pytest.mark.parametrize("coverage", (5, 50))
def test_preflight_rejects_unfunded_first_bet_and_accepts_exact_boundary(staking, coverage):
    """B-DOM-041: initial-stake preflight enforces exact funding boundaries."""
    selected = strategy(staking=staking, coverage=coverage)
    with pytest.raises(ValueError, match="initial capital cannot afford"):
        preflight_initial_stake(conditions(capital=coverage - 1), selected)
    with pytest.raises(ValueError, match="initial capital cannot afford"):
        run_session(conditions(capital=coverage - 1), selected, ())

    opts = conditions(capital=coverage)
    assert preflight_initial_stake(opts, selected) == 1
    result = run_session(opts, selected, [draw(opts.start_draw, (0, 1, 2, 3, 4))])
    assert result.bets[0].per_number == 1
    assert result.bets[0].wagered == coverage


def test_preflight_bold_stake_matches_first_executed_wager():
    """B-DOM-042: bold preflight equals the actual first stake."""
    opts = conditions(capital=2000, goal=2800)
    selected = strategy(staking="bold", coverage=50)
    stake = preflight_initial_stake(opts, selected)
    result = run_session(opts, selected, [draw(opts.start_draw, (0, 1, 2, 3, 4))])
    assert stake == result.bets[0].per_number == 27


def test_ladder_uses_coverage_recovery_rounds_and_resets_on_first_hit():
    """B-DOM-043: ladder recovery depends on coverage and resets on first hit."""
    rows = [
        draw("2025-01-01 05:10", (0, 1, 2, 3, 4)),
        draw("2025-01-01 05:15", (0, 1, 2, 3, 4)),
        draw("2025-01-01 05:20", (7, 1, 2, 3, 4)),
        draw("2025-01-01 05:25", (0, 1, 2, 3, 4)),
    ]
    result = run_session(
        conditions(capital=1000, goal=2000, max_bets=4),
        strategy(staking="ladder", coverage=10),
        rows,
    )
    assert [bet.per_number for bet in result.bets] == [1, 1, 1, 1]
    assert result.outcome is Outcome.LIMIT
    # Coverage 50 recovers with 1, 2, 6; first-position win resets to round zero.
    result = run_session(
        conditions(capital=2000, goal=10000, max_bets=4),
        strategy(staking="ladder", coverage=50),
        rows,
    )
    assert [bet.per_number for bet in result.bets] == [1, 2, 6, 1]
    assert result.outcome is Outcome.LIMIT


def test_settlement_precedes_goal_and_limit_and_goal_is_final_balance():
    """B-DOM-044: settlement runs before goal/limit checks; goal is final balance."""
    result = run_session(
        conditions(capital=10, goal=89, max_bets=1),
        strategy(),
        [draw("2025-01-01 05:10", (7, 0, 0, 0, 0))],
    )
    assert (result.outcome, result.final_balance, result.bets_count) == (Outcome.GOAL, 89, 1)


def test_gaps_consume_time_and_deadline_equality_excludes_draw():
    """B-DOM-045: unranked gaps consume time and deadline equality excludes a draw."""
    rows = [
        draw("2025-01-01 05:10", (0, 1, 2, 3, 4)),
        draw("2025-01-01 05:15", (7, 1, 2, 3, 4), None),
        draw("2025-01-01 05:20", (7, 1, 2, 3, 4)),
    ]
    result = run_session(conditions(max_minutes=10), strategy(), rows)
    assert result.outcome is Outcome.LIMIT
    assert result.bets_count == 1 and result.paid == 0
    assert result.bets[0].label == "2025-01-01 05:10"


def test_first_limit_wins_and_history_exhaustion_is_separate():
    """B-DOM-046: limits stop sessions; history exhaustion remains distinct."""
    rows = [
        draw("2025-01-01 05:10", (0, 1, 2, 3, 4)),
        draw("2025-01-01 05:15", (0, 1, 2, 3, 4)),
        draw("2025-01-01 05:20", (0, 1, 2, 3, 4)),
    ]
    bets_limit = run_session(conditions(max_bets=1, max_minutes=20), strategy(), rows)
    clock_limit = run_session(conditions(max_bets=3, max_minutes=10), strategy(), rows)
    exhaustion = run_session(conditions(), strategy(), rows)
    assert (bets_limit.outcome, bets_limit.bets_count) == (Outcome.LIMIT, 1)
    assert (clock_limit.outcome, clock_limit.bets_count) == (Outcome.LIMIT, 2)
    assert (exhaustion.outcome, exhaustion.bets_count) == (Outcome.HISTORY_EXHAUSTED, 3)


def test_ruin_precedes_simultaneous_bet_limit_after_settlement():
    """B-DOM-047: post-settlement ruin wins over a simultaneous bet limit."""
    result = run_session(
        conditions(capital=1, max_bets=1), strategy(), [draw("2025-01-01 05:10", (0, 1, 2, 3, 4))]
    )
    assert result.outcome is Outcome.RUIN


def test_bold_integer_stake_is_goal_gap_over_first_prize_net_and_capped():
    """B-DOM-048: bold stake covers the goal gap and respects caps."""
    result = run_session(
        conditions(capital=2000, goal=2800, max_bets=1),
        strategy(staking="bold", coverage=50),
        [draw("2025-01-01 05:10", (0, 1, 2, 3, 4), tuple(range(50)))],
    )
    assert (result.bets[0].per_number, result.wagered) == (27, 1350)


def test_adapter_routes_selectors_and_preserves_unranked_clock(data_dir):
    """B-DOM-049: adapter routes selectors while retaining unranked clock rows."""
    labels = ("2025-01-01 05:10", "2025-01-01 05:15", "2025-01-01 05:20")
    minutes = np.array([draw(label, (0, 1, 2, 3, 4)).minute for label in labels])
    history = History(labels, np.array([[7, 0, 0, 0, 0]] * 3, dtype=np.uint8), minutes, "test")
    source = io.BytesIO()
    np.savez(
        source,
        ranking100__cold=np.tile(np.arange(100, dtype=np.uint8), (2, 1)),
        ranking100__transition=np.tile(np.arange(99, -1, -1, dtype=np.uint8), (2, 1)),
    )
    rankings = Rankings(
        np.array([0, 2], dtype=np.int64), data_dir / "never-open.npz", source.getvalue()
    )
    data = LabData(history, rankings, Settings.from_environment())
    data._cache["parity"] = np.array([1, 0, 1], dtype=np.int8)
    opts = conditions(max_minutes=11)
    for selector, extra, expected in (
        ("system", {}, (0, 1, 2, 3, 4)),
        (
            "blend",
            {
                "components": (
                    BlendComponent(system="cold", weight=50),
                    BlendComponent(system="transition", weight=50),
                )
            },
            (0, 1, 2, 3, 4),
        ),
        ("random", {}, tuple(int(n) for n in random_order(17, labels[0])[:5])),
        ("parity", {}, (1, 3, 5, 7, 9)),
    ):
        coverage = 50 if selector == "parity" else 5
        strat = (
            strategy(selector=selector, coverage=coverage, components=extra["components"])
            if selector == "blend"
            else strategy(selector=selector, coverage=coverage)
        )
        rows = list(session_draws(data, strat, opts))
        assert rows[0].order is not None
        assert rows[0].order[:5] == expected
        assert rows[1].order is None
        assert rows[2].order is not None
    with pytest.raises(DataError, match="no ranking"):
        list(
            session_draws(
                data, strategy(coverage=5), opts.model_copy(update={"start_draw": labels[1]})
            )
        )


@pytest.mark.parametrize("coverage", (20, 30, 40))
@pytest.mark.parametrize("selector", ("blend", "random"))
@pytest.mark.parametrize("mode,prize", (("all", 95), ("best", 84)))
def test_adapter_blend_and_random_accounting_at_wider_coverages(
    data_dir, coverage, selector, mode, prize
):
    """B-DOM-050: blend/random adapter accounting supports wider coverages."""
    label = "2025-01-01 05:10"
    ranked = (7, 8, *range(20, 100), *range(7), *range(9, 20))
    if selector == "random":
        ranked = tuple(int(n) for n in random_order(17, label))
    first, second = ranked[:2]
    results = (first, first, second, first, second)
    history = History(
        (label,),
        np.array([results], dtype=np.uint8),
        np.array([draw(label, results).minute]),
        "test",
    )
    source = io.BytesIO()
    # Blend components agree on the top 40; this tests adapter wiring, not blend scoring.
    blend_ranking = np.array([(7, 8, *range(20, 100), *range(7), *range(9, 20))], dtype=np.uint8)
    np.savez(source, ranking100__cold=blend_ranking, ranking100__transition=blend_ranking)
    rankings = Rankings(
        np.array([0], dtype=np.int64), data_dir / "never-open.npz", source.getvalue()
    )
    data = LabData(history, rankings, Settings.from_environment())
    strat = (
        strategy(
            selector="blend",
            coverage=coverage,
            components=(
                BlendComponent(system="cold", weight=50),
                BlendComponent(system="transition", weight=50),
            ),
        )
        if selector == "blend"
        else strategy(selector="random", coverage=coverage)
    )
    opts = conditions(capital=200, goal=280, max_bets=1, settlement=mode)
    rows = list(session_draws(data, strat, opts))
    assert len(rows) == 1
    assert rows[0].order == ranked[:coverage]
    assert rows[0].results == results
    result = run_session(opts, strat, rows)
    # Positions 1/2/4 repeat first; positions 3/5 repeat second.
    cost = coverage
    balance = 200 - cost + prize
    assert (result.bets_count, result.wagered, result.paid, result.final_balance) == (
        1,
        cost,
        prize,
        balance,
    )
    assert result.outcome is Outcome.LIMIT
    assert (
        result.bets[0].numbers,
        result.bets[0].per_number,
        result.bets[0].wagered,
        result.bets[0].paid,
        result.bets[0].balance,
    ) == (ranked[:coverage], 1, cost, prize, balance)


@pytest.mark.real_data
def test_all_frozen_reference_sessions(data_dir):
    """B-DOM-051: legacy engine matches every frozen real-data reference session."""
    data = open_lab_data(Settings.from_environment())
    assert len(FIXTURE["cases"]) == 141
    assert len(FIXTURE["cases"]) == len(
        {(case["system"], case["k"], case["staking"], case["mode"]) for case in FIXTURE["cases"]}
    )
    for case in FIXTURE["cases"]:
        strat = strategy(
            staking=case["staking"],
            coverage=case["k"],
            selector="parity" if case["system"] == "parity" else "system",
            **({"system": case["system"]} if case["system"] != "parity" else {}),
        )
        for expected in case["sessions"]:
            opts = Conditions(
                start_draw=expected["start"],
                capital=2000,
                goal=2800,
                settlement=SettlementMode(case["mode"]),
                seed=17,
            )
            actual = run_session(opts, strat, session_draws(data, strat, opts))
            expected_outcome = (
                "history_exhausted" if expected["outcome"] == "open" else expected["outcome"]
            )
            assert (
                actual.bets_count,
                actual.final_balance,
                actual.wagered,
                actual.paid,
                actual.outcome.value,
            ) == (
                expected["bets"],
                expected["final"],
                expected["wagered"],
                expected["paid"],
                expected_outcome,
            ), (case, expected)
