from dataclasses import FrozenInstanceError

import pytest

from laboratorio.domain.laboratories import (
    LaboratoryConfig,
    LaboratoryDefinition,
    create_laboratory_definition,
    initial_laboratory_definitions,
)
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot

HISTORY_SHA256 = "a" * 64
RANKINGS_SHA256 = "b" * 64
DEFAULT_CONFIG = {
    "system": "transition",
    "coverage": 1,
    "stake_style": "bold",
    "capital": 2000,
    "goal": 2800,
    "prizes": (80, 8, 4, 2, 1),
    "window_start": "2025-09-02 05:10",
    "window_end": "2026-09-25 18:20",
}


def snapshot(definition=None, **changes):
    definition = definition or create_laboratory_definition(
        "Owned run", LaboratoryConfig(**DEFAULT_CONFIG)
    )
    return OwnedLaboratoryRunSnapshot(
        definition,
        changes.get("history_sha256", HISTORY_SHA256),
        changes.get("rankings_sha256", RANKINGS_SHA256),
    )


def test_manual_and_seed_definitions_round_trip_through_owned_namespace():
    manual = create_laboratory_definition("Manual snapshot", LaboratoryConfig(**DEFAULT_CONFIG))
    for definition in (manual, initial_laboratory_definitions()[0]):
        value = snapshot(definition).to_mapping()
        assert value == {
            "schema_version": 1,
            "kind": "owned_laboratory_run",
            "definition": definition.to_mapping(),
            "provenance": {
                "history_sha256": HISTORY_SHA256,
                "rankings_sha256": RANKINGS_SHA256,
                "history_origin": "frozen",
            },
        }
        restored = OwnedLaboratoryRunSnapshot.from_mapping(value)
        assert restored.definition == definition
        assert restored.history_sha256 == HISTORY_SHA256
        assert restored.rankings_sha256 == RANKINGS_SHA256
        assert restored.to_mapping() == value


def test_all_fourteen_seed_definition_dtos_round_trip_without_execution():
    definitions = initial_laboratory_definitions()
    assert len(definitions) == 14
    assert [
        OwnedLaboratoryRunSnapshot.from_mapping(snapshot(item).to_mapping()).definition
        for item in definitions
    ] == list(definitions)


def test_mapping_copies_and_frozen_snapshot_prevent_alias_mutation():
    definition = create_laboratory_definition(
        "Immutable snapshot", LaboratoryConfig(**DEFAULT_CONFIG)
    )
    value = snapshot(definition).to_mapping()
    value["definition"]["config"]["prizes"][0] = 999
    value["provenance"]["history_sha256"] = RANKINGS_SHA256
    assert definition.config.prizes == DEFAULT_CONFIG["prizes"]
    assert snapshot(definition).history_sha256 == HISTORY_SHA256

    model = snapshot(definition)
    with pytest.raises(FrozenInstanceError):
        model.history_sha256 = RANKINGS_SHA256
    second = model.to_mapping()
    second["definition"]["config"]["prizes"].append(1000)
    assert model.definition.config.prizes == DEFAULT_CONFIG["prizes"]
    assert model.to_mapping()["definition"]["config"]["prizes"] == list(DEFAULT_CONFIG["prizes"])


def test_custom_validated_definition_round_trip_preserves_financial_and_window_inputs():
    config = LaboratoryConfig(
        system="transition",
        coverage=2,
        stake_style="flat",
        capital=300,
        goal=900,
        prizes=(12, 7, 4, 2, 1),
        window_start="2025-10-01 00:00",
        window_end="2026-08-31 23:59",
    )
    definition = LaboratoryDefinition(
        "f3e59ac7-a21c-4ea6-bbe2-5df8d0566d24", "Custom financial", config
    )
    restored = OwnedLaboratoryRunSnapshot.from_mapping(snapshot(definition).to_mapping())
    assert restored.definition.config == config
    assert restored.definition.reference_id is None


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.update(schema_version=True),
        lambda value: value.update(schema_version=1.0),
        lambda value: value.update(schema_version=2),
        lambda value: value.update(kind="reference_lab_run"),
        lambda value: value.update(kind=1),
        lambda value: value.update(extra=True),
        lambda value: value.pop("definition"),
        lambda value: value.update(config=value["definition"]["config"]),
        lambda value: value["provenance"].update(extra=True),
        lambda value: value["provenance"].pop("history_origin"),
        lambda value: value["provenance"].update(history_origin="live"),
        lambda value: value["provenance"].update(history_origin=1),
        lambda value: value["provenance"].update(history_sha256="A" * 64),
        lambda value: value["provenance"].update(history_sha256="a" * 63),
        lambda value: value["provenance"].update(rankings_sha256="g" * 64),
        lambda value: value["provenance"].update(rankings_sha256=123),
        lambda value: value["definition"].update(schema_version=True),
        lambda value: value["definition"].update(name=" padded "),
        lambda value: value["definition"]["config"].update(capital=True),
        lambda value: value["definition"]["config"].update(window_start="2025-09-02 5:10"),
    ],
)
def test_rejects_wrong_or_malformed_owned_snapshot_shape(change):
    value = snapshot().to_mapping()
    change(value)
    with pytest.raises((TypeError, ValueError)):
        OwnedLaboratoryRunSnapshot.from_mapping(value)


def test_rejects_non_mapping_and_legacy_reference_metadata_shape():
    with pytest.raises((TypeError, ValueError)):
        OwnedLaboratoryRunSnapshot.from_mapping(None)
    with pytest.raises((TypeError, ValueError)):
        OwnedLaboratoryRunSnapshot.from_mapping(
            {
                "schema_version": 1,
                "config": DEFAULT_CONFIG,
                "provenance": {
                    "history_sha256": HISTORY_SHA256,
                    "rankings_sha256": RANKINGS_SHA256,
                    "history_origin": "frozen",
                },
            }
        )


def test_constructor_requires_exact_validated_definition_type():
    class ForgedDefinition(LaboratoryDefinition):
        def to_mapping(self):
            return {}

    with pytest.raises(ValueError):
        OwnedLaboratoryRunSnapshot(
            ForgedDefinition.__new__(ForgedDefinition), HISTORY_SHA256, RANKINGS_SHA256
        )


@pytest.mark.parametrize("digest", [True, 1, "A" * 64, "g" * 64, "a" * 63])
def test_constructor_rejects_noncanonical_source_pins(digest):
    definition = initial_laboratory_definitions()[0]
    with pytest.raises(ValueError):
        OwnedLaboratoryRunSnapshot(definition, digest, RANKINGS_SHA256)
    with pytest.raises(ValueError):
        OwnedLaboratoryRunSnapshot(definition, HISTORY_SHA256, digest)


def test_constructor_allows_equal_source_pins_without_inventing_a_difference_rule():
    definition = initial_laboratory_definitions()[0]
    model = OwnedLaboratoryRunSnapshot(definition, HISTORY_SHA256, HISTORY_SHA256)
    assert model.history_sha256 == model.rankings_sha256
