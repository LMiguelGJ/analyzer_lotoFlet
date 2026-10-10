"""Behavior and characterization tests for the consecutive-session run engine."""

import random
import time
from dataclasses import replace

import pytest

from laboratorio.domain.backtest import BacktestConfig, run_backtest
from laboratorio.domain.contracts import StakingStyle
from laboratorio.domain.runs import (
    MAX_COVERAGE,
    MAX_POSITIONS,
    NUMBERS,
    OUTCOME_GOAL,
    OUTCOME_INCOMPLETE,
    OUTCOME_LIMIT,
    OUTCOME_RUIN,
    RunConfig,
    RunResult,
    _ratio,
    run_sessions,
)
from laboratorio.domain.session import Bet, Draw

HIT = (7, 50, 51, 52, 53)
MISS = (90, 50, 51, 52, 53)
ORDER = (7, 8)


def config(**overrides):
    values = {
        "capital": 10,
        "goal": 20,
        "coverage": 2,
        "positions": 1,
        "prizes": (5,),
        "minimum_stake": 1,
    }
    values.update(overrides)
    return RunConfig(**values)


def row(index, results=MISS, order=ORDER):
    return Draw(f"d{index}", index, results, order)


def rows_from(results_list, order=ORDER):
    return [row(i, results, order) for i, results in enumerate(results_list)]


# --------------------------------------------------------------------------- constants


def test_constants():
    assert (OUTCOME_GOAL, OUTCOME_RUIN, OUTCOME_LIMIT, OUTCOME_INCOMPLETE) == (
        "goal",
        "ruin",
        "limit",
        "incomplete",
    )
    assert (NUMBERS, MAX_POSITIONS, MAX_COVERAGE) == (100, 5, 50)


# --------------------------------------------------------------------------- validation


def test_valid_config_builds():
    built = config(max_draws=3)
    assert built.max_draws == 3


@pytest.mark.parametrize(
    "overrides",
    [
        {"capital": 0, "goal": 5},
        {"goal": 10},
        {"goal": 9},
        {"coverage": 0},
        {"coverage": 51, "capital": 1000, "goal": 2000},
        {"positions": 0, "prizes": ()},
        {"positions": 6, "prizes": (1, 1, 1, 1, 1, 1)},
        {"positions": 2, "prizes": (5,)},
        {"prizes": (0,)},
        {"prizes": (-3,)},
        {"minimum_stake": 0},
        {"capital": 3, "goal": 10, "minimum_stake": 2},
        {"capital": 9, "goal": 20, "minimum_stake": 5},
        {"max_draws": 0},
        {"max_draws": -1},
    ],
)
def test_invalid_config_rejected(overrides):
    with pytest.raises(ValueError):
        config(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"capital": True},
        {"goal": True, "capital": 0},
        {"coverage": True, "capital": 5},
        {"positions": True, "prizes": (5,)},
        {"prizes": (True,)},
        {"minimum_stake": True},
        {"max_draws": True},
        {"capital": 10.0},
        {"coverage": 2.0},
        {"max_draws": 3.0},
    ],
)
def test_non_int_config_rejected(overrides):
    with pytest.raises(ValueError):
        config(**overrides)


def test_affordable_first_bet_boundary():
    assert config(capital=6, goal=7, coverage=3, minimum_stake=2).capital == 6
    with pytest.raises(ValueError):
        config(capital=5, goal=7, coverage=3, minimum_stake=2)


# --------------------------------------------------------------------------- outcomes


def test_goal_session():
    result = run_sessions(config(), rows_from([HIT] * 4))
    (session,) = result.sessions
    assert session.outcome == OUTCOME_GOAL
    assert (session.ordinal, session.start_index, session.end_index) == (1, 0, 3)
    assert session.draws == 4
    assert session.final_balance == 22
    assert (session.wagered, session.paid) == (8, 20)
    assert [bet.balance for bet in session.bets] == [13, 16, 19, 22]
    assert result.totals.goal == 1
    assert result.draws == result.ranked_draws == 4


def test_bet_fields():
    result = run_sessions(config(), rows_from([HIT]))
    (bet,) = result.sessions[0].bets
    assert bet == Bet("d0", (7, 8), 1, 2, (7,), 5, 13)


def test_ruin_when_next_bet_unaffordable():
    result = run_sessions(config(capital=5, goal=100), rows_from([MISS, MISS]))
    session = result.sessions[0]
    assert session.outcome == OUTCOME_RUIN
    assert session.draws == 2
    assert session.final_balance == 1
    assert [bet.balance for bet in session.bets] == [3, 1]


def test_exactly_affordable_next_bet_keeps_playing():
    result = run_sessions(config(capital=4, goal=100), rows_from([MISS, MISS]))
    session = result.sessions[0]
    assert [bet.balance for bet in session.bets] == [2, 0]
    assert session.outcome == OUTCOME_RUIN
    # balance 2 after the first miss equals the cost of the next bet: still playable.
    assert session.draws == 2


def test_limit_session():
    result = run_sessions(config(goal=100, max_draws=3), rows_from([MISS] * 5))
    first = result.sessions[0]
    assert first.outcome == OUTCOME_LIMIT
    assert first.draws == 3
    assert first.final_balance == 4
    assert result.sessions[1].start_index == 3


def test_limit_counts_unranked_draws():
    rows = [row(0), row(1, order=None), row(2, order=None), row(3)]
    result = run_sessions(config(goal=100, max_draws=3), rows)
    first = result.sessions[0]
    assert first.outcome == OUTCOME_LIMIT
    assert (first.start_index, first.end_index, first.draws) == (0, 2, 3)
    assert len(first.bets) == 1
    assert first.final_balance == 8


def test_limit_closing_on_unranked_row_after_bet():
    # Limit is only reachable on an unranked row here, so the check applies to it too.
    rows = [row(0, HIT), row(1, order=None)]
    result = run_sessions(config(goal=100, max_draws=2), rows)
    assert result.sessions[0].outcome == OUTCOME_LIMIT
    assert result.sessions[0].end_index == 1


def test_goal_beats_limit_on_same_draw():
    result = run_sessions(config(goal=13, max_draws=1), rows_from([HIT]))
    assert result.sessions[0].outcome == OUTCOME_GOAL


def test_ruin_beats_limit_on_same_draw():
    result = run_sessions(config(capital=3, goal=100, max_draws=1), rows_from([MISS]))
    assert result.sessions[0].outcome == OUTCOME_RUIN


def test_no_limit_means_sessions_run_until_rows_end():
    result = run_sessions(config(goal=1000), rows_from([MISS, HIT] * 3))
    (session,) = result.sessions
    assert session.outcome == OUTCOME_INCOMPLETE


# --------------------------------------------------------------------------- chaining


def test_restart_with_fresh_capital_and_chained_ordinals():
    rows = rows_from([MISS] * 5)
    result = run_sessions(config(capital=5, goal=100), rows)
    assert [s.ordinal for s in result.sessions] == [1, 2, 3]
    assert [s.outcome for s in result.sessions] == [OUTCOME_RUIN, OUTCOME_RUIN, OUTCOME_INCOMPLETE]
    assert [(s.start_index, s.end_index) for s in result.sessions] == [(0, 1), (2, 3), (4, 4)]
    # Every session begins from the initial capital again.
    assert [s.bets[0].balance for s in result.sessions] == [3, 3, 3]
    assert [s.final_balance for s in result.sessions] == [1, 1, 3]


def test_leading_unranked_rows_belong_to_no_session():
    rows = [row(0, order=None), row(1, order=None), row(2), row(3)]
    result = run_sessions(config(capital=5, goal=100), rows)
    first = result.sessions[0]
    assert first.start_index == 2
    assert first.draws == 2
    assert result.draws == 4
    assert result.ranked_draws == 2


def test_unranked_rows_between_sessions_are_skipped():
    rows = [row(0), row(1), row(2, order=None), row(3, order=None), row(4), row(5)]
    result = run_sessions(config(capital=5, goal=100), rows)
    first, second = result.sessions
    assert (first.outcome, first.start_index, first.end_index) == (OUTCOME_RUIN, 0, 1)
    assert (second.start_index, second.end_index, second.draws) == (4, 5, 2)
    assert second.outcome == OUTCOME_RUIN


def test_unranked_rows_inside_session_count_as_elapsed_but_do_not_bet():
    rows = [row(0), row(1, order=None), row(2)]
    result = run_sessions(config(capital=5, goal=100), rows)
    (session,) = result.sessions
    assert session.outcome == OUTCOME_RUIN
    assert session.draws == 3
    assert len(session.bets) == 2
    assert (session.start_index, session.end_index) == (0, 2)


def test_incomplete_tail_has_a_bet_and_stops_the_chain():
    result = run_sessions(config(goal=100), rows_from([MISS, HIT]))
    (session,) = result.sessions
    assert session.outcome == OUTCOME_INCOMPLETE
    assert len(session.bets) == 2
    assert result.totals.incomplete == 1
    assert result.totals.mean_net_closed is None


def test_trailing_unranked_rows_do_not_open_a_session():
    rows = [row(0, HIT), row(1, HIT), row(2, order=None)]
    result = run_sessions(config(goal=100), rows)
    (session,) = result.sessions
    assert session.outcome == OUTCOME_INCOMPLETE
    assert session.draws == 3


def test_no_ranked_rows_gives_no_sessions():
    result = run_sessions(config(), [row(0, order=None), row(1, order=None)])
    assert result.sessions == ()
    totals = result.totals
    assert (totals.sessions, totals.bets, totals.wagered, totals.paid, totals.net) == (0,) * 5
    assert totals.return_pct is None
    assert totals.mean_net_closed is None
    assert (result.draws, result.ranked_draws) == (2, 0)


def test_empty_rows():
    result = run_sessions(config(), [])
    assert result == RunResult(sessions=(), totals=result.totals, draws=0, ranked_draws=0)
    assert result.totals.sessions == 0


# --------------------------------------------------------------------------- payouts


def test_three_positions_hand_computed_with_repeated_number():
    cfg = RunConfig(
        capital=100,
        goal=1000,
        coverage=3,
        positions=3,
        prizes=(60, 10, 5),
        minimum_stake=2,
    )
    # Order picks 9, 4, 11. Results: 9 first and third (pays twice), 4 second, 50 uncovered;
    # the fifth result (11) is covered but lies beyond the three positions in play.
    draw = Draw("x", 0, (9, 4, 9, 50, 11), (9, 4, 11, 30))
    result = run_sessions(cfg, [draw])
    (session,) = result.sessions
    (bet,) = session.bets
    assert bet.numbers == (9, 4, 11)
    assert bet.per_number == 2
    assert bet.wagered == 6
    assert bet.results == (9, 4, 9)
    assert bet.paid == 2 * 60 + 2 * 10 + 2 * 5 == 150
    assert bet.balance == 100 + 150 - 6 == 244
    assert session.outcome == OUTCOME_INCOMPLETE


def test_positions_use_only_the_first_results():
    cfg = config(positions=1, prizes=(5,))
    # Only the first result counts: the covered 7 sits in the second slot.
    draw = Draw("x", 0, (90, 7, 7, 7, 7), ORDER)
    (bet,) = run_sessions(cfg, [draw]).sessions[0].bets
    assert bet.paid == 0
    assert bet.results == (90,)


def test_prize_by_position_not_by_number():
    cfg = config(positions=2, prizes=(50, 3))
    draw = Draw("x", 0, (90, 7, 7, 7, 7), ORDER)
    (bet,) = run_sessions(cfg, [draw]).sessions[0].bets
    assert bet.paid == 3


# --------------------------------------------------------------------------- totals


def test_totals_hand_computed():
    result = run_sessions(config(capital=5, goal=100), rows_from([MISS] * 5))
    totals = result.totals
    assert totals.sessions == 3
    assert (totals.goal, totals.ruin, totals.limit, totals.incomplete) == (0, 2, 0, 1)
    assert totals.bets == 5
    assert totals.wagered == 10
    assert totals.paid == 0
    assert totals.net == -10
    assert totals.return_pct == -100.0
    assert totals.mean_net_closed == -4.0


def test_return_pct_rounding():
    # hit (+5), miss, miss: wagered 6 (3 bets x 2), paid 5.
    cfg = config(goal=1000)
    result = run_sessions(cfg, rows_from([HIT, MISS, MISS]))
    assert result.totals.wagered == 6
    assert result.totals.paid == 5
    assert result.totals.net == -1
    assert result.totals.return_pct == -16.7


def test_ratio_rounds_half_up_away_from_zero():
    assert _ratio(1, 4) == 0.3
    assert _ratio(-1, 4) == -0.3
    assert _ratio(1, 3) == 0.3
    assert _ratio(7, 2) == 3.5
    assert _ratio(-1572, 1) == -1572.0


def test_mean_net_closed_excludes_incomplete_tail():
    # Ruin (net -4), goal (net +6), then an incomplete tail that is ignored by the mean.
    rows = rows_from([MISS, MISS, HIT, HIT, MISS])
    result = run_sessions(config(capital=5, goal=11), rows)
    assert [s.outcome for s in result.sessions] == [OUTCOME_RUIN, OUTCOME_GOAL, OUTCOME_INCOMPLETE]
    assert result.totals.mean_net_closed == 1.0


def _random_rows(seed, count, unranked_share, coverage=50):
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        results = tuple(rng.randrange(100) for _ in range(5))
        order = None if rng.random() < unranked_share else tuple(rng.sample(range(100), coverage))
        rows.append(Draw(f"r{index}", index, results, order))
    return rows


def test_totals_reconcile():
    rows = _random_rows(7, 500, 0.3)
    cfg = RunConfig(
        capital=60,
        goal=90,
        coverage=10,
        positions=5,
        prizes=(80, 8, 4, 2, 1),
        minimum_stake=1,
        max_draws=8,
    )
    result = run_sessions(cfg, rows)
    totals = result.totals
    assert totals.sessions == len(result.sessions) > 3
    assert totals.sessions == totals.goal + totals.ruin + totals.limit + totals.incomplete
    assert sum(s.paid - s.wagered for s in result.sessions) == totals.net
    assert sum(s.wagered for s in result.sessions) == totals.wagered
    assert sum(s.paid for s in result.sessions) == totals.paid
    assert sum(len(s.bets) for s in result.sessions) == totals.bets
    for session in result.sessions:
        assert session.wagered == sum(bet.wagered for bet in session.bets)
        assert session.paid == sum(bet.paid for bet in session.bets)
        assert session.final_balance == cfg.capital + session.paid - session.wagered
        assert session.draws == session.end_index - session.start_index + 1
    ordinals = [s.ordinal for s in result.sessions]
    assert ordinals == list(range(1, len(ordinals) + 1))
    for earlier, later in zip(result.sessions, result.sessions[1:], strict=False):
        assert later.start_index > earlier.end_index
    assert {s.outcome for s in result.sessions} >= {OUTCOME_LIMIT}


def test_determinism():
    rows = _random_rows(11, 300, 0.3)
    cfg = RunConfig(
        capital=50,
        goal=80,
        coverage=10,
        positions=3,
        prizes=(60, 10, 5),
        minimum_stake=1,
        max_draws=25,
    )
    assert run_sessions(cfg, rows) == run_sessions(cfg, list(rows))


def test_accepts_any_iterable_of_rows():
    rows = rows_from([HIT] * 4)
    assert run_sessions(config(), iter(rows)) == run_sessions(config(), rows)


# --------------------------------------------------------------------------- invalid rows


@pytest.mark.parametrize(
    "bad",
    [
        "not a draw",
        Draw("a", 0, (1, 2, 3, 4), ORDER),
        Draw("a", 0, (1, 2, 3, 4, 100), ORDER),
        Draw("a", 0, (1, 2, 3, 4, -1), ORDER),
        Draw("a", 0, (1, 2, 3, 4, True), ORDER),
        Draw("a", 0, (1, 2, 3, 4, 5), (7,)),
        Draw("a", 0, (1, 2, 3, 4, 5), (7, 7)),
        Draw("a", 0, (1, 2, 3, 4, 5), (7, 100)),
        Draw("a", 0, (1, 2, 3, 4, 5), (7, -1)),
        Draw("a", 0, (1, 2, 3, 4, 5), (7, True)),
    ],
)
def test_invalid_rows_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        run_sessions(config(), [bad])


def test_non_chronological_rows_rejected():
    with pytest.raises(ValueError):
        run_sessions(config(), [row(1), row(1)])
    with pytest.raises(ValueError):
        run_sessions(config(), [row(2), row(1)])


def test_config_type_enforced():
    with pytest.raises(TypeError):
        run_sessions("config", [])  # type: ignore[arg-type]


# --------------------------------------------------------------------------- performance


def test_large_input_is_fast():
    rng = random.Random(5)
    base = tuple(range(10))
    rows = []
    for index in range(65_000):
        results = tuple(rng.randrange(100) for _ in range(5))
        rows.append(Draw("p", index, results, base))
    cfg = RunConfig(
        capital=100, goal=200, coverage=10, positions=5, prizes=(80, 8, 4, 2, 1), minimum_stake=1
    )
    started = time.perf_counter()
    result = run_sessions(cfg, rows)
    assert time.perf_counter() - started < 3.0
    assert result.totals.sessions > 0


# --------------------------------------------------------------------------- characterization

OLD_OUTCOMES = {
    "reached_goal": OUTCOME_GOAL,
    "quiebre": OUTCOME_RUIN,
    "incomplete": OUTCOME_INCOMPLETE,
}


@pytest.mark.parametrize(
    ("coverage", "capital", "goal"),
    [(50, 200, 400), (10, 30, 60), (25, 100, 180), (1, 5, 12)],
)
def test_matches_old_flat_engine_on_synthetic_rows(coverage, capital, goal):
    rng = random.Random(1234)
    rows = []
    for index in range(600):
        results = tuple(rng.randrange(100) for _ in range(5))
        order = None if rng.random() < 0.3 else tuple(rng.sample(range(100), 50))
        rows.append(Draw(f"s{index}", index, results, order))

    prizes = (80, 8, 4, 2, 1)
    old = run_backtest(
        BacktestConfig(
            capital=capital,
            goal=goal,
            numbers=100,
            positions=5,
            prizes=prizes,
            minimum_stake=1,
            coverage=coverage,
            staking=StakingStyle.FLAT,
        ),
        rows,
    )
    new = run_sessions(
        RunConfig(
            capital=capital,
            goal=goal,
            coverage=coverage,
            positions=5,
            prizes=prizes,
            minimum_stake=1,
        ),
        rows,
    )

    assert len(new.sessions) == len(old.sessions) > 1
    for old_session, new_session in zip(old.sessions, new.sessions, strict=True):
        assert new_session.outcome == OLD_OUTCOMES[old_session.outcome]
        assert new_session.final_balance == old_session.final_balance
        assert len(new_session.bets) == len(old_session.bets)
        for old_bet, new_bet in zip(old_session.bets, new_session.bets, strict=True):
            assert new_bet.label == old_bet.label
            assert new_bet.numbers == old_bet.numbers
            assert new_bet.paid == old_bet.paid
            assert new_bet.balance == old_bet.balance
            assert new_bet.wagered == old_bet.wagered
            assert new_bet.per_number == old_bet.per_number
    assert new.totals.bets == old.window.bets
    assert new.totals.wagered == old.window.wagered
    assert new.totals.paid == old.window.paid
    assert new.totals.goal == old.reached_goal
    assert new.totals.ruin == old.quiebre
    assert new.totals.incomplete == old.incomplete


@pytest.mark.real_data
@pytest.mark.golden
def test_real_history_parity_flat_golden(tmp_path):
    from laboratorio.api.backtests import _selection_rows
    from laboratorio.engine.adapter import open_lab_data
    from laboratorio.settings import Settings

    data = open_lab_data(replace(Settings.from_environment(), data_dir=tmp_path))
    rows = _selection_rows(data, "parity", None, 50)
    result = run_sessions(
        RunConfig(
            capital=2000,
            goal=2800,
            coverage=50,
            positions=5,
            prizes=(80, 8, 4, 2, 1),
            minimum_stake=1,
        ),
        rows,
    )
    totals = result.totals
    assert totals.goal == 13
    assert totals.goal + totals.ruin == 91
    assert totals.ruin == 78
    assert totals.mean_net_closed == -1572.8
    assert round(100 * totals.goal / (totals.goal + totals.ruin), 1) == 14.3
