"""Independent Q1 probes promoted to permanent public-boundary regressions."""

import json
from collections.abc import Mapping, MutableMapping
from copy import deepcopy
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_configurable_laboratory_values import config
from test_game_profiles_v2_api import BASE_URL, HEADERS, ROOT, make_app, public_state, rules

from laboratorio.domain.configurable_laboratories import (
    ConfigurableRunSnapshot,
    create_definition,
    create_run_snapshot,
)
from laboratorio.domain.contracts import MAX_MONEY
from laboratorio.domain.quiniela_profiles import QuinielaRules
from laboratorio.storage.game_profile_store import create_game_profile


def test_exact_rational_equality_and_money_ceiling():
    value = rules(numbers=4, positions=2)
    value.update(
        order_matters=False,
        multipliers=[{"numerator": 2, "denominator": 2}, {"numerator": 3, "denominator": 3}],
    )
    assert QuinielaRules.from_mapping(value).to_mapping() == value
    value.update(max_exposure=MAX_MONEY, payout_mode="best")
    assert QuinielaRules.from_mapping(value).max_exposure == MAX_MONEY
    with pytest.raises(ValueError):
        QuinielaRules.from_mapping(value | {"payout_mode": "all"})
    with pytest.raises(ValueError):
        QuinielaRules.from_mapping(
            value | {"multipliers": [{"numerator": 1, "denominator": 3}] * 2}
        )


def test_snapshot_rejects_nested_profile_and_strategy_changes():
    mapped = create_run_snapshot(create_definition("Lab", config()), "independent/v2").to_mapping()
    for component in ("profile", "strategy"):
        bad = deepcopy(mapped)
        if component == "profile":
            bad["definition"]["config"]["profile"]["name"] = "Altered"
        else:
            bad["definition"]["config"]["strategy"]["stake"]["parameters"]["per_number"] = 20
        with pytest.raises(ValueError):
            ConfigurableRunSnapshot.from_mapping(bad)
    assert ConfigurableRunSnapshot.from_mapping(mapped).to_mapping() == mapped


def test_nested_parameters_are_detached_and_bounded():
    payload = config()
    payload["strategy"]["selection"]["parameters"] = {"nested": [{"n": 1}]}
    definition = create_definition("Lab", payload)
    payload["strategy"]["selection"]["parameters"]["nested"][0]["n"] = 2
    params = definition.config.strategy.selection.parameters
    nested = cast(tuple[Mapping[str, int], ...], params["nested"])
    assert nested[0]["n"] == 1
    # Deliberately attempt a forbidden runtime write without a broad type ignore.
    with pytest.raises(TypeError):
        cast(MutableMapping[str, int], nested[0])["n"] = 3
    assert nested[0]["n"] == 1
    payload["strategy"]["selection"]["parameters"] = {"x": list(range(1001))}
    with pytest.raises(ValueError):
        create_definition("Lab", payload)


@pytest.mark.parametrize(
    "body",
    [
        bytes([255]),
        b'{"name":NaN,"rules":{}}',
        b'{"name":"x","rules":{"schema_version":2,"schema_version":2}}',
        rb'{"name":"\ud800","rules":' + json.dumps(rules()).encode() + b"}",
    ],
)
def test_malformed_public_posts_preserve_all_public_counters(tmp_path, lab_data, body):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        before = public_state(client)
        response = client.post(ROOT, content=body, headers=HEADERS)
        assert response.status_code == 422, response.text
        assert public_state(client) == before


def test_constructed_model_cannot_bypass_store_revalidation(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        before = public_state(client)
        poisoned = QuinielaRules.from_mapping(rules()).model_copy(update={"minimum_stake": True})
        with pytest.raises(ValueError):
            create_game_profile(app.state.repo, "Poisoned", poisoned)
        assert public_state(client) == before
