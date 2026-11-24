"""The four extra Leidsa systems: transition, overdue, digits and ensemble.

Every ranking row is a permutation built only from draws strictly before it, so these
tests pin the causal contract, hand-computed tiny histories per family and the API
surface that offers the systems to Leidsa (and refuses them on Chance Express).
"""

import time
from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.contracts import SYSTEMS
from laboratorio.domain.number_lists import (
    LIST_ONLY_SYSTEMS,
    get_list,
    system_label,
    unavailable_message,
)
from laboratorio.engine import causal_rankings as cr
from laboratorio.settings import Settings

BASE = "http://localhost:8765"
ORIGIN = {"Origin": BASE, "Content-Type": "application/json"}
LEIDSA = "leidsa_quiniela"
UNAVAILABLE = "No disponible para esta lista"
NEW_SYSTEMS = ("transition", "overdue", "digits", "ensemble")
LABELS = {
    "transition": "Transición",
    "overdue": "Ciclo vencido",
    "digits": "Terminaciones y decenas",
    "ensemble": "Ensamble",
}


@pytest.fixture
def client(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    app = create_app(settings, catalog_loader=lambda _settings: lab_data)
    with TestClient(app, base_url=BASE, raise_server_exceptions=False) as http:
        yield http


def activate(client, list_id):
    response = client.put("/api/v1/lists/active", json={"id": list_id}, headers=ORIGIN)
    assert response.status_code == 200, response.text


def mix(system, coverage=10):
    return {
        "kind": "mix",
        "components": [{"system": system, "percent": 100}],
        "coverage": coverage,
    }


def run_body(strategy, max_draws: int | None = 40):
    return {
        "name": None,
        "rules": {"positions": 3, "prizes": [60, 8, 4], "minimum_stake": 1},
        "strategy": strategy,
        "conditions": {"capital": 2000, "goal": 2800, "max_draws": max_draws},
        "window": {"start_date": None, "end_date": None},
        "history_sha256": None,
    }


def leidsa_config(system, coverage=10):
    return {
        "schema_version": 1,
        "system": system,
        "coverage": coverage,
        "stake_style": "flat",
        "capital": 2000,
        "goal": 2800,
        "prizes": [60, 8, 4],
        "window_start": "2023-01-04 20:50",
        "window_end": "2026-11-16 20:50",
    }


def chance_config(system, coverage=10):
    return {
        "schema_version": 1,
        "system": system,
        "coverage": coverage,
        "stake_style": "flat",
        "capital": 2000,
        "goal": 2800,
        "prizes": [80, 8, 4, 2, 1],
        "window_start": "2025-09-02 05:10",
        "window_end": "2026-09-25 18:20",
    }


def random_nums(rows, width=3, seed=7):
    return np.random.default_rng(seed).integers(0, 100, size=(rows, width), dtype=np.int64)


# ------------------------------------------------------------------ the registry


def test_the_four_archived_families_stay_first_and_the_new_ones_are_extra():
    assert cr.FAMILIES == ("cold", "freq_hist", "freq_recent", "decay")
    assert tuple(cr.EXTRA_FAMILIES) == NEW_SYSTEMS
    assert cr.LEIDSA_FAMILIES == cr.FAMILIES + cr.EXTRA_FAMILIES
    for system in NEW_SYSTEMS:
        assert system in cr.DEFAULT_PARAMS
    assert cr.DEFAULT_PARAMS["transition"] == {"fallback_window": 500}
    assert cr.DEFAULT_PARAMS["overdue"] == {}
    assert cr.DEFAULT_PARAMS["digits"] == {"window": 500}
    assert cr.DEFAULT_PARAMS["ensemble"] == {
        "components": (
            "cold",
            "freq_hist",
            "freq_recent",
            "decay",
            "transition",
            "overdue",
            "digits",
        )
    }


# ------------------------------------------------------- the list labels (plan §2)


def test_the_list_label_wins_then_the_archived_one_then_the_id():
    leidsa = get_list(LEIDSA)
    chance = get_list("chance_express")
    assert leidsa is not None and chance is not None
    assert system_label("ensemble", leidsa) == "Ensamble"
    assert system_label("ensemble", chance) == "Ensemble"  # Chance keeps its archived label
    assert system_label("transition") == "Transición"
    assert system_label("notebook", leidsa) == "Cuaderno"
    assert system_label("overdue") == "overdue"
    assert system_label("overdue", chance) == "overdue"
    assert system_label("parity", leidsa) == "Paridad"
    assert tuple(LIST_ONLY_SYSTEMS) == ("overdue", "digits")
    assert not set(LIST_ONLY_SYSTEMS) & set(SYSTEMS)  # the archived export stays untouched
    assert unavailable_message("overdue", chance) == (
        "El sistema «overdue»: No disponible para esta lista."
    )


# ------------------------------------------------------- causal contract, per family


@pytest.mark.parametrize("system", NEW_SYSTEMS)
def test_every_row_is_a_permutation_of_the_hundred_numbers(system):
    ranking = cr.causal_ranking(system, random_nums(300))
    assert ranking.shape == (300, 100) and ranking.dtype == np.uint8
    assert (np.sort(ranking, axis=1) == np.arange(100)).all()


@pytest.mark.parametrize("system", NEW_SYSTEMS)
def test_a_row_depends_only_on_the_draws_before_it(system):
    nums = random_nums(400)
    baseline = cr.causal_ranking(system, nums)
    cut = 250
    mutated = nums.copy()
    mutated[cut:] = random_nums(400 - cut, seed=99)  # rewrite the future, including draw `cut`
    changed = cr.causal_ranking(system, mutated)
    assert np.array_equal(baseline[: cut + 1], changed[: cut + 1])
    # ...and the mutation is really visible afterwards (the test can fail).
    assert not np.array_equal(baseline[cut + 1 :], changed[cut + 1 :])


@pytest.mark.parametrize("system", NEW_SYSTEMS)
def test_the_first_row_has_no_information_and_follows_the_fixed_tie_order(system):
    ranking = cr.causal_ranking(system, random_nums(5))
    assert tuple(ranking[0]) == tuple(np.argsort(cr.TIE))


# ------------------------------------------------------------ hand-computed histories


def test_transition_counts_the_pair_and_the_row_zero_fallback():
    nums = np.zeros((5, 3), dtype=np.int64)
    nums[:, 0] = [10, 11, 12, 10, 11]
    scores = cr.score_matrix("transition", nums)
    scale = 1.0 / (1000 * (500 + 1))
    # Row 4 sees pairs s<=3: (10,11), (11,12) and (12,10); the last draw is 10, so 11 leads.
    assert scores[4, 11] == pytest.approx(1 + scale)
    assert scores[4, 10] == pytest.approx(2 * scale)  # 10 was drawn twice before row 4
    assert scores[4, 12] == pytest.approx(scale)
    assert scores[4, 20] == 0.0
    # Row 2 only knows the pair (10,11), and 11 was the draw before it.
    assert scores[2, 11] == pytest.approx(scale)
    assert scores[2, 10] == pytest.approx(scale)
    assert scores[2, 12] == 0.0
    # Row 1 only counts the draw at row 0; row 0 counts nothing.
    assert scores[1, 10] == pytest.approx(scale)
    assert scores[1, 11] == 0.0
    assert not scores[0].any()
    assert tuple(cr.causal_ranking("transition", nums)[4][:3]) == (11, 10, 12)


def test_overdue_divides_the_age_by_the_mean_gap():
    nums = np.zeros((6, 3), dtype=np.int64)
    nums[:, 0] = [5, 9, 9, 9, 5, 20]
    scores = cr.score_matrix("overdue", nums)
    # 9 appeared three times (rows 1-3, mean gap 1) and its age at row 5 is 2.
    assert scores[5, 9] == pytest.approx(2.0)
    # 5 appeared twice (rows 0 and 4, mean gap 4) and its age at row 5 is 1.
    assert scores[5, 5] == pytest.approx(0.25)
    # 20 was never seen: age t + 1 over the 100-draw fallback gap.
    assert scores[5, 20] == pytest.approx(6 / 100)
    assert tuple(cr.causal_ranking("overdue", nums)[5][:2]) == (9, 5)
    # Row 0 has no history at all, so every number scores 1/100.
    assert np.allclose(scores[0], 1 / 100)
    assert not np.allclose(scores[1], scores[1][0])


def test_digits_add_the_units_share_and_the_decade_share():
    nums = np.zeros((5, 3), dtype=np.int64)
    nums[:, 0] = [12, 12, 33, 47, 5]
    scores = cr.score_matrix("digits", nums)
    # Units before row 4: 2 -> 1/2, 3 -> 1/4, 7 -> 1/4. Decades: 1 -> 1/2, 3 -> 1/4, 4 -> 1/4.
    assert scores[4, 12] == pytest.approx(1.0)
    assert scores[4, 13] == pytest.approx(0.5 + 0.25)
    assert scores[4, 42] == pytest.approx(0.5 + 0.25)
    assert scores[4, 33] == pytest.approx(0.5)
    assert scores[4, 47] == pytest.approx(0.5)
    assert scores[4, 27] == pytest.approx(0.25)
    assert int(cr.causal_ranking("digits", nums)[4][0]) == 12
    # Row 0 has no draws in the window, so every score is 0.
    assert not scores[0].any()
    # A two-draw window only counts 33 and 47.
    narrow = cr.score_matrix("digits", nums, {"window": 2})
    assert narrow[4, 47] == pytest.approx(1.0)
    assert narrow[4, 12] == 0.0


def test_ensemble_is_minus_the_mean_ranking_position_of_the_seven_components():
    nums = random_nums(40, seed=11)
    components = cr.DEFAULT_PARAMS["ensemble"]["components"]
    assert "parity" not in components and len(components) == 7
    positions = [
        np.argsort(cr.causal_ranking(component, nums), axis=1).astype(np.float64)
        for component in components
    ]
    expected = -np.mean(positions, axis=0)
    scores = cr.score_matrix("ensemble", nums)
    assert np.allclose(scores, expected)
    assert np.array_equal(cr.rank_rows(scores), cr.causal_ranking("ensemble", nums))


def test_causal_rankings_cache_the_new_families():
    nums = random_nums(60)
    rankings = cr.CausalRankings(nums)
    for system in NEW_SYSTEMS:
        assert np.array_equal(rankings.family(system), cr.causal_ranking(system, nums))
        assert rankings.family(system) is rankings.family(system)


# ------------------------------------------------------------------------- the API


@pytest.mark.parametrize("system", NEW_SYSTEMS)
def test_each_new_system_creates_and_runs_a_leidsa_laboratory(client, system):
    activate(client, LEIDSA)
    created = client.post(
        "/api/v1/laboratories",
        json={"name": f"nuevo {system}", "config": leidsa_config(system)},
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    lab = created.json()
    assert lab["config"]["system"] == system
    sha = client.get("/api/v1/runs/options").json()["history"]["sha256"]
    response = client.post(
        f"/api/v1/laboratories/{lab['id']}/runs",
        json={"required_history_sha256": sha},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["snapshot"]["provenance"]["list_id"] == LEIDSA
    assert run["snapshot"]["provenance"]["ranking_method"] == "causal-on-the-fly/v1"
    assert run["snapshot"]["provenance"]["history_origin"] == "list"
    assert run["summary"]["session_count"] >= 1


@pytest.mark.parametrize(("system", "label"), sorted(LABELS.items()))
def test_the_default_run_name_uses_the_leidsa_label(client, system, label):
    activate(client, LEIDSA)
    response = client.post("/api/v1/runs", json=run_body(mix(system, 5)), headers=ORIGIN)
    assert response.status_code == 201, response.text
    assert response.json()["name"] == f"{label} · 5 números"


def test_leidsa_run_options_offer_the_two_list_only_systems(client):
    activate(client, LEIDSA)
    options = client.get("/api/v1/runs/options").json()
    by_id = {item["id"]: item for item in options["systems"]}
    assert set(by_id) == set(SYSTEMS) | set(LIST_ONLY_SYSTEMS)
    for system in LIST_ONLY_SYSTEMS:
        assert by_id[system]["available"] is True
        assert by_id[system]["label"] == LABELS[system]
    assert by_id["ensemble"]["label"] == "Ensamble"


def test_chance_run_options_do_not_offer_the_new_systems(client):
    options = client.get("/api/v1/runs/options").json()
    offered = {item["id"] for item in options["systems"]}
    assert offered == set(SYSTEMS)
    for system in LIST_ONLY_SYSTEMS:
        assert system not in offered


@pytest.mark.parametrize("system", sorted(LIST_ONLY_SYSTEMS))
def test_chance_rejects_the_list_only_systems(client, system):
    response = client.post("/api/v1/runs", json=run_body(mix(system)), headers=ORIGIN)
    assert response.status_code == 422
    assert UNAVAILABLE in response.json()["detail"]
    created = client.post(
        "/api/v1/laboratories",
        json={"name": f"chance {system}", "config": chance_config(system)},
        headers=ORIGIN,
    )
    assert created.status_code == 422


# ----------------------------------------------------------------------- performance


@pytest.mark.parametrize("system", NEW_SYSTEMS)
def test_a_full_range_leidsa_run_takes_less_than_five_seconds(client, system):
    activate(client, LEIDSA)
    draws = client.get("/api/v1/runs/options").json()["history"]["draws"]
    body = run_body(mix(system, 10), max_draws=None)
    started = time.perf_counter()
    response = client.post("/api/v1/runs", json=body, headers=ORIGIN)
    elapsed = time.perf_counter() - started
    assert response.status_code == 201, response.text
    assert response.json()["summary"]["window"]["draws"] == draws
    print(f"\nPERF {system} full range: {elapsed:.3f}s for {draws} draws")
    assert elapsed < 5.0
