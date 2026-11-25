"""Per-laboratory ``ranking_params`` (T1: S1, S4, S5).

Covers the config codec (absent = today's mapping), the Spanish validation, the engine
(deep-merge of partial overrides, ensemble with params, seeded tie-break), the run path
(Leidsa "Decaimiento 300"), the warm-up default of ``GET /laboratories/options`` and the
extra B-009 rule for new progression labs.
"""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.laboratories import LaboratoryConfig, validate_new_laboratory_config
from laboratorio.engine import causal_rankings as cr
from laboratorio.settings import Settings
from laboratorio.storage.laboratory_store import (
    create_laboratory_definition as store_laboratory,
)

BASE = "http://localhost:8765"
ORIGIN = {"Origin": BASE, "Content-Type": "application/json"}
LEIDSA = "leidsa_quiniela"
LEIDSA_FILE = Path(__file__).resolve().parents[3] / "datos" / "leidsa_quiniela_history.json"


@pytest.fixture
def client(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    app = create_app(settings, catalog_loader=lambda _settings: lab_data)
    with TestClient(app, base_url=BASE, raise_server_exceptions=False) as http:
        yield http


def activate(client, list_id):
    response = client.put("/api/v1/lists/active", json={"id": list_id}, headers=ORIGIN)
    assert response.status_code == 200, response.text


def leidsa_sha(client):
    return client.get("/api/v1/runs/options").json()["history"]["sha256"]


def lab_config(system="decay", coverage=1, **changes):
    value = {
        "schema_version": 1,
        "system": system,
        "coverage": coverage,
        "stake_style": "bold",
        "capital": 10000,
        "goal": 10500,
        "prizes": [60, 8, 4],
        "window_start": "2019-01-01 00:00",
        "window_end": "2026-12-31 23:59",
    }
    return value | changes


def create_lab(client, name, config):
    return client.post(
        "/api/v1/laboratories", json={"name": name, "config": config}, headers=ORIGIN
    )


def domain_config(system="decay", **changes):
    value = lab_config(system) | {"list_id": LEIDSA} | changes
    return LaboratoryConfig.from_mapping(value)


def _random_nums(rows, width=3, seed=11):
    return np.random.default_rng(seed).integers(0, 100, size=(rows, width), dtype=np.int64)


# -------------------------------------------------------------------- config codec


def test_absent_ranking_params_keep_todays_mapping_byte_identical():
    config = domain_config()
    mapping = config.to_mapping()
    assert "ranking_params" not in mapping
    assert config.ranking_params is None
    assert LaboratoryConfig.from_mapping(mapping) == config
    assert LaboratoryConfig.from_mapping(mapping).to_mapping() == mapping
    # An empty object means "defaults" too and is not stored.
    assert "ranking_params" not in domain_config(ranking_params={}).to_mapping()


@pytest.mark.parametrize(
    ("system", "params"),
    [
        ("decay", {"half_life": 300}),
        ("freq_recent", {"window": 120, "tie_break": "seeded"}),
        ("freq_hist", {"window": None, "scope": "any"}),
        ("freq_hist", {"window": 365, "scope": "position"}),
        ("transition", {"fallback_window": 200}),
        ("digits", {"window": 90}),
        ("cold", {"scope": "any"}),
        ("overdue", {"tie_break": "seeded"}),
        ("ensemble", {"components": ["freq_recent", "decay", "digits"]}),
        (
            "ensemble",
            {
                "components": ["freq_recent", "decay"],
                "component_params": {"decay": {"half_life": 300}},
                "tie_break": "seeded",
            },
        ),
    ],
)
def test_present_ranking_params_round_trip(system, params):
    config = domain_config(system, ranking_params=params)
    mapping = config.to_mapping()
    assert mapping["ranking_params"] == params
    assert json.loads(json.dumps(mapping)) == mapping  # plain JSON
    assert LaboratoryConfig.from_mapping(mapping) == config
    assert LaboratoryConfig.from_mapping(mapping).to_mapping() == mapping


# --------------------------------------------------------------------- validation


@pytest.mark.parametrize(
    ("system", "params", "needle"),
    [
        ("decay", {"half_life": 4}, "vida media"),
        ("decay", {"half_life": 5001}, "vida media"),
        ("decay", {"half_life": "300"}, "vida media"),
        ("decay", {"half_life": True}, "vida media"),
        ("decay", {"half_life": 300.5}, "vida media"),
        ("decay", {"window": 300}, "window"),
        ("freq_recent", {"window": 9}, "ventana"),
        ("freq_recent", {"window": 5001}, "ventana"),
        ("freq_recent", {"window": None}, "ventana"),
        ("freq_hist", {"window": 0}, "ventana"),
        ("freq_hist", {"scope": "global"}, "mirar"),
        ("cold", {"scope": "everywhere"}, "mirar"),
        ("cold", {"window": 100}, "window"),
        ("transition", {"fallback_window": 3}, "ventana"),
        ("digits", {"window": -5}, "ventana"),
        ("overdue", {"window": 100}, "window"),
        ("decay", {"tie_break": "random"}, "desempate"),
        ("ensemble", {"components": ["decay"]}, "al menos 2"),
        ("ensemble", {"components": ["decay", "decay"]}, "repet"),
        ("ensemble", {"components": ["decay", "ensemble"]}, "componente"),
        ("ensemble", {"components": ["decay", "nope"]}, "componente"),
        ("ensemble", {"components": "decay"}, "componentes"),
        (
            "ensemble",
            {"components": ["decay", "cold"], "component_params": {"digits": {}}},
            "digits",
        ),
        (
            "ensemble",
            {"components": ["decay", "cold"], "component_params": {"decay": {"half_life": 1}}},
            "vida media",
        ),
        ("decay", "half_life=300", "objeto"),
        ("decay", [300], "objeto"),
    ],
)
def test_invalid_ranking_params_are_rejected_in_spanish(system, params, needle):
    with pytest.raises(ValueError) as caught:
        domain_config(system, ranking_params=params)
    assert needle in str(caught.value).lower()


def test_parity_takes_no_ranking_params():
    with pytest.raises(ValueError, match="Paridad"):
        domain_config("parity", coverage=50, ranking_params={"tie_break": "seeded"})


def test_api_rejects_invalid_ranking_params_with_a_spanish_422(client):
    activate(client, LEIDSA)
    response = create_lab(client, "mala", lab_config(ranking_params={"half_life": 1}))
    assert response.status_code == 422
    assert "vida media" in response.json()["detail"].lower()


def test_chance_express_rejects_ranking_params_with_a_spanish_422(client):
    activate(client, "chance_express")
    config = {
        "schema_version": 1,
        "system": "cold",
        "coverage": 1,
        "stake_style": "bold",
        "capital": 2000,
        "goal": 2800,
        "prizes": [80, 8, 4, 2, 1],
        "window_start": "2025-09-02 05:10",
        "window_end": "2026-09-25 18:20",
    }
    ok = create_lab(client, "sin parámetros", config)
    assert ok.status_code == 201, ok.text
    response = create_lab(client, "con parámetros", config | {"ranking_params": {"scope": "any"}})
    assert response.status_code == 422
    assert "Chance Express" in response.json()["detail"]


# ------------------------------------------------------------------------- B-009


@pytest.mark.parametrize("style", ["martingale", "paroli", "dalembert", "fibonacci"])
def test_new_progression_labs_need_first_prize_above_coverage(client, style):
    activate(client, LEIDSA)
    config = lab_config("cold", 60, stake_style=style, capital=2000, goal=2800)
    config["coverage"] = 50  # prizes[0] = 60 > 50: fine
    assert create_lab(client, f"{style} ok", config).status_code == 201
    bad = lab_config("cold", 50, stake_style=style, capital=2000, goal=2800, prizes=[40, 8, 4])
    response = create_lab(client, f"{style} mal", bad)
    assert response.status_code == 422
    assert "primer premio" in response.json()["detail"].lower()


def test_stored_progression_labs_that_break_the_new_rule_still_load_and_list(client):
    activate(client, LEIDSA)
    legacy = domain_config(
        "cold",
        coverage=50,
        stake_style="martingale",
        capital=2000,
        goal=2800,
        prizes=[40, 8, 4],
    )
    with pytest.raises(ValueError, match="primer premio"):
        validate_new_laboratory_config(legacy)
    # Stored rows and snapshots are decoded without the new-lab rule.
    settings = client.app.state.settings
    stored = store_laboratory(
        client.app.state.repo,
        "vieja",
        legacy,
        quota_bytes=settings.quota_bytes,
        quota_explicit=settings.is_quota_explicit,
    )
    assert LaboratoryConfig.from_mapping(stored.config.to_mapping()) == legacy
    listed = client.get("/api/v1/laboratories").json()["items"]
    assert [item["name"] for item in listed if item["name"] == "vieja"] == ["vieja"]
    detail = client.get(f"/api/v1/laboratories/{stored.id}")
    assert detail.status_code == 200


# ------------------------------------------------------------------ engine: merge


def test_partial_overrides_are_deep_merged_with_the_family_defaults():
    nums = _random_nums(260)
    partial = cr.CausalRankings(nums, {"freq_hist": {"window": 100}, "decay": {}})
    full = cr.CausalRankings(
        nums, {"freq_hist": {"scope": "position", "window": 100}, "decay": {"half_life": 500}}
    )
    for system in ("freq_hist", "decay"):
        assert np.array_equal(partial.family(system), full.family(system))
    assert np.array_equal(
        cr.causal_ranking("freq_hist", nums, {"window": 100}),
        cr.causal_ranking("freq_hist", nums, {"scope": "position", "window": 100}),
    )
    assert np.array_equal(
        cr.causal_ranking("cold", nums, {}), cr.causal_ranking("cold", nums, None)
    )
    # The shared defaults are never mutated by a merge.
    assert cr.DEFAULT_PARAMS["freq_hist"] == {"scope": "position", "window": None}


def test_freq_hist_any_scope_counts_every_position():
    nums = np.zeros((6, 3), dtype=np.int64)
    nums[:, 0] = [1, 1, 1, 1, 1, 1]
    nums[:, 1] = [7, 7, 7, 7, 7, 7]
    nums[:, 2] = [1, 1, 1, 1, 1, 1]
    position = cr.causal_ranking("freq_hist", nums, {"scope": "position", "window": None})
    anywhere = cr.causal_ranking("freq_hist", nums, {"scope": "any", "window": None})
    assert int(position[5][0]) == 1
    assert {int(v) for v in anywhere[5][:2]} == {1, 7}


# ----------------------------------------------------------------- engine: ensemble


def _legacy_ensemble(nums, components):
    positions = [
        np.argsort(cr.causal_ranking(component, nums), axis=1).astype(np.float64)
        for component in components
    ]
    return cr.rank_rows(-np.mean(positions, axis=0))


def test_default_ensemble_is_unchanged():
    nums = _random_nums(320)
    expected = _legacy_ensemble(nums, cr.DEFAULT_PARAMS["ensemble"]["components"])
    assert np.array_equal(cr.causal_ranking("ensemble", nums), expected)
    assert np.array_equal(cr.CausalRankings(nums).family("ensemble"), expected)
    assert np.array_equal(cr.CausalRankings(nums, {"ensemble": {}}).family("ensemble"), expected)


def test_ensemble_with_custom_components_differs_and_uses_only_them():
    nums = _random_nums(320)
    default = cr.CausalRankings(nums).family("ensemble")
    params = {"ensemble": {"components": ["freq_recent", "decay", "digits"]}}
    custom = cr.CausalRankings(nums, params).family("ensemble")
    assert not np.array_equal(custom, default)
    assert np.array_equal(custom, _legacy_ensemble(nums, ("freq_recent", "decay", "digits")))


def test_ensemble_components_respect_their_params():
    nums = _random_nums(320)
    base = {"components": ["freq_recent", "decay"]}
    plain = cr.CausalRankings(nums, {"ensemble": base}).family("ensemble")
    tuned = cr.CausalRankings(
        nums,
        {"ensemble": base | {"component_params": {"decay": {"half_life": 20}}}},
    ).family("ensemble")
    assert not np.array_equal(plain, tuned)
    decay20 = cr.causal_ranking("decay", nums, {"half_life": 20})
    freq = cr.causal_ranking("freq_recent", nums)
    positions = [np.argsort(freq, axis=1), np.argsort(decay20, axis=1)]
    assert np.array_equal(tuned, cr.rank_rows(-np.mean(np.asarray(positions, float), axis=0)))
    # The standalone score function takes the same params.
    standalone = cr.causal_ranking(
        "ensemble", nums, base | {"component_params": {"decay": {"half_life": 20}}}
    )
    assert np.array_equal(standalone, tuned)


def test_variants_are_cached_by_params_and_share_component_rankings():
    nums = _random_nums(200)
    base = cr.CausalRankings(nums)
    first = base.variant({"decay": {"half_life": 300}})
    again = base.variant({"decay": {"half_life": 300}})
    other = base.variant({"decay": {"half_life": 100}})
    assert first is again and first is not other
    assert not np.array_equal(first.family("decay"), other.family("decay"))
    assert np.array_equal(
        first.family("decay"), cr.causal_ranking("decay", nums, {"half_life": 300})
    )
    # A default ensemble variant reuses the component matrices the base already holds.
    base.family("cold")
    cached = base.family("cold")
    ensemble_variant = base.variant({"ensemble": {"components": ["cold", "decay"]}})
    ensemble_variant.family("ensemble")
    assert ensemble_variant._ranking("cold", cr.DEFAULT_PARAMS["cold"]) is cached


# ----------------------------------------------------------------- engine: tie-break


@pytest.mark.parametrize("system", ["freq_recent", "cold", "decay", "overdue", "digits"])
def test_seeded_tie_break_is_reproducible_causal_and_valid(system):
    nums = _random_nums(260)
    params = {"tie_break": "seeded"}
    first = cr.causal_ranking(system, nums, params)
    second = cr.causal_ranking(system, nums, params)
    assert np.array_equal(first, second)
    assert (np.sort(first, axis=1) == np.arange(100)).all()
    fixed = cr.causal_ranking(system, nums)
    assert not np.array_equal(first, fixed)
    # Row 0 has no information: the permutation depends on the draw index only.
    assert tuple(first[0]) != tuple(np.argsort(cr.TIE))
    assert tuple(first[0]) != tuple(first[1]) or system == "cold"
    # Causal: rewriting draws >= cut never changes rows <= cut.
    cut = 150
    mutated = nums.copy()
    mutated[cut:] = _random_nums(260 - cut, seed=77)
    changed = cr.causal_ranking(system, mutated, params)
    assert np.array_equal(first[: cut + 1], changed[: cut + 1])
    assert not np.array_equal(first[cut + 1 :], changed[cut + 1 :])
    # A subset of rows ranks exactly like the full matrix.
    rows = np.array([3, 40, 199])
    assert np.array_equal(cr.causal_ranking(system, nums, params, rows=rows), first[rows])


def test_seeded_tie_break_only_reorders_equal_scores():
    nums = _random_nums(260)
    scores = cr.score_matrix("freq_recent", nums, {"window": 500})
    seeded = cr.causal_ranking("freq_recent", nums, {"window": 500, "tie_break": "seeded"})
    for t in (50, 120, 259):
        ranked_scores = scores[t][seeded[t]]
        assert (np.diff(ranked_scores) <= 0).all()


def test_fixed_tie_break_equals_the_default():
    nums = _random_nums(100)
    assert np.array_equal(
        cr.causal_ranking("decay", nums, {"half_life": 500, "tie_break": "fixed"}),
        cr.causal_ranking("decay", nums),
    )


# ------------------------------------------------------------------------ run path


def test_leidsa_decay_300_lab_matches_the_simulator_net(client):
    activate(client, LEIDSA)
    created = create_lab(client, "Decaimiento 300", lab_config(ranking_params={"half_life": 300}))
    assert created.status_code == 201, created.text
    lab = created.json()
    assert lab["config"]["ranking_params"] == {"half_life": 300}
    run = client.post(
        f"/api/v1/laboratories/{lab['id']}/runs",
        json={"required_history_sha256": leidsa_sha(client)},
        headers=ORIGIN,
    )
    assert run.status_code == 201, run.text
    body = run.json()
    assert body["snapshot"]["definition"]["config"]["ranking_params"] == {"half_life": 300}
    assert body["summary"]["totals"]["total_net"] == 16959
    assert body["summary"]["totals"]["ruins"] == 0


def test_default_params_lab_does_not_equal_decay_300_and_stays_on_defaults(client):
    activate(client, LEIDSA)
    plain = create_lab(client, "Decaimiento por defecto", lab_config()).json()
    explicit = create_lab(
        client, "Decaimiento 500", lab_config(ranking_params={"half_life": 500})
    ).json()
    sha = leidsa_sha(client)
    totals = []
    for lab in (plain, explicit):
        response = client.post(
            f"/api/v1/laboratories/{lab['id']}/runs",
            json={"required_history_sha256": sha},
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        totals.append(response.json()["summary"]["totals"])
    assert totals[0] == totals[1]
    assert "ranking_params" not in plain["config"]
    assert totals[0]["total_net"] != 16959


def test_the_stored_decay_300_ranking_is_not_polluted_by_other_runs(client):
    """Running with params must leave the default Leidsa rankings of the list untouched."""
    activate(client, LEIDSA)
    sha = leidsa_sha(client)
    lists = client.app.state.lists
    before = lists.lab_data(LEIDSA).rankings.family("decay").copy()
    lab = create_lab(
        client, "Decaimiento 300", lab_config(ranking_params={"half_life": 300})
    ).json()
    client.post(
        f"/api/v1/laboratories/{lab['id']}/runs",
        json={"required_history_sha256": sha},
        headers=ORIGIN,
    )
    assert np.array_equal(lists.lab_data(LEIDSA).rankings.family("decay"), before)


# ---------------------------------------------------------------------- warm-up


def test_leidsa_default_window_starts_after_the_warm_up(client):
    activate(client, LEIDSA)
    options = client.get("/api/v1/laboratories/options").json()
    labels = client.app.state.lists.history(LEIDSA).labels
    assert options["window"]["start"] == labels[500]
    assert options["window"]["start"] != labels[0]
    assert options["window"]["end"] == labels[-1]
    activate(client, "chance_express")
    chance = client.get("/api/v1/laboratories/options").json()
    assert chance["window"] == {"start": "2025-09-02 05:10", "end": "2026-09-25 18:20"}


def test_the_leidsa_file_is_long_enough_for_the_warm_up():
    data = json.loads(LEIDSA_FILE.read_text(encoding="utf-8"))
    assert sum(len(draws) for draws in data["sorteos_por_fecha"].values()) > 500
