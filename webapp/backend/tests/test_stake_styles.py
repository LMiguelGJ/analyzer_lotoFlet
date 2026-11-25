"""Progression stake styles: martingale, paroli, dalembert, fibonacci and oscars_grind.

Every sequence below was computed by hand from the rule table in
``odd/tasks/estilos-de-apuesta.md``. ``b`` is the stake per played number; the draw stake is
``b x coverage``. A draw is "won" only when what it paid is greater than what it cost.

Draw rows (parity picks the even numbers, so number 0 is always played):
``W`` first prize on number 0, ``L`` nothing, ``P`` fifth prize on number 0 (pays 1 per unit),
``S`` second prize on number 0.
"""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.laboratories import LaboratoryConfig
from laboratorio.domain.reference_labs import REFERENCE_LABS, ReferenceLab
from laboratorio.engine.reference_labs import DeadlineReferenceTotals, run_reference_lab
from laboratorio.engine.stake_styles import make_progression
from laboratorio.settings import Settings

BASE = "http://localhost:8765"
ORIGIN = {"Origin": BASE, "Content-Type": "application/json"}
LEIDSA = "leidsa_quiniela"
NEW_STYLES = ("martingale", "paroli", "dalembert", "fibonacci", "oscars_grind")
LABELS = {
    "flat": "Plana",
    "ladder": "Escalera",
    "bold": "Audaz",
    "martingale": "Martingala",
    "paroli": "Paroli",
    "dalembert": "D'Alembert",
    "fibonacci": "Fibonacci",
    "oscars_grind": "Oscar's Grind",
}

ROWS = {
    "W": [0, 91, 92, 93, 94],
    "L": [1, 91, 92, 93, 94],
    "P": [91, 92, 93, 94, 0],
    "S": [91, 0, 92, 93, 94],
}
PRIZES = (80, 8, 4, 2, 1)
SMALL_PRIZES = (10, 3, 2, 1, 1)


def replay(draws, style, *, coverage=1, capital=100, goal=10_000, prizes=PRIZES, **changes):
    lab = ReferenceLab(
        "synthetic",
        "parity",
        coverage,
        style,
        "parity",
        capital,
        goal,
        prizes,
        **changes,
    )
    count = len(draws)
    labels = tuple(f"2025-10-{day + 1:02d} 05:10" for day in range(count))
    nums = np.asarray([ROWS[kind] for kind in draws], dtype=np.uint8)
    history = SimpleNamespace(labels=labels, nums=nums)
    rankings = SimpleNamespace(row_ids=np.arange(count, dtype=np.int64))
    return run_reference_lab(lab, history, rankings, parity_votes=np.zeros(count, dtype=np.int8))


def row(session):
    return (
        session.outcome,
        session.start_index,
        session.end_index,
        session.draws,
        session.final_balance,
        session.wagered,
        session.paid,
    )


def drive(style, draws, *, coverage=1, capital=100, prizes=PRIZES, goal=10_000):
    """Walk the stake object like the engine does; return (stakes per number, balance)."""
    progression = make_progression(style, coverage, prizes[0], goal)
    pay = {"W": prizes[0], "L": 0, "P": prizes[4], "S": prizes[1]}
    balance, stakes = capital, []
    for kind in draws:
        per_number = progression.bet(balance)
        stake = coverage * per_number
        paid = per_number * pay[kind]
        balance += paid - stake
        progression.settle(stake, paid)
        stakes.append(per_number)
    return stakes, balance


# (style, coverage, draws, prizes, stakes per number, final balance, wagered, paid)
SCENARIOS = [
    # martingale: lose doubles, win goes back to 1.
    ("martingale", 1, "WLLWLLWL", PRIZES, [1, 1, 2, 4, 1, 2, 4, 1], 804, 16, 720),
    # 'P' pays 4 on a stake of 8: not a win, so the stake keeps doubling.
    ("martingale", 2, "LLPWL", PRIZES, [1, 2, 4, 8, 1], 712, 32, 644),
    # paroli: win doubles, the third win in a row goes back to 1, a loss goes back to 1.
    ("paroli", 1, "WWWWLWL", PRIZES, [1, 2, 4, 1, 2, 1, 2], 807, 13, 720),
    ("paroli", 2, "WPWL", PRIZES, [1, 2, 1, 2], 250, 12, 162),
    # dalembert: lose +1, win -1 but never below 1. 'P' at c=1 pays exactly the stake: a loss.
    ("dalembert", 1, "LLWPWWL", PRIZES, [1, 2, 3, 2, 3, 2, 1], 728, 14, 642),
    ("dalembert", 1, "WWL", PRIZES, [1, 1, 1], 257, 3, 160),
    ("dalembert", 2, "LLWL", PRIZES, [1, 2, 3, 2], 324, 16, 240),
    # fibonacci: index over 1,1,2,3,5,8...; lose +1, win -2 but never below the first term.
    ("fibonacci", 1, "LLLLWLL", PRIZES, [1, 1, 2, 3, 5, 2, 3], 483, 17, 400),
    ("fibonacci", 1, "LWWL", PRIZES, [1, 1, 1, 1], 256, 4, 160),
    ("fibonacci", 2, "LLLWL", PRIZES, [1, 1, 2, 3, 1], 324, 16, 240),
    # oscars_grind c=5, P1=10: objective +5 per cycle, +5 per unit won on first prize.
    # Cycle: -5 -10 -15, win -> profit -10 (b = min(2, ceil(15/5)=3) = 2), win with b=2 ->
    # profit 0 (b = min(3, ceil(5/5)=1) = 1), win -> profit 5 = objective: new cycle, b = 1.
    ("oscars_grind", 5, "LLLWWWL", SMALL_PRIZES, [1, 1, 1, 1, 2, 1, 1], 100, 40, 40),
    # c=2, P1=6: -8 after four losses, win -> -4 (b = min(2, ceil(6/4)=2) = 2),
    # win with b=2 -> profit 4 >= objective 2: new cycle.
    ("oscars_grind", 2, "LLLLWWL", (6, 3, 2, 1, 1), [1, 1, 1, 1, 1, 2, 1], 102, 16, 18),
    # first prize 80 pays far more than the objective: every win closes the cycle at once.
    ("oscars_grind", 1, "LLWLW", PRIZES, [1, 1, 1, 1, 1], 100 - 2 + 79 - 1 + 79, 5, 160),
]
IDS = [f"{s[0]}-c{s[1]}-{s[2]}" for s in SCENARIOS]


@pytest.mark.parametrize(
    ("style", "coverage", "draws", "prizes", "stakes", "final", "wagered", "paid"),
    SCENARIOS,
    ids=IDS,
)
def test_stake_sequence_and_balance_match_the_hand_computation(
    style, coverage, draws, prizes, stakes, final, wagered, paid
):
    assert drive(style, draws, coverage=coverage, prizes=prizes) == (stakes, final)


@pytest.mark.parametrize(
    ("style", "coverage", "draws", "prizes", "stakes", "final", "wagered", "paid"),
    SCENARIOS,
    ids=IDS,
)
def test_engine_replays_the_same_sequence_as_one_open_session(
    style, coverage, draws, prizes, stakes, final, wagered, paid
):
    result = replay(draws, style, coverage=coverage, prizes=prizes)
    assert [row(s) for s in result.sessions] == [
        ("incomplete", 0, len(draws) - 1, len(draws), final, wagered, paid)
    ]
    assert result.totals.total_wagered == wagered
    assert result.totals.total_paid == paid
    assert result.totals.total_net == final - 100


def test_fibonacci_walks_the_classic_terms():
    stakes, _ = drive("fibonacci", "L" * 10, capital=10_000)
    assert stakes == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]


def test_paroli_only_resets_after_three_wins_in_a_row():
    stakes, _ = drive("paroli", "WWWWWWL")
    assert stakes == [1, 2, 4, 1, 2, 4, 1]


def test_oscars_grind_does_not_raise_after_a_loss():
    stakes, _ = drive("oscars_grind", "LLLLL", coverage=5, prizes=SMALL_PRIZES)
    assert stakes == [1] * 5


# ------------------------------------------------------------------- cap and ruin


def test_martingale_cap_stake_is_balance_over_coverage_then_ruin_at_zero():
    # balance 6: stakes 1, 2 and then 4 is cut to the 3 that remain; losing it leaves 0.
    result = replay("LLLLW", "martingale", capital=6)
    assert [row(s) for s in result.sessions] == [
        ("ruin", 0, 2, 3, 0, 6, 0),
        # next session restarts with capital 6 and b = 1: lose (5), then b = 2 and win.
        ("incomplete", 3, 4, 2, 5 - 2 + 160, 3, 160),
    ]


def test_capped_stake_can_still_win_and_the_progression_continues():
    result = replay("LLWL", "martingale", capital=6)
    # 1, 2, then 4 cut to 3 which wins 240; then b is back to 1.
    assert [row(s) for s in result.sessions] == [("incomplete", 0, 3, 4, 239, 7, 240)]


def test_coverage_two_cap_uses_integer_division():
    # balance 9, c=2: stakes 2, 4, then b=4 -> 9-6=3 // 2 = 1 per number = 2 pesos. Left 1 < 2.
    result = replay("LLL", "martingale", coverage=2, capital=9)
    assert [row(s) for s in result.sessions] == [("ruin", 0, 2, 3, 1, 8, 0)]


def test_coverage_two_ruin_when_the_balance_cannot_cover_every_number():
    # balance 7, c=2: stake 2 (5), stake 4 (1); 1 < 2 numbers: ruin after two draws.
    result = replay("LLL", "martingale", coverage=2, capital=7)
    assert row(result.sessions[0]) == ("ruin", 0, 1, 2, 1, 6, 0)


@pytest.mark.parametrize(
    ("style", "draws_until_ruin"),
    [("martingale", 3), ("paroli", 6), ("dalembert", 3), ("fibonacci", 4), ("oscars_grind", 6)],
)
def test_every_style_is_capped_and_ruins_at_zero(style, draws_until_ruin):
    # Capital 6, all losses: martingale 1+2+3(cut from 4), paroli 1x6, dalembert 1+2+3,
    # fibonacci 1+1+2+2(cut from 3), oscars_grind 1x6: always exactly 6 wagered.
    result = replay("L" * 6, style, capital=6)
    assert row(result.sessions[0]) == ("ruin", 0, draws_until_ruin - 1, draws_until_ruin, 0, 6, 0)


def test_fibonacci_cap_lowers_the_index_to_the_stake_actually_played():
    progression = make_progression("fibonacci", 1, 80, 10_000)
    for balance in (100, 99, 97, 94, 89):  # lose: terms 1, 1, 2, 3, 5
        progression.bet(balance)
        progression.settle(1, 0)
    assert progression.bet(4) == 3  # next term is 8 but only 4 fit: the largest term is 3
    progression.settle(3, 0)
    assert progression.bet(1000) == 5  # one step up from the term actually played


# ------------------------------------------------------------- goal and deadline


@pytest.mark.parametrize(
    ("style", "second_stake"),
    [("martingale", 2), ("paroli", 1), ("dalembert", 2), ("fibonacci", 1), ("oscars_grind", 1)],
)
def test_goal_still_ends_a_session_and_the_next_one_restarts_at_one(style, second_stake):
    # d1 wins 79 -> 179 >= 150 goal. The new session loses d2 (99), then plays d3 with the
    # stake the style dictates after one loss and wins it.
    result = replay("WLW", style, goal=150)
    assert [row(s) for s in result.sessions] == [
        ("goal", 0, 0, 1, 179, 1, 80),
        ("goal", 1, 2, 2, 99 + 79 * second_stake, 1 + second_stake, 80 * second_stake),
    ]


@pytest.mark.parametrize(
    ("style", "second_stake"),
    [("martingale", 2), ("paroli", 1), ("dalembert", 2), ("fibonacci", 1), ("oscars_grind", 1)],
)
def test_max_session_draws_still_cuts_sessions_as_timeouts(style, second_stake):
    final = 100 - 1 - second_stake
    result = replay("LLLL", style, max_session_draws=2)
    assert [row(s) for s in result.sessions] == [
        ("timeout", 0, 1, 2, final, 1 + second_stake, 0),
        ("timeout", 2, 3, 2, final, 1 + second_stake, 0),
    ]
    assert isinstance(result.totals, DeadlineReferenceTotals)
    assert result.totals.timeouts == 2


@pytest.mark.parametrize("style", NEW_STYLES)
def test_session_state_is_not_carried_over_between_sessions(style):
    # Both sessions are identical losing streaks cut by the deadline, so they must match.
    result = replay("LLLLLL", style, max_session_draws=3)
    first, second = result.sessions
    assert row(first)[3:] == row(second)[3:]


# --------------------------------------------------------------------- validation


@pytest.mark.parametrize("style", NEW_STYLES)
def test_config_accepts_the_new_styles_on_any_list(style):
    chance = {
        "schema_version": 1,
        "system": "cold",
        "coverage": 10,
        "stake_style": style,
        "capital": 2000,
        "goal": 2800,
        "prizes": [80, 8, 4, 2, 1],
        "window_start": "2025-09-02 05:10",
        "window_end": "2026-09-25 18:20",
    }
    assert LaboratoryConfig.from_mapping(chance).to_mapping()["stake_style"] == style
    leidsa = {
        **chance,
        "prizes": [60, 8, 4],
        "window_start": "2023-01-04 20:50",
        "window_end": "2026-11-16 20:50",
        "list_id": LEIDSA,
    }
    assert LaboratoryConfig.from_mapping(leidsa).stake_style == style


def _chance(style, **changes):
    return LaboratoryConfig.from_mapping(
        {
            "schema_version": 1,
            "system": "cold",
            "coverage": 10,
            "stake_style": style,
            "capital": 2000,
            "goal": 2800,
            "prizes": [80, 8, 4, 2, 1],
            "window_start": "2025-09-02 05:10",
            "window_end": "2026-09-25 18:20",
        }
        | changes
    )


def test_unknown_style_is_refused_in_spanish():
    with pytest.raises(ValueError, match="estilo de apuesta"):
        _chance("ruleta")


def test_first_prize_rule_stays_for_bold_and_ladder_only():
    for style in ("bold", "ladder"):
        with pytest.raises(ValueError, match="bold and ladder require"):
            _chance(style, prizes=[10, 8, 4, 2, 1])
    for style in ("martingale", "paroli", "dalembert", "fibonacci"):
        assert _chance(style, prizes=[10, 8, 4, 2, 1]).stake_style == style


@pytest.mark.parametrize("first_prize", [10, 9])
def test_oscars_grind_needs_a_first_prize_above_the_coverage(first_prize):
    with pytest.raises(ValueError, match="Oscar's Grind"):
        _chance("oscars_grind", prizes=[first_prize, 8, 4, 2, 1])
    assert _chance("oscars_grind", prizes=[11, 8, 4, 2, 1]).stake_style == "oscars_grind"


def test_reference_labs_keep_their_original_styles():
    assert {lab.stake_style for lab in REFERENCE_LABS} <= {"flat", "ladder", "bold"}


# ------------------------------------------------------------------------- API


LEIDSA_CONFIG = {
    "schema_version": 1,
    "system": "cold",
    "coverage": 10,
    "stake_style": "flat",
    "capital": 2000,
    "goal": 2800,
    "prizes": [60, 8, 4],
    "window_start": "2023-01-04 20:50",
    "window_end": "2026-11-16 20:50",
}


@pytest.fixture
def client(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    app = create_app(settings, catalog_loader=lambda _settings: lab_data)
    with TestClient(app, base_url=BASE, raise_server_exceptions=False) as http:
        yield http


def activate_leidsa(client):
    response = client.put("/api/v1/lists/active", json={"id": LEIDSA}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return client.get("/api/v1/runs/options").json()["history"]["sha256"]


@pytest.mark.parametrize("style", NEW_STYLES)
def test_api_creates_and_runs_a_leidsa_lab_with_each_new_style(client, style):
    sha = activate_leidsa(client)
    created = client.post(
        "/api/v1/laboratories",
        json={"name": f"estilo {style}", "config": {**LEIDSA_CONFIG, "stake_style": style}},
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    lab = created.json()
    assert lab["config"]["stake_style"] == style
    run = client.post(
        f"/api/v1/laboratories/{lab['id']}/runs",
        json={"required_history_sha256": sha},
        headers=ORIGIN,
    )
    assert run.status_code == 201, run.text
    body = run.json()
    assert body["snapshot"]["definition"]["config"]["stake_style"] == style
    totals = body["summary"]["totals"]
    assert totals["total_wagered"] > 0
    assert totals["total_paid"] >= 0
    assert totals["total_net"] == totals["total_paid"] - totals["total_wagered"]
    assert client.get(f"/api/v1/laboratories/{lab['id']}/runs/{body['id']}").json() == body


def test_api_refuses_an_unknown_style_with_a_spanish_422(client):
    activate_leidsa(client)
    before = client.get("/api/v1/laboratories").json()["total"]
    response = client.post(
        "/api/v1/laboratories",
        json={"name": "malo", "config": {**LEIDSA_CONFIG, "stake_style": "ruleta"}},
        headers=ORIGIN,
    )
    assert response.status_code == 422, response.text
    assert "estilo de apuesta" in response.json()["detail"]
    assert client.get("/api/v1/laboratories").json()["total"] == before


def test_api_refuses_oscars_grind_when_the_first_prize_does_not_beat_the_coverage(client):
    activate_leidsa(client)
    config = {
        **LEIDSA_CONFIG,
        "stake_style": "oscars_grind",
        "coverage": 40,
        "prizes": [30, 8, 4],
    }
    response = client.post(
        "/api/v1/laboratories", json={"name": "grind", "config": config}, headers=ORIGIN
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("list_id", [None, LEIDSA])
def test_options_list_the_stake_styles_with_spanish_labels(client, list_id):
    if list_id:
        activate_leidsa(client)
    options = client.get("/api/v1/laboratories/options").json()
    assert options["stake_styles"] == [{"id": k, "label": v} for k, v in LABELS.items()]
