"""Closed profile capability admission and public matrix projection."""

from dataclasses import replace
from typing import cast

import pytest

from laboratorio.api import catalog
from laboratorio.domain import profile_capabilities as registry
from laboratorio.domain.contracts import SettlementMode, legacy_quiniela_80_profile
from laboratorio.domain.profile_session import ProfileConditions, ProfileSelector, ProfileStaking

EXPECTED = {
    "selector": ("static-numbers/v1", "seeded-random/hash-sha256-v1"),
    "staking": (
        "flat-per-number/v1",
        "q80-first-prize-cycling/v1",
        "profile-audaz/v1",
        "profile-recovery-ladder/v1",
    ),
    "entry": ("all_rows/v1",),
    "settlement": ("all", "best"),
}


def test_registry_unique_closed_versions_and_pending_status():
    entries = registry.PROFILE_CAPABILITIES
    assert len({(item.kind, item.identifier) for item in entries}) == len(entries)
    projected = {kind: registry.supported(cast(registry.CapabilityKind, kind)) for kind in EXPECTED}
    assert projected == EXPECTED
    assert {
        (item.kind, item.identifier): (item.schema_version, item.version)
        for item in entries
        if item.status == "supported"
    } == {
        ("selector", "static-numbers/v1"): (1, "v1"),
        ("selector", "seeded-random/hash-sha256-v1"): (1, "hash-sha256-v1"),
        ("staking", "flat-per-number/v1"): (1, "v1"),
        ("staking", "q80-first-prize-cycling/v1"): (2, "v1"),
        ("staking", "profile-audaz/v1"): (3, "v1"),
        ("staking", "profile-recovery-ladder/v1"): (4, "v1"),
        ("entry", "all_rows/v1"): (1, "v1"),
        ("settlement", "all"): (1, "v1"),
        ("settlement", "best"): (1, "v1"),
    }
    assert all(item.schema_version is None for item in entries if item.status == "pending")
    assert {"freq_hist", "blend", "parity"} <= {
        item.identifier for item in entries if item.kind == "selector" and item.status == "pending"
    }
    assert {"fractional-flat", "kelly-binary", "fractional-kelly"} <= {
        item.identifier for item in entries if item.kind == "staking" and item.status == "pending"
    }
    with pytest.raises(ValueError, match="invalid profile capability"):
        registry._validate_registry((*entries, entries[0]))
    with pytest.raises(ValueError, match="invalid profile capability"):
        registry._validate_registry((replace(entries[0], status="pending"),))


def test_exact_admission_rejects_pending_unknown_wrong_kind_and_schema():
    for kind, identifiers in EXPECTED.items():
        axis = cast(registry.CapabilityKind, kind)
        for identifier in identifiers:
            schema = (
                2
                if identifier == "q80-first-prize-cycling/v1"
                else 3
                if identifier == "profile-audaz/v1"
                else 4
                if identifier == "profile-recovery-ladder/v1"
                else 1
            )
            assert registry.require_supported(axis, identifier, schema).identifier == identifier
            wrong_version = 2 if schema == 3 else 3 if schema == 2 else 2
            for version in (0, wrong_version, True, "1"):
                with pytest.raises(ValueError, match="unsupported"):
                    registry.require_supported(axis, identifier, version)
    for kind, identifier in (
        ("selector", "freq_hist"),
        ("selector", "blend"),
        ("selector", "static-numbers/v2"),
        ("staking", "kelly-binary"),
        ("staking", "ladder"),
        ("entry", "conditional-entry"),
        ("settlement", "custom-settlement"),
        ("settlement", "static-numbers/v1"),
        ("selector", "all"),
        ("selector", None),
    ):
        with pytest.raises(ValueError, match="unsupported"):
            registry.require_supported(cast(registry.CapabilityKind, kind), identifier, 1)
    with pytest.raises(ValueError, match="unsupported"):
        ProfileSelector(
            1,
            "seeded-random/hash-sha256-v2",
            1,
            seed=1,
            algorithm_version="hash-sha256-v2",
        )
    with pytest.raises(ValueError, match="algorithm"):
        ProfileSelector(1, EXPECTED["selector"][1], 1, seed=1, algorithm_version="v1")
    with pytest.raises(ValueError, match="unsupported"):
        ProfileStaking(1, "kelly-binary", 1)
    with pytest.raises(ValueError, match="unsupported"):
        ProfileConditions(2, "2025-01-01 05:10", 10, 20, SettlementMode.ALL)


def test_api_matrix_exact_projection_and_no_pending_families(monkeypatch):
    expected = {
        "ready": True,
        "selector_capabilities": list(EXPECTED["selector"]),
        "staking_capabilities": ["flat-per-number/v1"],
        "entry_policies": list(EXPECTED["entry"]),
        "settlements": list(EXPECTED["settlement"]),
        "requires_compatible_dataset": True,
        "audaz_compatibility": {
            "available": False,
            "maximum_compatible_coverage": 0,
            "coverage_rule": "selected coverage must be strictly less than multiplier[0]",
        },
        "recovery_compatibility": {
            "available": False,
            "maximum_compatible_coverage": 0,
            "coverage_rule": "selected coverage must be strictly less than multiplier[0]",
            "parameters": ["target_margin", "rounds", "end_mode"],
        },
    }
    assert catalog.profile_execution(True) == expected
    assert catalog.profile_execution(False) == {**expected, "ready": False}
    # The projection is live, not a second hardcoded matrix fixed at import time.
    monkeypatch.setattr(
        registry,
        "PROFILE_CAPABILITIES",
        (
            *registry.PROFILE_CAPABILITIES,
            registry.ProfileCapability("entry", "test-only/v1", "v1", "supported", 1),
        ),
    )
    assert catalog.profile_execution(True)["entry_policies"] == ["all_rows/v1", "test-only/v1"]
    q80 = catalog.profile_execution(True, legacy_quiniela_80_profile())
    assert "q80-first-prize-cycling/v1" in q80["staking_capabilities"]
    assert "profile-audaz/v1" in q80["staking_capabilities"]
    assert q80["audaz_compatibility"]["maximum_compatible_coverage"] == 50
    assert registry.require_supported("entry", "test-only/v1", 1).identifier == "test-only/v1"


def test_audaz_metadata_reports_profile_specific_coverage_bound():
    profile = legacy_quiniela_80_profile()
    metadata = catalog.profile_execution(True, profile)
    assert metadata["audaz_compatibility"]["maximum_compatible_coverage"] == 50
    assert "profile-audaz/v1" in metadata["staking_capabilities"]
    low_multiplier = profile.model_copy(
        update={
            "multipliers": (
                profile.multipliers[0].model_copy(update={"numerator": 3}),
                *profile.multipliers[1:],
            )
        }
    )
    low = catalog.profile_execution(True, low_multiplier)
    assert low["audaz_compatibility"]["maximum_compatible_coverage"] == 2
