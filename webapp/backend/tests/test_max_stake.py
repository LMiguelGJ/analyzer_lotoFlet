"""Optional ``max_stake_per_number`` (bank cap): config, engine, golden parity and API.

Engine scenarios were computed by hand. Draw rows (parity picks the even numbers, so number 0 is
always played): ``W`` first prize on number 0, ``L`` nothing. ``c`` is the coverage and ``b`` the
stake on every played number; the draw stake is ``b x c``.
"""

from dataclasses import asdict, replace
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.laboratories import LaboratoryConfig, LaboratoryDefinition
from laboratorio.domain.reference_labs import REFERENCE_LABS, STAKE_STYLE_LABELS, ReferenceLab
from laboratorio.engine.reference_labs import run_reference_lab
from laboratorio.engine.stake_styles import make_progression
from laboratorio.settings import Settings

BASE = "http://localhost:8765"
ORIGIN = {"Origin": BASE, "Content-Type": "application/json"}
LEIDSA = "leidsa_quiniela"
MESSAGE = (
    "La apuesta máxima por número debe ser un número entero entre 1 y 1000000, "
    "o quedar vacía para no poner tope."
)

CHANCE_CONFIG = {
    "schema_version": 1,
    "system": "cold",
    "coverage": 10,
    "stake_style": "flat",
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
ROWS = {"W": [0, 91, 92, 93, 94], "L": [1, 91, 92, 93, 94]}
PRIZES = (80, 8, 4, 2, 1)
SMALL_PRIZES = (10, 3, 2, 1, 1)


# ------------------------------------------------------------------------ config


def test_config_without_the_field_keeps_the_exact_mapping():
    config = LaboratoryConfig.from_mapping(CHANCE_CONFIG)
    assert config.max_stake_per_number is None
    assert config.to_mapping() == CHANCE_CONFIG
    assert "max_stake_per_number" not in config.to_mapping()


def test_config_with_the_field_round_trips():
    config = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_stake_per_number": 500})
    assert config.max_stake_per_number == 500
    assert config.to_mapping() == {**CHANCE_CONFIG, "max_stake_per_number": 500}
    assert LaboratoryConfig.from_mapping(config.to_mapping()) == config


def test_config_with_both_optional_fields_round_trips():
    raw = {**LEIDSA_CONFIG, "list_id": LEIDSA, "max_session_draws": 30, "max_stake_per_number": 500}
    config = LaboratoryConfig.from_mapping(raw)
    assert config.to_mapping() == raw


def test_explicit_null_means_no_cap_and_is_not_emitted():
    config = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_stake_per_number": None})
    assert config.max_stake_per_number is None
    assert config.to_mapping() == CHANCE_CONFIG


@pytest.mark.parametrize("value", [1, 500, 1_000_000])
def test_bounds_are_accepted(value):
    config = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_stake_per_number": value})
    assert config.max_stake_per_number == value


@pytest.mark.parametrize("value", [0, -1, 1_000_001, True, False, 1.5, "500", [500]])
def test_invalid_values_are_refused_in_spanish(value):
    with pytest.raises(ValueError) as caught:
        LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_stake_per_number": value})
    assert str(caught.value) == MESSAGE


def test_reference_lab_adapter_carries_the_cap():
    identity = "6f1b0c1e-0b5c-4b57-9a54-0d9c7d6f4a11"
    capped = LaboratoryConfig.from_mapping({**CHANCE_CONFIG, "max_stake_per_number": 500})
    lab = LaboratoryDefinition(identity, "x", capped).to_reference_lab()
    assert lab.max_stake_per_number == 500
    plain = LaboratoryConfig.from_mapping(CHANCE_CONFIG)
    lab = LaboratoryDefinition(identity, "x", plain).to_reference_lab()
    assert lab.max_stake_per_number is None


def test_the_fourteen_chance_reference_labs_have_no_cap():
    assert all(lab.max_stake_per_number is None for lab in REFERENCE_LABS)


# ------------------------------------------------------------------------ engine


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


def test_martingale_is_capped_and_the_state_follows_the_stake_placed():
    # cap 3: 1, 2, 4->3, 8->3, 16->3; the win pays 3 x 80 and b returns to 1 for the last draw.
    result = replay("LLLLLWL", "martingale", max_stake_per_number=3)
    assert [row(s) for s in result.sessions] == [("incomplete", 0, 6, 7, 324, 16, 240)]


def test_martingale_without_the_cap_is_unchanged_by_the_feature():
    result = replay("LLLLLWL", "martingale")
    big = replay("LLLLLWL", "martingale", max_stake_per_number=1_000_000)
    assert asdict(big) == asdict(result)


def test_fibonacci_cap_lowers_the_index_to_the_stake_placed():
    # terms 1,1,2,3,5; cap 2: 1, 1, 2, 3->2, 3->2, win (index back by two, to 0), then 1.
    result = replay("LLLLLWL", "fibonacci", max_stake_per_number=2)
    assert [row(s) for s in result.sessions] == [("incomplete", 0, 6, 7, 249, 11, 160)]


def test_bold_keeps_its_goal_math_but_is_capped():
    # goal 1000, c=1, P1=80: wants 12, 12, 7, 7 per number; cap 5; balance 100 -> 95 -> 490 ->
    # 485 -> 880 (stake 5); then it wants ceil(120/79)=2 < cap, wins 160 and reaches the goal.
    result = replay("LWLWW", "bold", goal=1000, max_stake_per_number=5)
    assert [row(s) for s in result.sessions] == [("goal", 0, 4, 5, 1038, 22, 960)]


def test_bold_without_the_cap_wagers_more():
    plain = replay("LWLWW", "bold", goal=1000)
    capped = replay("LWLWW", "bold", goal=1000, max_stake_per_number=5)
    assert plain.totals.total_wagered > capped.totals.total_wagered


def test_ladder_is_capped_and_still_advances_its_rounds():
    # c=1, P1=10: ladder 2,2,2,2,2,3,3,3,4,4. Cap 2 binds only from the sixth round on.
    result = replay("LLLLLLL", "ladder", prizes=SMALL_PRIZES, max_stake_per_number=2)
    assert [row(s) for s in result.sessions] == [("incomplete", 0, 6, 7, 86, 14, 0)]
    # A first-prize hit resets the ladder: the seventh draw wins 2 x 10.
    result = replay("LLLLLLW", "ladder", prizes=SMALL_PRIZES, max_stake_per_number=2)
    assert [row(s) for s in result.sessions] == [("incomplete", 0, 6, 7, 106, 14, 20)]


def test_flat_with_a_cap_of_one_is_the_same_as_without():
    plain = replay("LWLLW", "flat")
    assert asdict(replay("LWLLW", "flat", max_stake_per_number=1)) == asdict(plain)


def test_coverage_multiplies_the_capped_stake():
    # c=2, cap 3: stakes per number 1, 2, 3, 3 -> 2, 4, 6, 6 pesos per draw.
    result = replay("LLLL", "martingale", coverage=2, max_stake_per_number=3)
    assert [row(s) for s in result.sessions] == [("incomplete", 0, 3, 4, 82, 18, 0)]


def test_ruin_still_happens_when_the_capped_stake_exhausts_the_balance():
    # capital 10, cap 3: 1, 2, 3, 3, then only 1 peso is left and it is played: ruin at 0.
    result = replay("LLLLL", "martingale", capital=10, max_stake_per_number=3)
    assert [row(s) for s in result.sessions] == [("ruin", 0, 4, 5, 0, 10, 0)]


def test_progression_object_never_exceeds_the_cap_nor_the_balance():
    progression = make_progression("martingale", 2, 80, 10_000, max_stake=3)
    stakes = []
    balance = 100
    for _ in range(6):
        per_number = progression.bet(balance)
        stakes.append(per_number)
        balance -= 2 * per_number
        progression.settle(2 * per_number, 0)
    assert stakes == [1, 2, 3, 3, 3, 3]
    assert progression.bet(4) == 2  # balance // coverage is still the tighter bound


@pytest.mark.parametrize("style", list(STAKE_STYLE_LABELS))
def test_every_style_never_places_more_than_cap_times_coverage_per_draw(style):
    draws = "LLLLWLLLLLWLLLLLLLWLLL"
    cap, coverage = 2, 2
    result = replay(draws, style, coverage=coverage, capital=300, max_stake_per_number=cap)
    assert result.sessions
    for session in result.sessions:
        assert session.wagered <= cap * coverage * session.draws


@pytest.mark.parametrize("style", list(STAKE_STYLE_LABELS))
def test_a_cap_that_never_binds_changes_nothing(style):
    draws = "LLLLWLLLLLWLLLLLLLWLLL"
    plain = replay(draws, style, coverage=2, capital=300)
    capped = replay(draws, style, coverage=2, capital=300, max_stake_per_number=1_000_000)
    assert asdict(capped) == asdict(plain)


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


def test_api_creates_and_runs_a_leidsa_lab_with_a_stake_cap(client):
    sha = activate_leidsa(client)
    config = {
        **LEIDSA_CONFIG,
        "coverage": 1,
        "stake_style": "bold",
        "capital": 20_000,
        "goal": 50_000,
        "max_stake_per_number": 500,
    }
    created = create_lab(client, "con tope", config)
    assert created.status_code == 201, created.text
    lab = created.json()
    assert lab["config"]["max_stake_per_number"] == 500
    run = client.post(
        f"/api/v1/laboratories/{lab['id']}/runs",
        json={"required_history_sha256": sha},
        headers=ORIGIN,
    )
    assert run.status_code == 201, run.text
    body = run.json()
    assert body["snapshot"]["definition"]["config"]["max_stake_per_number"] == 500
    sessions = client.get(
        f"/api/v1/laboratories/{lab['id']}/runs/{body['id']}/sessions?limit=500"
    ).json()
    rows = [item["summary"] for item in sessions["items"]]
    assert rows
    assert all(item["wagered"] <= 500 * item["draws"] for item in rows)
    assert client.get(f"/api/v1/laboratories/{lab['id']}/runs/{body['id']}").json() == run.json()


def test_api_lab_without_the_field_has_no_key_anywhere(client):
    activate_leidsa(client)
    created = create_lab(client, "sin tope", LEIDSA_CONFIG)
    assert created.status_code == 201, created.text
    assert "max_stake_per_number" not in created.json()["config"]


def test_api_null_cap_is_stored_as_absent(client):
    activate_leidsa(client)
    created = create_lab(client, "nulo", {**LEIDSA_CONFIG, "max_stake_per_number": None})
    assert created.status_code == 201, created.text
    assert "max_stake_per_number" not in created.json()["config"]


@pytest.mark.parametrize("value", [0, -5, 1_000_001, 2.5, "500", True])
def test_api_refuses_a_bad_cap_with_a_spanish_422(client, value):
    activate_leidsa(client)
    before = client.get("/api/v1/laboratories").json()["total"]
    response = create_lab(client, "malo", {**LEIDSA_CONFIG, "max_stake_per_number": value})
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == MESSAGE
    assert client.get("/api/v1/laboratories").json()["total"] == before
