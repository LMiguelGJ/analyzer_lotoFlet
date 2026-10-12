import uuid
from dataclasses import FrozenInstanceError, replace

import pytest

from laboratorio.domain.laboratories import (
    FROZEN_HISTORY_SHA256,
    MAX_SAFE_INTEGER,
    LaboratoryConfig,
    LaboratoryDefinition,
    create_laboratory_definition,
    initial_laboratory_definitions,
)
from laboratorio.domain.reference_labs import REFERENCE_LABS
from laboratorio.settings import HISTORY_SHA256

DEFAULT = {
    "system": "transition",
    "coverage": 1,
    "stake_style": "bold",
    "capital": 2000,
    "goal": 2800,
    "prizes": (80, 8, 4, 2, 1),
    "window_start": "2025-09-02 05:10",
    "window_end": "2026-09-25 18:20",
}


def config(**changes):
    return LaboratoryConfig(**(DEFAULT | changes))


def test_initial_factory_is_fourteen_ordered_deterministic_fidelity_seeds():
    first = initial_laboratory_definitions()
    second = initial_laboratory_definitions()

    assert len(first) == len(REFERENCE_LABS) == 14
    assert [item.reference_id for item in first] == [lab.lab_id for lab in REFERENCE_LABS]
    assert [item.id for item in first] == [item.id for item in second]
    assert len({item.id for item in first}) == 14
    for definition, reference in zip(first, REFERENCE_LABS, strict=True):
        assert definition.name == reference.lab_id
        assert definition.to_reference_lab() == definition.to_reference_lab()
        replay_contract = definition.to_reference_lab()
        assert (
            replay_contract.system,
            replay_contract.coverage,
            replay_contract.stake_style,
            replay_contract.selection_kind,
            replay_contract.capital,
            replay_contract.goal,
            replay_contract.prizes,
            replay_contract.window_start,
            replay_contract.window_end,
        ) == (
            reference.system,
            reference.coverage,
            reference.stake_style,
            reference.selection_kind,
            reference.capital,
            reference.goal,
            reference.prizes,
            reference.window_start,
            reference.window_end,
        )


def test_manual_recreation_gets_new_identity_and_names_are_casefold_unique():
    lab_config = config()
    first = create_laboratory_definition("Prueba", lab_config)
    recreated = create_laboratory_definition("Prueba", lab_config)

    assert first.id != recreated.id
    assert first.config == recreated.config
    with pytest.raises(ValueError, match="unique"):
        create_laboratory_definition("prueba", lab_config, existing_names=(first.name,))


@pytest.mark.parametrize(
    "changes",
    [
        {"system": "invented"},
        {"system": "parity", "coverage": 49},
        {"coverage": True},
        {"coverage": 1.0},
        {"coverage": 51},
        {"stake_style": "unknown"},
        {"capital": True},
        {"capital": 2000.0},
        {"capital": 0},
        {"capital": 1, "coverage": 2},
        {"goal": False},
        {"goal": 2000},
        {"prizes": (80, 8, 4, 2, True)},
        {"prizes": (80.0, 8, 4, 2, 1)},
        {"prizes": (80, 8, 4, 2)},
        {"prizes": (1, 8, 4, 2, 1)},
        {"stake_style": "ladder", "coverage": 25, "prizes": (25, 8, 4, 2, 1)},
        {"stake_style": "ladder", "coverage": 25, "capital": 25, "prizes": (26, 8, 4, 2, 1)},
        {"window_start": "2025-02-30 05:10"},
        {"window_start": "2025-09-02 5:10"},
        {"window_start": "2026-09-25 18:20", "window_end": "2025-09-02 05:10"},
        {"window_start": "2025-09-01 23:59"},
        {"window_end": "2026-09-25 18:21"},
        {"goal": 10**15},
        {"prizes": (10**15, 8, 4, 2, 1)},
    ],
)
def test_rejects_invalid_configuration_values(changes):
    with pytest.raises(ValueError):
        config(**changes)


def test_parity_selection_is_derived_and_valid_flat_low_prizes_are_allowed():
    parity = config(system="parity", coverage=50, stake_style="flat", prizes=(1, 1, 1, 1, 1))
    assert parity.selection_kind == "parity"
    assert config(stake_style="flat", prizes=(1, 1, 1, 1, 1)).prizes == (1, 1, 1, 1, 1)


def test_financial_bound_respects_safe_integer_ceiling():
    assert FROZEN_HISTORY_SHA256 == HISTORY_SHA256
    assert MAX_SAFE_INTEGER == 2**53 - 1
    # With a smaller goal and tiny payouts the source-wide aggregate remains safe.
    assert config(capital=1, goal=2, prizes=(1, 1, 1, 1, 1), stake_style="flat")
    # The bound fits SQLite int64 but not JavaScript's exact integer range.
    aggregate_bound = 105_426 * 2**34 * 5
    assert 2**53 - 1 < aggregate_bound < 2**63 - 1
    with pytest.raises(ValueError, match="safe SQLite/browser"):
        config(capital=1, goal=2**34, prizes=(1, 1, 1, 1, 1), stake_style="flat")


def test_definition_identity_name_and_nested_config_are_immutable_and_validated():
    lab_config = config()
    identity = str(uuid.uuid4())
    definition = LaboratoryDefinition(identity, "Mi laboratorio", lab_config)
    config_field, definition_field = "prizes", "name"
    with pytest.raises(FrozenInstanceError):
        setattr(lab_config, config_field, (1, 2, 3, 4, 5))
    with pytest.raises(FrozenInstanceError):
        setattr(definition, definition_field, "Otro")
    with pytest.raises(ValueError, match="canonical"):
        LaboratoryDefinition(identity.upper(), "Mi laboratorio", lab_config)
    for name in ("", " espacio ", "x\ny", "x" * 121):
        with pytest.raises(ValueError):
            LaboratoryDefinition(str(uuid.uuid4()), name, lab_config)


def test_snapshot_v1_round_trip_has_exact_keys_and_independent_mutable_copies():
    definition = create_laboratory_definition("Instantánea", config())
    snapshot = definition.to_mapping()
    assert set(snapshot) == {"schema_version", "id", "name", "reference_id", "config"}
    assert set(snapshot["config"]) == {
        "schema_version",
        "system",
        "coverage",
        "stake_style",
        "capital",
        "goal",
        "prizes",
        "window_start",
        "window_end",
    }
    restored = LaboratoryDefinition.from_mapping(snapshot)
    assert restored == definition
    snapshot["config"]["prizes"][0] = 999
    assert definition.config.prizes == (80, 8, 4, 2, 1)
    with pytest.raises(ValueError):
        LaboratoryDefinition.from_mapping(snapshot | {"unexpected": 1})
    with pytest.raises(ValueError):
        LaboratoryDefinition.from_mapping(snapshot | {"schema_version": 2})
    with pytest.raises(ValueError):
        LaboratoryConfig.from_mapping(
            definition.config.to_mapping() | {"selection_kind": "ranking"}
        )


def test_config_can_be_replaced_only_by_constructing_another_valid_snapshot():
    original = config()
    updated = replace(original, goal=3000)
    assert original.goal == 2800
    assert updated.goal == 3000
