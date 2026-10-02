"""Versioned Q80 request boundaries keep flat v1 bytes and admission distinct."""

import json
from dataclasses import replace
from typing import Any

import pytest

from laboratorio.domain.contracts import SettlementMode, legacy_quiniela_80_profile
from laboratorio.domain.profile_request import (
    ProfileExperimentRequest,
    load_profile_request,
    profile_sha256,
    serialize_profile_request,
)
from laboratorio.domain.profile_request_v2 import (
    ProfileCyclingRequest,
    load_profile_cycling_request,
    serialize_profile_cycling_request,
)
from laboratorio.domain.profile_session import (
    ProfileConditions,
    ProfileSelector,
    ProfileStaking,
    Q80CyclingStaking,
)

pytest_plugins = ("test_profile_api",)
START = "2025-01-01 05:10"


def request(**changes):
    profile = legacy_quiniela_80_profile()
    values: dict[str, Any] = dict(
        kind="profile",
        schema_version=2,
        name="Ciclo ñ",
        dataset_sha256="a" * 64,
        profile_id=profile.profile_id,
        profile_revision=profile.revision,
        profile_sha256=profile_sha256(profile),
        conditions=ProfileConditions(1, START, 2000, 10000, SettlementMode.ALL),
        selector=ProfileSelector(1, "static-numbers/v1", 50, numbers=tuple(range(50, 100))),
        staking=Q80CyclingStaking(1, "q80-first-prize-cycling/v1"),
        entry_policy="all_rows/v1",
    )
    values.update(changes)
    return ProfileCyclingRequest(**values)


def wire():
    return json.loads(serialize_profile_cycling_request(request()))


def test_exact_private_roundtrip_and_v1_bytes_unchanged():
    source = request()
    text = serialize_profile_cycling_request(source)
    assert load_profile_cycling_request(text) == source
    assert text == json.dumps(
        json.loads(text), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert json.loads(text)["staking"] == {
        "capability": "q80-first-prize-cycling/v1",
        "schema_version": 1,
    }
    assert json.loads(text)["conditions"]["schema_version"] == 1
    assert json.loads(text)["selector"]["schema_version"] == 1
    with pytest.raises(ValueError):
        load_profile_request(text)  # the v1 parser must still reject v2 bytes
    with pytest.raises(TypeError):
        serialize_profile_request(source)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ProfileExperimentRequest(
            "profile",
            1,
            source.name,
            source.dataset_sha256,
            source.profile_id,
            source.profile_revision,
            source.profile_sha256,
            source.conditions,
            source.selector,
            source.staking,
            source.entry_policy,  # type: ignore[arg-type]
        )
    flat = ProfileExperimentRequest(
        "profile",
        1,
        "Flat",
        source.dataset_sha256,
        source.profile_id,
        source.profile_revision,
        source.profile_sha256,
        source.conditions,
        source.selector,
        ProfileStaking(1, "flat-per-number/v1", 1),
        "all_rows/v1",
    )
    flat_text = serialize_profile_request(flat)
    assert load_profile_request(flat_text) == flat
    assert json.loads(flat_text)["staking"] == {
        "capability": "flat-per-number/v1",
        "per_number_stake": 1,
        "schema_version": 1,
    }
    with pytest.raises(ValueError):
        load_profile_cycling_request(flat_text)
    with pytest.raises(TypeError):
        serialize_profile_cycling_request(flat)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "path,bad",
    [
        (("kind",), "legacy"),
        (("schema_version",), 1),
        (("schema_version",), True),
        (("name",), " "),
        (("name",), "\ud800"),
        (("dataset_sha256",), "A" * 64),
        (("profile_sha256",), "x" * 64),
        (("profile_id",), "Bad ID"),
        (("profile_revision",), 1.0),
        (("entry_policy",), "conditional-entry/v1"),
        (("conditions", "schema_version"), 2),
        (("conditions", "capital"), True),
        (("conditions", "settlement"), "unknown"),
        (("selector", "schema_version"), 2),
        (("selector", "numbers", 0), True),
        (("staking", "schema_version"), 2),
        (("staking", "capability"), "flat-per-number/v1"),
        (("staking", "per_number_stake"), 1),
    ],
)
def test_malformed_wire_rejected(path, bad):
    value = wire()
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad
    with pytest.raises((ValueError, TypeError)):
        load_profile_cycling_request(json.dumps(value))


def test_public_profile_post_dispatches_v2_then_rejects_unregistered_binding(api_setup):
    client, _, _ = api_setup
    response = client.post(
        "/api/v1/experiments/profiles",
        content=serialize_profile_cycling_request(request()),
        headers={"content-type": "application/json", "Origin": "http://localhost:8765"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "profile admission failed: incompatible binding or stake"


def test_no_missing_or_extra_fields_and_recursive_duplicate_and_non_json_numbers():
    value = wire()
    for section, key in (
        (None, "entry_policy"),
        ("conditions", "goal"),
        ("selector", "seed"),
        ("staking", "capability"),
    ):
        copy = json.loads(json.dumps(value))
        (copy if section is None else copy[section]).pop(key)
        with pytest.raises(ValueError):
            load_profile_cycling_request(json.dumps(copy))
    for text in (
        json.dumps(value)[:-1] + ',"name":"duplicate"}',
        json.dumps(value).replace('"coverage": 50', '"coverage": 50, "coverage": 50'),
        json.dumps(value).replace(
            '"capability": "q80-first-prize-cycling/v1"',
            '"capability": "q80-first-prize-cycling/v1", "capability": "other"',
        ),
        json.dumps({**value, "conditions": {**value["conditions"], "capital": float("nan")}}),
    ):
        with pytest.raises(ValueError):
            load_profile_cycling_request(text)
    with pytest.raises(ValueError):
        load_profile_cycling_request(json.dumps({**value, "surprise": 1}))
    with pytest.raises(ValueError):
        serialize_profile_cycling_request(replace(request(), schema_version=True))
    forged = request()
    object.__setattr__(forged.staking, "capability", "other")
    with pytest.raises(ValueError):
        serialize_profile_cycling_request(forged)
