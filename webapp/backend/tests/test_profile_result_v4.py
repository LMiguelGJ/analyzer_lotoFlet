import json

import pytest

from laboratorio.domain.profile_result import load_profile_result
from laboratorio.domain.profile_result_v2 import (
    ProfileCyclingResult,
    load_profile_cycling_result,
    serialize_profile_cycling_result,
)
from laboratorio.domain.profile_result_v3 import (
    ProfileAudazResult,
    load_profile_audaz_result,
    serialize_profile_audaz_result,
)
from laboratorio.domain.profile_result_v4 import (
    ProfileRecoveryResult,
    load_profile_recovery_result,
    serialize_profile_recovery_result,
)
from laboratorio.domain.profile_session import ProfileOutcome, ProfileSessionResult


def round_limit():
    return ProfileSessionResult(
        1,
        "sample",
        1,
        ProfileOutcome.LIMIT,
        ("recovery_round_limit",),
        1,
        0,
        0,
        0,
        80,
        (),
    )


def test_v4_collision_roundtrips_but_older_wires_refuse_it():
    session = round_limit()
    result = ProfileRecoveryResult("profile", 4, session)
    wire = serialize_profile_recovery_result(result)
    assert json.loads(wire)["collisions"] == ["recovery_round_limit"]
    assert load_profile_recovery_result(wire) == result
    with pytest.raises(ValueError, match="collisions"):
        load_profile_result(wire.replace('"schema_version":4', '"schema_version":1'))
    cycling = ProfileCyclingResult("profile", 2, session)
    with pytest.raises(ValueError, match="collisions"):
        serialize_profile_cycling_result(cycling)
    with pytest.raises(ValueError):
        load_profile_cycling_result(wire.replace('"schema_version":4', '"schema_version":2'))
    audaz = ProfileAudazResult("profile", 3, session)
    with pytest.raises(ValueError, match="audaz result"):
        serialize_profile_audaz_result(audaz)
    with pytest.raises(ValueError):
        load_profile_audaz_result(wire.replace('"schema_version":4', '"schema_version":3'))


def test_v4_rejects_unknown_versions_and_collision_values():
    wire = serialize_profile_recovery_result(ProfileRecoveryResult("profile", 4, round_limit()))
    raw = json.loads(wire)
    raw["schema_version"] = 5
    with pytest.raises(ValueError, match="version"):
        load_profile_recovery_result(json.dumps(raw))
    raw["schema_version"] = 4
    raw["collisions"] = ["invented"]
    with pytest.raises(ValueError, match="collisions"):
        load_profile_recovery_result(json.dumps(raw))
