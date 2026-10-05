from datetime import datetime, timedelta

import pytest

from laboratorio.domain.backtest import BacktestConfig, run_backtest
from laboratorio.domain.contracts import StakingStyle
from laboratorio.domain.session import Draw


def draw(minute, results=(90, 91, 92, 93, 94), order=tuple(range(100))):
    label = (datetime(2025, 1, 1) + timedelta(minutes=minute)).strftime("%Y-%m-%d %H:%M")
    return Draw(label, minute, results, order)


def config(*, coverage=1, staking="flat", capital=10, goal=20, prizes=(80, 8, 4, 2, 1)):
    return BacktestConfig(
        capital=capital,
        goal=goal,
        numbers=100,
        positions=5,
        prizes=prizes,
        minimum_stake=1,
        coverage=coverage,
        staking=StakingStyle(staking),
    )


def test_goal_and_quiebre_are_completed_and_next_session_starts_next_ranked_row():
    rows = [
        draw(10, (0, 9, 8, 7, 6)),  # bold 1: stake 1; first prize reaches goal
        draw(11, (9, 8, 7, 6, 5)),  # next session starts here, not at row 10
    ]
    result = run_backtest(config(staking="bold", capital=1, goal=20), rows)
    assert (result.reached_goal, result.quiebre, result.completed, result.incomplete) == (
        1,
        1,
        2,
        0,
    )
    assert result.sessions[0].bets[0].label == rows[0].label
    assert result.sessions[1].bets[0].label == rows[1].label


def test_unranked_gaps_carry_balance_and_incomplete_tail_is_excluded_from_completed_rates():
    rows = [
        draw(10, (9, 8, 7, 6, 5)),
        draw(11, (0, 9, 8, 7, 6), None),
        draw(12, (9, 8, 7, 6, 5)),
    ]
    result = run_backtest(config(capital=100, goal=1000), rows)
    assert (result.completed, result.incomplete, result.goal_rate, result.neto_medio) == (
        0,
        1,
        0.0,
        0.0,
    )
    assert result.sessions[0].final_balance == 98
    assert result.window.bets == 2
    assert result.sessions[-1].bets[0].label == rows[0].label


def test_ladder_amounts_and_first_prize_reset_secondary_does_not_reset():
    rows = [
        draw(10),  # lose 1
        draw(11),  # lose 2
        draw(12, (0, 90, 91, 92, 93)),  # win first, stake 6 and reset
        draw(13),  # stake 1
        draw(14, (90, 0, 91, 92, 93)),  # secondary hit, still advances
        draw(15),  # stake 2
    ]
    result = run_backtest(config(coverage=50, staking="ladder", capital=2000, goal=9000), rows)
    assert [bet.per_number for bet in result.sessions[0].bets] == [1, 2, 6, 1, 2, 6]
    assert result.sessions[0].bets[4].paid > 0


def test_ladder_cycle_and_full_next_round_quiebre():
    rows = [draw(i) for i in range(10, 22)]
    cycled = run_backtest(
        config(coverage=50, staking="ladder", capital=10_000_000, goal=20_000_000), rows
    )
    amounts = [bet.per_number for bet in cycled.sessions[0].bets]
    assert amounts[:5] == [1, 2, 6, 16, 42]
    assert amounts[10:] == [1, 2]
    broken = run_backtest(config(coverage=50, staking="ladder", capital=200, goal=9000), rows)
    assert broken.sessions[0].bets[-1].per_number == 2
    assert broken.sessions[0].outcome == "quiebre"


def test_bold_stakes_match_reference_examples():
    one = run_backtest(
        config(coverage=1, staking="bold", capital=2000, goal=2800),
        [draw(10, (0, 9, 8, 7, 6))],
    )
    fifty = run_backtest(
        config(coverage=50, staking="bold", capital=2000, goal=2800),
        [draw(10, (0, 90, 91, 92, 93))],
    )
    assert (one.sessions[0].bets[0].per_number, one.sessions[0].bets[0].balance) == (11, 2869)
    assert (fifty.sessions[0].bets[0].per_number, fifty.sessions[0].bets[0].wagered) == (27, 1350)
    assert fifty.sessions[0].bets[0].balance == 2810


@pytest.mark.golden
@pytest.mark.real_data
def test_golden_transition_one_bold():
    from laboratorio.domain.contracts import Conditions, SelectorKind, SettlementMode, Strategy
    from laboratorio.engine.adapter import open_lab_data, session_draws
    from laboratorio.settings import Settings

    data = open_lab_data(Settings.from_environment())
    strategy = Strategy(
        name="golden",
        selector=SelectorKind.SYSTEM,
        system="transition",
        coverage=1,
        staking=StakingStyle.BOLD,
    )
    start = data.history.labels[int(data.rankings.row_ids[0])]
    conditions = Conditions(
        start_draw=start, capital=2000, goal=2800, settlement=SettlementMode.ALL, seed=17
    )
    rows = session_draws(data, strategy, conditions)
    result = run_backtest(config(coverage=1, staking="bold", capital=2000, goal=2800), rows)
    assert (result.reached_goal, result.completed, result.goal_rate, result.quiebre) == (
        681,
        963,
        70.7,
        282,
    )
    assert result.neto_medio == 10.3


@pytest.mark.golden
@pytest.mark.real_data
def test_golden_parity_fifty_flat():
    from laboratorio.domain.contracts import Conditions, SelectorKind, SettlementMode, Strategy
    from laboratorio.engine.adapter import open_lab_data, session_draws
    from laboratorio.settings import Settings

    data = open_lab_data(Settings.from_environment())
    strategy = Strategy(
        name="golden",
        selector=SelectorKind.PARITY,
        coverage=50,
        staking=StakingStyle.FLAT,
    )
    start = data.history.labels[int(data.rankings.row_ids[0])]
    conditions = Conditions(
        start_draw=start, capital=2000, goal=2800, settlement=SettlementMode.ALL, seed=17
    )
    rows = session_draws(data, strategy, conditions)
    result = run_backtest(config(coverage=50, staking="flat", capital=2000, goal=2800), rows)
    assert (result.reached_goal, result.completed, result.goal_rate, result.quiebre) == (
        13,
        91,
        14.3,
        78,
    )
    assert result.neto_medio == -1572.8
