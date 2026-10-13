"""Structural snapshots are immutable; compilation/admission remain separate."""

import hashlib
import json
from copy import deepcopy
from uuid import uuid4

import pytest

from laboratorio.domain.configurable_laboratories import (
    ConfigurableLaboratoryDefinition,
    ConfigurableRunSnapshot,
    create_definition,
    create_run_snapshot,
)
from laboratorio.domain.quiniela_profiles import create_profile


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def config():
    profile = create_profile(
        "Juego 4/2",
        {
            "schema_version": 2,
            "universe": [0, 1, 2, 3],
            "display_width": 1,
            "positions": 2,
            "played_positions": [0, 1],
            "order_matters": True,
            "allows_repeats": False,
            "multipliers": [{"numerator": 1, "denominator": 1}] * 2,
            "payout_mode": "all",
            "currency": "DOP",
            "scale": 0,
            "minimum_stake": 10,
            "stake_increment": 10,
            "maximum_stake": 100,
            "max_coverage": 4,
            "max_exposure": 400,
        },
    ).to_mapping()

    def block(role, kind, parameters):
        return {
            "schema_version": 2,
            "role": role,
            "kind": kind,
            "version": 1,
            "parameters": parameters,
        }

    return {
        "schema_version": 2,
        "profile": profile,
        "source": {
            "schema_version": 2,
            "id": str(uuid4()),
            "sha256": "a" * 64,
            "profile_sha256": digest(profile),
            "origin": "imported",
            "raw_sha256": "b" * 64,
            "rankings_sha256": None,
        },
        "strategy": {
            "schema_version": 2,
            "selection": block("selection", "manual", {"numbers": [0, 1]}),
            "stake": block("stake", "fixed", {"per_number": 10}),
            "close": block("close", "goal-or-ruin", {}),
        },
        "conditions": {
            "schema_version": 2,
            "capital": 1000,
            "goal": 1500,
            "window": {
                "schema_version": 2,
                "start": "2025-01-01T00:00:00Z",
                "end": "2025-01-02T00:00:00Z",
            },
        },
    }


def test_definition_and_run_snapshot_round_trip_detach_all_mutable_input():
    payload = config()
    definition = create_definition(" Laboratorio ", payload)
    original = deepcopy(definition.to_mapping())
    payload["strategy"]["selection"]["parameters"]["numbers"].append(2)
    payload["profile"]["rules"]["universe"].append(4)
    assert definition.to_mapping() == original
    assert definition.name == "Laboratorio"
    assert ConfigurableLaboratoryDefinition.from_mapping(original) == definition
    snapshot = create_run_snapshot(definition, "quiniela-replay/v2")
    mapped = snapshot.to_mapping()
    assert mapped["kind"] == "configurable_quiniela_run"
    assert mapped["profile_sha256"] == digest(original["config"]["profile"])
    assert mapped["strategy_sha256"] == digest(original["config"]["strategy"])
    assert mapped["history_sha256"] == "a" * 64
    assert ConfigurableRunSnapshot.from_mapping(mapped).to_mapping() == mapped
    with pytest.raises((AttributeError, TypeError)):
        definition.__setattr__("name", "changed")
    assert definition.to_mapping() == original


@pytest.mark.parametrize(
    "component,field,value",
    [
        (None, "schema_version", True),
        (None, "schema_version", 2.0),
        (None, "extra", "plugin"),
        ("source", "id", "not-a-uuid"),
        ("source", "profile_sha256", "c" * 64),
        ("source", "sha256", "A" * 64),
        ("source", "rankings_sha256", "d" * 64),
        ("conditions", "capital", True),
        ("conditions", "capital", 0),
        ("conditions", "goal", 1000),
        ("conditions", "goal", 10**12 + 1),
    ],
)
def test_invalid_structural_config_is_rejected_without_mutating_input(component, field, value):
    payload = config()
    target = payload if component is None else payload[component]
    target[field] = value
    original = deepcopy(payload)
    with pytest.raises((TypeError, ValueError)):
        create_definition("Lab", payload)
    assert payload == original


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "exec"),
        ("role", "stake"),
        ("version", 2),
        ("version", True),
        ("parameters", {"fraction": 1.5}),
    ],
)
def test_unknown_blocks_and_lossy_parameters_are_structurally_rejected(field, value):
    payload = config()
    payload["strategy"]["selection"][field] = value
    original = deepcopy(payload)
    with pytest.raises((TypeError, ValueError)):
        create_definition("Lab", payload)
    assert payload == original


def test_snapshot_hash_and_extra_field_tampering_are_rejected():
    snapshot = create_run_snapshot(create_definition("Lab", config()), "quiniela-replay/v2")
    mapped = snapshot.to_mapping()
    for change in (
        {"profile_sha256": "f" * 64},
        {"strategy_sha256": "f" * 64},
        {"history_sha256": "f" * 64},
        {"partial_trace": True},
    ):
        with pytest.raises((TypeError, ValueError)):
            ConfigurableRunSnapshot.from_mapping(mapped | change)
    assert snapshot.to_mapping() == mapped
