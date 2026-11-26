"""Stake rules v2 (``stake_rules: 2``): ladder tied to the goal and progressions that reset only
when the cycle is recovered. Rules 1 (absent) must behave exactly as before.

Every scenario was computed by hand. Draw rows (parity picks the even numbers, so number 0 is
always played): ``W`` first prize on number 0, ``L`` nothing, ``S`` second prize on number 0.
``c`` is the coverage, ``b`` the stake per number (the draw stake is ``b x c``).
"""

from dataclasses import asdict, replace
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.laboratories import LaboratoryConfig, LaboratoryDefinition
from laboratorio.domain.reference_labs import REFERENCE_LABS, ReferenceLab
from laboratorio.engine.reference_labs import run_reference_lab
from laboratorio.settings import Settings

BASE = "http://localhost:8765"
ORIGIN = {"Origin": BASE, "Content-Type": "application/json"}
LEIDSA = "leidsa_quiniela"
MESSAGE = "Las reglas de apuesta deben ser 1 (las de siempre) o 2 (corregidas)."

CHANCE_CONFIG = {
    "schema_version": 1,
    "system": "cold",
    "coverage": 10,
    "stake_style": "ladder",
    "capital": 2000,
    "goal": 2800,
    "prizes": [80, 8, 4, 2, 1],
    "window_start": "2025-09-02 05:10",
    "window_end": "2026-09-25 18:20",
}
LEIDSA_CONFIG = {
    **CHANCE_CONFIG,
    "prizes": [60, 8, 4],
    "window_start": "2023-01-04 20:50",
    "window_end": "2026-11-16 20:50",
}
ROWS = {
    "W": [0, 91, 92, 93, 94],
    "L": [1, 91, 92, 93, 94],
    "S": [91, 0, 92, 93, 94],
}
PRIZES = (80, 8, 4, 2, 1)
SMALL = (10, 3, 2, 1, 1)  # c=1: ladder gain per number 9
FOUR = (20, 3, 2, 1, 1)  # c=4: gain 16 and a second prize (3) below the cost (4)


def replay(draws, style, *, coverage=1, capital=100, goal=10_000, prizes=PRIZES, **changes):
    lab = ReferenceLab(
        "synthetic", "parity", coverage, style, "parity", capital, goal, prizes, **changes
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


def rows(result):
    return [row(s) for s in result.sessions]


# ------------------------------------------------------------------------ config


def test_absent_stake_rules_keeps_the_exact_mapping():
    config = LaboratoryConfig.from_mapping(CHANCE_CONFIG)
    assert config.stake_rules == 1
    assert config.to_mapping() == CHANCE_CONFIG
    assert "stake_rules" not in config.to_mapping()


def test_explicit_rules_one_is_the_same_as_absent():
    config = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "stake_rules": 1})
    assert config.stake_rules == 1
    assert config == LaboratoryConfig.from_mapping(CHANCE_CONFIG)
    assert config.to_mapping() == CHANCE_CONFIG


def test_rules_two_round_trips():
    config = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "stake_rules": 2})
    assert config.stake_rules == 2
    assert config.to_mapping() == {**CHANCE_CONFIG, "stake_rules": 2}
    assert LaboratoryConfig.from_mapping(config.to_mapping()) == config


def test_rules_two_round_trips_with_the_other_optional_fields():
    raw = {
        **LEIDSA_CONFIG,
        "list_id": LEIDSA,
        "max_session_draws": 30,
        "max_stake_per_number": 500,
        "stake_rules": 2,
    }
    assert LaboratoryConfig.from_mapping(raw).to_mapping() == raw


@pytest.mark.parametrize("value", [0, 3, -1, True, False, 2.0, "2", None, [2]])
def test_other_values_are_refused_in_spanish(value):
    with pytest.raises(ValueError) as caught:
        LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "stake_rules": value})
    assert str(caught.value) == MESSAGE


def test_the_adapter_carries_the_rules_and_the_chance_labs_stay_on_rules_one():
    identity = "6f1b0c1e-0b5c-4b57-9a54-0d9c7d6f4a11"
    v2 = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "stake_rules": 2})
    assert LaboratoryDefinition(identity, "x", v2).to_reference_lab().stake_rules == 2
    v1 = LaboratoryConfig.from_mapping(CHANCE_CONFIG)
    assert LaboratoryDefinition(identity, "x", v1).to_reference_lab().stake_rules == 1
    assert all(lab.stake_rules == 1 for lab in REFERENCE_LABS)


def test_rules_two_accepts_a_ladder_whose_goal_target_exceeds_the_capital():
    # c=10, goal 100000: the v2 first stake (ceil(9990/50) per number) is cut to the balance.
    raw = {**CHANCE_CONFIG, "capital": 100, "goal": 100_000}
    assert LaboratoryConfig.from_mapping(raw).stake_rules == 1
    assert LaboratoryConfig.from_mapping({**raw, "stake_rules": 2}).stake_rules == 2


# ------------------------------------------------------------------------ ladder v2


def test_ladder_target_comes_from_the_goal():
    # c=1, capital 100, goal 1000 -> target ceil(900/10) = 90; gain 9.
    # Draw 1: ceil(90/9) = 10 per number (loses 10). Draw 2: ceil(100/9) = 12, wins 120:
    # cycle net 98 >= 90 closes it. Draw 3 starts a new cycle at 10 again.
    result = replay("LWL", "ladder", prizes=SMALL, goal=1000, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 2, 3, 188, 32, 120)]


def test_ladder_with_a_small_goal_keeps_the_old_first_steps():
    # goal 200 -> target 10: the first ten stakes equal the historical ladder 2,2,2,2,2,3,3,3,4,4.
    result = replay("L" * 10, "ladder", prizes=SMALL, goal=200, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 9, 10, 73, 27, 0)]
    old = replay("L" * 10, "ladder", prizes=SMALL, goal=200)
    assert rows(old) == rows(result)


def test_ladder_does_not_wrap_around_after_ten_misses():
    # Stakes continue 5, 5 after the tenth miss (invested 27 -> ceil(37/9) = 5, 32 -> 5).
    result = replay("L" * 12, "ladder", prizes=SMALL, goal=200, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 11, 12, 63, 37, 0)]
    # Rules 1 wraps back to 2, 2 (31 wagered): that silent reset is the defect being fixed.
    old = replay("L" * 12, "ladder", prizes=SMALL, goal=200)
    assert rows(old) == [("incomplete", 0, 11, 12, 69, 31, 0)]


def test_ladder_keeps_growing_far_beyond_the_old_ten_steps():
    result = replay("L" * 14, "ladder", prizes=SMALL, goal=200, stake_rules=2)
    # Steps 11-14: 5, 5, 6, 6 on top of the 27 wagered in the first ten.
    assert result.sessions[0].wagered == 27 + 5 + 5 + 6 + 6


def test_ladder_recovers_everything_invested_when_the_first_prize_hits():
    # After twelve misses 37 are invested: ceil(47/9) = 6 pays 60 (net +17 >= 10): cycle closed,
    # so the fourteenth draw is back at 2.
    result = replay("L" * 12 + "WL", "ladder", prizes=SMALL, goal=200, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 13, 14, 115, 45, 60)]


def test_ladder_second_prize_reduces_what_is_invested():
    # c=4, P=(20,3,...): target 10, gain 16. Stakes 1, 1, 2 lose 4, 4, 8 (invested 16); the
    # fourth draw (ceil(26/16) = 2) pays 3 x 2 = 6 of the second prize: invested 18, so the
    # fifth stake is ceil(28/16) = 2 (without the reduction it would be ceil(34/16) = 3).
    result = replay("LLLSL", "ladder", coverage=4, prizes=FOUR, goal=200, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 4, 5, 74, 32, 6)]


def test_ladder_stake_is_cut_to_the_balance_and_ruins_only_at_zero_per_number():
    # capital 21, c=4, goal 200 -> target 18. Stakes: ceil(18/16) = 2 (8), 2 (8), then ceil(34/16)
    # = 3 would cost 12 but only 5 are left: 1 per number is placed (balance 1 < 4: ruin).
    result = replay("LLL", "ladder", coverage=4, capital=21, prizes=FOUR, goal=200, stake_rules=2)
    assert rows(result) == [("ruin", 0, 2, 3, 1, 20, 0)]


def test_ladder_does_not_ruin_while_the_balance_still_covers_one_per_number():
    # capital 20: after two draws 4 remain (>= c): the session is NOT over; the third is played.
    result = replay("LL", "ladder", coverage=4, capital=20, prizes=FOUR, goal=200, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 1, 2, 4, 16, 0)]
    result = replay("LLL", "ladder", coverage=4, capital=20, prizes=FOUR, goal=200, stake_rules=2)
    assert rows(result) == [("ruin", 0, 2, 3, 0, 20, 0)]


def test_ladder_cycle_follows_the_stake_really_placed_when_the_balance_cuts_it():
    # capital 21 as above; the third draw places 1 and wins 20 (first prize): invested 0 < target
    # 18, so the cycle stays open and the fourth stake is ceil(18/16) = 2 again.
    result = replay("LLWL", "ladder", coverage=4, capital=21, prizes=FOUR, goal=200, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 3, 4, 13, 28, 20)]


def test_ladder_is_capped_by_the_bank_cap_and_the_cycle_follows_the_placed_stake():
    # cap 3: steps 2,2,2,2,2,3,3,3,4,4,5 are placed as 2,2,2,2,2,3,3,3,3,3,3 (wagered 28).
    result = replay(
        "L" * 11, "ladder", prizes=SMALL, goal=200, max_stake_per_number=3, stake_rules=2
    )
    assert rows(result) == [("incomplete", 0, 10, 11, 72, 28, 0)]
    # Invested is 28 (what was really placed). The first-prize draw wants ceil(38/9) = 5 but
    # places 3 (+30): the cycle is not recovered (net -1), so the next stake is ceil(11/9) = 2.
    result = replay(
        "L" * 11 + "WL",
        "ladder",
        prizes=SMALL,
        goal=200,
        max_stake_per_number=3,
        stake_rules=2,
    )
    assert rows(result) == [("incomplete", 0, 12, 13, 97, 33, 30)]


def test_ladder_never_places_more_than_cap_per_number():
    result = replay(
        "L" * 40,
        "ladder",
        prizes=SMALL,
        goal=2000,
        capital=1000,
        max_stake_per_number=4,
        stake_rules=2,
    )
    assert result.sessions[0].wagered <= 4 * 40


def test_ladder_v1_is_unchanged_by_the_feature():
    for draws in ("LLLLLLLLLLLLWL", "LWLLLW", "LLLSLL"):
        plain = replay(draws, "ladder", prizes=SMALL, goal=200)
        explicit = replay(draws, "ladder", prizes=SMALL, goal=200, stake_rules=1)
        assert asdict(plain) == asdict(explicit)


# ------------------------------------------------------------------------ progressions v2


def test_martingale_second_prize_that_does_not_recover_keeps_doubling():
    # c=6: stakes 1, 2, 4 (the second prize pays 32 on 24: net -6-12-24+32 = -10 < 0 is not a
    # win), so the fourth stake doubles to 8 instead of going back to 1.
    result = replay("LLSL", "martingale", coverage=6, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 3, 4, 42, 90, 32)]
    # Rules 1 counted that partial prize as a win and went back to 1.
    old = replay("LLSL", "martingale", coverage=6)
    assert rows(old) == [("incomplete", 0, 3, 4, 84, 48, 32)]


def test_martingale_full_recovery_resets():
    result = replay("LLSWL", "martingale", coverage=6, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 4, 5, 676, 96, 672)]


def test_martingale_partial_prizes_that_add_up_to_the_cycle_reset():
    # net -6, then -2 (b=2 pays 16 on 12), then +6 (b=4 pays 32 on 24): recovered, back to 1.
    result = replay("LSSL", "martingale", coverage=6, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 3, 4, 100, 48, 48)]


def test_a_first_draw_that_only_pays_what_it_cost_is_not_a_win():
    # Same strictness as rules 1: paid == wagered at the start of a cycle keeps doubling.
    result = replay("SL", "martingale", coverage=8, stake_rules=2)  # second prize 8 pays 8 on 8
    assert rows(result) == [("incomplete", 0, 1, 2, 84, 24, 8)]


def test_fibonacci_partial_prize_steps_as_a_loss():
    # c=6 terms 1,1,2,3: the second prize at b=2 leaves the cycle at -8, so the index goes
    # forward (b=3), not back by two (rules 1 would place 1).
    result = replay("LLSL", "fibonacci", coverage=6, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 3, 4, 74, 42, 16)]
    old = replay("LLSL", "fibonacci", coverage=6)
    assert rows(old) == [("incomplete", 0, 3, 4, 86, 30, 16)]


def test_fibonacci_full_recovery_steps_back():
    # Terms 1,1,2,3: stakes 1,1,2,3 and the first prize at b=3 recovers the cycle, so the index
    # goes back two (to the second 1): the fifth stake is 1.
    result = replay("LLLWL", "fibonacci", coverage=6, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 4, 5, 292, 48, 240)]


def test_dalembert_partial_prize_steps_as_a_loss():
    # c=6: b 1, 2, 3, then the second prize at b=3 (pays 24 on 18, cycle -12) -> b=4.
    result = replay("LLSL", "dalembert", coverage=6, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 3, 4, 64, 60, 24)]
    old = replay("LLSL", "dalembert", coverage=6)
    assert rows(old) == [("incomplete", 0, 3, 4, 76, 48, 24)]


def test_dalembert_full_recovery_steps_back_by_one():
    result = replay("LLSWL", "dalembert", coverage=6, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 4, 5, 366, 78, 344)]


def test_paroli_counts_only_full_recoveries_as_wins():
    # c=6: a loss, then three second prizes. The first two do not recover (-4, -2): b stays 1.
    # The third brings the cycle to 0 (a recovery): streak 1 and b=2 for the last draw.
    result = replay("LSSSL", "paroli", coverage=6, stake_rules=2)
    assert rows(result) == [("incomplete", 0, 4, 5, 88, 36, 24)]
    # Rules 1 doubled after the first partial prize and reached the third win in a row (b=1 again).
    old = replay("LSSSL", "paroli", coverage=6)
    assert rows(old) == [("incomplete", 0, 4, 5, 102, 54, 56)]


def test_oscars_grind_rule_is_cycle_based_already_and_identical_on_both_rules():
    for draws in ("LLSWLL", "LLLWWSL", "LSSLWW"):
        old = replay(draws, "oscars_grind", coverage=6, prizes=(80, 8, 4, 2, 1))
        new = replay(draws, "oscars_grind", coverage=6, prizes=(80, 8, 4, 2, 1), stake_rules=2)
        assert asdict(old) == asdict(new)


@pytest.mark.parametrize("style", ["flat", "bold"])
def test_flat_and_bold_are_unchanged_by_the_rules(style):
    draws = "LLSWLWLLSL"
    old = replay(draws, style, coverage=2, capital=300, goal=600)
    new = replay(draws, style, coverage=2, capital=300, goal=600, stake_rules=2)
    assert asdict(old) == asdict(new)


@pytest.mark.parametrize("style", ["martingale", "paroli", "dalembert", "fibonacci"])
def test_progressions_without_partial_prizes_behave_the_same_on_both_rules(style):
    # Only first prizes and misses: every draw that pays recovers its cycle, so v2 = v1.
    draws = "LLWLWWLLLWLL"
    old = replay(draws, style, coverage=2, capital=500)
    new = replay(draws, style, coverage=2, capital=500, stake_rules=2)
    assert asdict(old) == asdict(new)


@pytest.mark.parametrize("style", ["martingale", "paroli", "dalembert", "fibonacci"])
def test_progressions_stay_within_cap_and_balance_on_rules_two(style):
    result = replay(
        "LLSLLSLLLWLL", style, coverage=2, capital=100, max_stake_per_number=3, stake_rules=2
    )
    for session in result.sessions:
        assert session.wagered <= 3 * 2 * session.draws


# ------------------------------------------------------------------------ API


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


def create_lab(client, name, config):
    return client.post(
        "/api/v1/laboratories", json={"name": name, "config": config}, headers=ORIGIN
    )


@pytest.mark.parametrize("style", ["ladder", "martingale"])
def test_api_creates_and_runs_a_leidsa_lab_with_rules_two(client, style):
    sha = activate_leidsa(client)
    created = create_lab(
        client,
        f"v2 {style}",
        {**LEIDSA_CONFIG, "stake_style": style, "system": "cold", "stake_rules": 2},
    )
    assert created.status_code == 201, created.text
    lab = created.json()
    assert lab["config"]["stake_rules"] == 2
    run = client.post(
        f"/api/v1/laboratories/{lab['id']}/runs",
        json={"required_history_sha256": sha},
        headers=ORIGIN,
    )
    assert run.status_code == 201, run.text
    body = run.json()
    assert body["snapshot"]["definition"]["config"]["stake_rules"] == 2
    assert body["summary"]["totals"]["sessions_total"] >= 1
    assert client.get(f"/api/v1/laboratories/{lab['id']}/runs/{body['id']}").json() == body


def test_api_lab_without_the_field_has_no_key(client):
    activate_leidsa(client)
    created = create_lab(client, "sin reglas", LEIDSA_CONFIG)
    assert created.status_code == 201, created.text
    assert "stake_rules" not in created.json()["config"]


@pytest.mark.parametrize("value", [0, 3, "2", True, None])
def test_api_refuses_unknown_rules_with_a_spanish_422(client, value):
    activate_leidsa(client)
    before = client.get("/api/v1/laboratories").json()["total"]
    response = create_lab(client, "malo", {**LEIDSA_CONFIG, "stake_rules": value})
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == MESSAGE
    assert client.get("/api/v1/laboratories").json()["total"] == before
