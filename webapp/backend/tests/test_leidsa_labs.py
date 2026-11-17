"""Laboratories and runs on the Quiniela Leidsa list: 3 positions, 5 systems (S3, S5, S6)."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.laboratories import LaboratoryConfig, LaboratoryDefinition
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.domain.runs import RunConfig, run_sessions
from laboratorio.domain.session import Draw
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256, Settings

BASE = "http://localhost:8765"
ORIGIN = {"Origin": BASE, "Content-Type": "application/json"}
LEIDSA = "leidsa_quiniela"
UNAVAILABLE = "No disponible para esta lista"
AVAILABLE_SYSTEMS = {"parity", "cold", "freq_hist", "freq_recent", "decay"}
RANKING_SYSTEMS = {"cold", "freq_hist", "freq_recent", "decay"}


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


def run_body(strategy, **conditions):
    return {
        "name": None,
        "rules": {"positions": 3, "prizes": [60, 8, 4], "minimum_stake": 1},
        "strategy": strategy,
        "conditions": {"capital": 2000, "goal": 2800, "max_draws": 40} | conditions,
        "window": {"start_date": None, "end_date": None},
        "history_sha256": None,
    }


def mix(system, coverage=10):
    return {
        "kind": "mix",
        "components": [{"system": system, "percent": 100}],
        "coverage": coverage,
    }


PARITY = {"kind": "parity", "components": [], "coverage": 50}


def lab_config(system="cold", coverage=10, **changes):
    value = {
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
    return value | changes


def create_lab(client, name, config):
    body = {"name": name, "config": config}
    return client.post("/api/v1/laboratories", json=body, headers=ORIGIN)


def run_lab(client, lab, sha):
    return client.post(
        f"/api/v1/laboratories/{lab['id']}/runs",
        json={"required_history_sha256": sha},
        headers=ORIGIN,
    )


# ------------------------------------------------------------------------------ runs


@pytest.mark.parametrize("strategy", [PARITY] + [mix(s) for s in sorted(RANKING_SYSTEMS)])
def test_leidsa_run_completes_with_three_positions_and_numbers_00_99(client, strategy):
    activate(client, LEIDSA)
    response = client.post("/api/v1/runs", json=run_body(strategy), headers=ORIGIN)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["config"]["rules"] == {"positions": 3, "prizes": [60, 8, 4], "minimum_stake": 1}
    assert run["config"]["history"]["list_id"] == LEIDSA
    window = run["summary"]["window"]
    assert window["draws"] == window["ranked_draws"] == 1381
    assert window["first_label"] == "2023-01-04 20:50"
    assert run["summary"]["totals"]["sessions"] >= 1
    sessions = client.get(f"/api/v1/runs/{run['id']}/sessions").json()["items"]
    assert sessions
    seen_bets = 0
    for session in sessions:
        bets = client.get(f"/api/v1/runs/{run['id']}/sessions/{session['ordinal']}/bets").json()
        for bet in bets["items"]:
            seen_bets += 1
            numbers, results = bet["numbers"], bet["results"]
            assert len(numbers) == len(set(numbers)) == strategy["coverage"]
            assert all(0 <= number <= 99 for number in numbers)
            assert len(results) == 3 and all(0 <= number <= 99 for number in results)
    assert seen_bets > 0


def test_leidsa_run_results_are_deterministic(client):
    activate(client, LEIDSA)
    first = client.post("/api/v1/runs", json=run_body(mix("freq_hist")), headers=ORIGIN).json()
    second = client.post("/api/v1/runs", json=run_body(mix("freq_hist")), headers=ORIGIN).json()
    assert first["summary"]["totals"] == second["summary"]["totals"]
    assert first["summary"]["detail"] == second["summary"]["detail"]


@pytest.mark.parametrize("system", ["transition", "mix", "ensemble", "time", "carry", "notebook"])
def test_ranking_dependent_system_is_rejected_for_leidsa(client, system):
    activate(client, LEIDSA)
    response = client.post("/api/v1/runs", json=run_body(mix(system)), headers=ORIGIN)
    assert response.status_code == 422
    assert UNAVAILABLE in response.json()["detail"]
    assert response.json()["detail"].endswith(f"{UNAVAILABLE}.")


def test_a_mix_with_one_unavailable_component_is_rejected(client):
    activate(client, LEIDSA)
    strategy = {
        "kind": "mix",
        "components": [
            {"system": "cold", "percent": 50},
            {"system": "transition", "percent": 50},
        ],
        "coverage": 5,
    }
    response = client.post("/api/v1/runs", json=run_body(strategy), headers=ORIGIN)
    assert response.status_code == 422
    assert UNAVAILABLE in response.json()["detail"]


def test_leidsa_run_cannot_use_more_positions_than_the_list_has(client):
    activate(client, LEIDSA)
    body = run_body(mix("cold"))
    body["rules"] = {"positions": 5, "prizes": [80, 8, 4, 2, 1], "minimum_stake": 1}
    response = client.post("/api/v1/runs", json=body, headers=ORIGIN)
    assert response.status_code == 422
    assert "3" in response.json()["detail"]


def test_leidsa_run_rejects_an_unknown_history_fingerprint(client):
    activate(client, LEIDSA)
    body = run_body(mix("cold")) | {"history_sha256": HISTORY_SHA256}
    response = client.post("/api/v1/runs", json=body, headers=ORIGIN)
    assert response.status_code == 404


def test_run_options_for_leidsa_offer_exactly_the_five_systems(client):
    activate(client, LEIDSA)
    options = client.get("/api/v1/runs/options").json()
    assert options["list"] == {"id": LEIDSA, "name": "Quiniela Leidsa", "positions": 3}
    assert set(options["systems_available"]) == AVAILABLE_SYSTEMS
    assert len(options["systems_available"]) == 5
    by_id = {item["id"]: item for item in options["systems"]}
    assert {key for key, item in by_id.items() if item["available"]} == RANKING_SYSTEMS
    for key, item in by_id.items():
        if key not in RANKING_SYSTEMS:
            assert item["available"] is False
            assert item["reason"] == UNAVAILABLE
    assert len(by_id) == 13
    assert options["defaults"]["rules"] == {
        "positions": 3,
        "prizes": [60, 8, 4],
        "minimum_stake": 1,
    }
    default_systems = {c["system"] for c in options["defaults"]["strategy"]["components"]}
    assert default_systems <= RANKING_SYSTEMS
    assert options["limits"]["positions"] == {"min": 1, "max": 3}
    assert options["history"]["draws"] == 1381
    assert options["history"]["first_label"] == "2023-01-04 20:50"


def test_run_options_for_chance_keep_their_shape(client):
    options = client.get("/api/v1/runs/options").json()
    assert options["list"]["id"] == "chance_express"
    assert all(set(item) == {"id", "label"} for item in options["systems"])
    assert len(options["systems"]) == 13
    assert len(options["systems_available"]) == 14  # parity + the 13 ranking systems


# ------------------------------------------------------------------------------- labs


def test_lab_options_describe_the_active_list(client):
    activate(client, LEIDSA)
    options = client.get("/api/v1/laboratories/options").json()
    assert options["list"] == {"id": LEIDSA, "name": "Quiniela Leidsa", "positions": 3}
    assert options["prizes"] == [60, 8, 4]
    assert options["window"] == {"start": "2023-01-04 20:50", "end": "2026-11-16 20:50"}
    assert options["history_sha256"] == leidsa_sha(client)
    available = {item["id"] for item in options["systems"] if item["available"]}
    assert available == AVAILABLE_SYSTEMS
    blocked = [item for item in options["systems"] if not item["available"]]
    assert blocked and all(item["reason"] == UNAVAILABLE for item in blocked)

    activate(client, "chance_express")
    chance = client.get("/api/v1/laboratories/options").json()
    assert chance["list"]["id"] == "chance_express"
    assert chance["prizes"] == [80, 8, 4, 2, 1]
    assert chance["window"] == {"start": "2025-09-02 05:10", "end": "2026-09-25 18:20"}
    assert chance["history_sha256"] == HISTORY_SHA256
    assert all(item["available"] for item in chance["systems"])
    assert len(chance["systems"]) == 14


@pytest.mark.parametrize("system", sorted(AVAILABLE_SYSTEMS))
def test_leidsa_lab_is_created_and_runs(client, system):
    activate(client, LEIDSA)
    coverage = 50 if system == "parity" else 10
    created = create_lab(client, f"leidsa {system}", lab_config(system, coverage))
    assert created.status_code == 201, created.text
    lab = created.json()
    assert lab["config"]["list_id"] == LEIDSA
    assert lab["config"]["prizes"] == [60, 8, 4]
    response = run_lab(client, lab, leidsa_sha(client))
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["snapshot"]["provenance"]["list_id"] == LEIDSA
    assert run["snapshot"]["provenance"]["history_origin"] == "list"
    assert run["snapshot"]["provenance"]["history_sha256"] == leidsa_sha(client)
    assert HISTORY_SHA256 not in str(run["snapshot"]["provenance"])
    summary = run["summary"]
    assert summary["eligible_draws"] == 1381
    assert summary["first"] == "2023-01-04 20:50" and summary["last"] == "2026-11-16 20:50"
    assert summary["session_count"] >= 1
    stored = client.get(f"/api/v1/laboratories/{lab['id']}/runs/{run['id']}").json()
    assert stored == run


def test_leidsa_lab_rejects_unavailable_systems_and_wrong_prize_count(client):
    activate(client, LEIDSA)
    blocked = create_lab(client, "x", lab_config("transition", 1))
    assert blocked.status_code == 422
    assert UNAVAILABLE in blocked.json()["detail"]
    five = create_lab(client, "y", lab_config("cold", 10, prizes=[80, 8, 4, 2, 1]))
    assert five.status_code == 422
    two = create_lab(client, "z", lab_config("cold", 10, prizes=[60, 8]))
    assert two.status_code == 422


def test_lab_config_naming_another_list_is_refused(client):
    activate(client, LEIDSA)
    response = create_lab(client, "otra", lab_config("cold", 10, list_id="chance_express"))
    assert response.status_code == 409
    assert "Quiniela Leidsa" in response.json()["detail"]


def test_lab_of_one_list_is_refused_under_the_other_list(client):
    activate(client, LEIDSA)
    leidsa_lab = create_lab(client, "leidsa lab", lab_config("cold", 10)).json()
    sha_leidsa = leidsa_sha(client)
    activate(client, "chance_express")
    chance_lab = create_lab(
        client,
        "chance lab",
        {
            "schema_version": 1,
            "system": "cold",
            "coverage": 10,
            "stake_style": "flat",
            "capital": 2000,
            "goal": 2800,
            "prizes": [80, 8, 4, 2, 1],
            "window_start": "2025-09-02 05:10",
            "window_end": "2025-09-02 06:10",
        },
    ).json()
    assert "list_id" not in chance_lab["config"]

    refused = run_lab(client, leidsa_lab, sha_leidsa)  # Chance is active
    assert refused.status_code == 409
    assert "Quiniela Leidsa" in refused.json()["detail"]
    assert "Loteka Chance Express" in refused.json()["detail"]
    ok = run_lab(client, chance_lab, HISTORY_SHA256)
    assert ok.status_code == 201, ok.text
    assert "list_id" not in ok.json()["snapshot"]["provenance"]
    assert ok.json()["snapshot"]["provenance"]["history_origin"] == "frozen"

    activate(client, LEIDSA)
    refused = run_lab(client, chance_lab, HISTORY_SHA256)
    assert refused.status_code == 409
    assert "Loteka Chance Express" in refused.json()["detail"]
    assert run_lab(client, leidsa_lab, sha_leidsa).status_code == 201


def test_leidsa_lab_requires_the_loaded_history_fingerprint(client):
    activate(client, LEIDSA)
    lab = create_lab(client, "pin", lab_config("cold", 10)).json()
    response = run_lab(client, lab, "0" * 64)
    assert response.status_code == 409


def test_reference_labs_stay_loteka_only_under_leidsa(client):
    activate(client, LEIDSA)
    for path in ("/api/v1/reference-labs", "/api/v1/reference-labs/paridad_50_audaz"):
        assert client.get(path).status_code == 409
    posted = client.post(
        "/api/v1/reference-labs/paridad_50_audaz/runs",
        json={"required_history_sha256": HISTORY_SHA256},
        headers=ORIGIN,
    )
    assert posted.status_code == 409


# -------------------------------------------------------------- domain: snapshot, config


def test_leidsa_config_round_trips_and_chance_mapping_is_unchanged():
    leidsa = LaboratoryConfig.from_mapping(lab_config("cold", 10) | {"list_id": LEIDSA})
    assert leidsa.list_id == LEIDSA
    assert leidsa.to_mapping()["list_id"] == LEIDSA
    assert LaboratoryConfig.from_mapping(leidsa.to_mapping()) == leidsa
    chance = LaboratoryConfig.from_mapping(
        lab_config(
            "cold",
            10,
            prizes=[80, 8, 4, 2, 1],
            window_start="2025-09-02 05:10",
            window_end="2026-09-25 18:20",
        )
    )
    assert chance.list_id == "chance_express"
    assert "list_id" not in chance.to_mapping()
    with pytest.raises(ValueError):
        LaboratoryConfig.from_mapping(
            lab_config(
                "cold",
                10,
                prizes=[80, 8, 4, 2, 1],
                window_start="2025-09-02 05:10",
                window_end="2026-09-25 18:20",
            )
            | {"list_id": "chance_express"}
        )
    with pytest.raises(ValueError):
        LaboratoryConfig.from_mapping(lab_config("cold", 10) | {"list_id": "otra"})


def test_chance_config_validation_is_not_weakened():
    base = lab_config(
        "cold",
        10,
        prizes=[80, 8, 4, 2, 1],
        window_start="2025-09-02 05:10",
        window_end="2026-09-25 18:20",
    )
    LaboratoryConfig.from_mapping(base)
    with pytest.raises(ValueError):
        LaboratoryConfig.from_mapping(base | {"prizes": [60, 8, 4]})
    with pytest.raises(ValueError):
        LaboratoryConfig.from_mapping(base | {"window_start": "2023-01-04 20:50"})


def test_owned_snapshot_for_leidsa_is_strict_and_chance_snapshot_is_unchanged():
    definition = LaboratoryDefinition(
        "6f1d5c2a-8d0b-4f3e-9a55-0f6d4a0f9a11",
        "L",
        LaboratoryConfig.from_mapping(lab_config("cold", 10) | {"list_id": LEIDSA}),
    )
    snapshot = OwnedLaboratoryRunSnapshot(
        definition, "a" * 64, None, list_id=LEIDSA, history_origin="list"
    )
    mapping = snapshot.to_mapping()
    assert mapping["provenance"] == {
        "history_sha256": "a" * 64,
        "history_origin": "list",
        "list_id": LEIDSA,
        "ranking_method": "causal-on-the-fly/v1",
    }
    assert OwnedLaboratoryRunSnapshot.from_mapping(mapping).to_mapping() == mapping
    for tamper in (
        lambda m: m["provenance"].update(history_origin="frozen"),
        lambda m: m["provenance"].update(rankings_sha256="b" * 64),
        lambda m: m["provenance"].pop("list_id"),
        lambda m: m["provenance"].update(list_id="chance_express"),
        lambda m: m["provenance"].update(ranking_method="otro"),
    ):
        broken = OwnedLaboratoryRunSnapshot.from_mapping(mapping).to_mapping()
        tamper(broken)
        with pytest.raises(ValueError):
            OwnedLaboratoryRunSnapshot.from_mapping(broken)
    chance = OwnedLaboratoryRunSnapshot(
        LaboratoryDefinition(
            "6f1d5c2a-8d0b-4f3e-9a55-0f6d4a0f9a12",
            "C",
            LaboratoryConfig.from_mapping(
                lab_config(
                    "cold",
                    10,
                    prizes=[80, 8, 4, 2, 1],
                    window_start="2025-09-02 05:10",
                    window_end="2026-09-25 18:20",
                )
            ),
        ),
        HISTORY_SHA256,
        RANKINGS_SHA256,
    ).to_mapping()
    assert chance["provenance"] == {
        "history_sha256": HISTORY_SHA256,
        "rankings_sha256": RANKINGS_SHA256,
        "history_origin": "frozen",
    }


def test_run_engine_accepts_three_wide_draws_only_when_told_so():
    config = RunConfig(100, 150, 2, 3, (60, 8, 4), 1, 5)
    order = (1, 2, 3)
    rows = [Draw(f"d{i}", i, (1, 50, 51), order) for i in range(3)]
    result = run_sessions(config, rows, results_per_draw=3)
    assert result.totals.sessions >= 1
    with pytest.raises(ValueError):
        run_sessions(config, rows)  # default width stays five
    with pytest.raises(ValueError):
        run_sessions(RunConfig(100, 150, 2, 4, (60, 8, 4, 2), 1, 5), rows, results_per_draw=3)
