import json

import pytest
from test_import_records import profile

from laboratorio.domain.contracts import SettlementMode
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.profile_request_v4 import (
    ProfileRecoveryRequest,
    load_profile_recovery_request,
    serialize_profile_recovery_request,
)
from laboratorio.domain.profile_session import ProfileConditions, ProfileSelector
from laboratorio.domain.profile_staking import ProfileRecoveryLadderStaking


def request():
    game = profile()
    return ProfileRecoveryRequest(
        "profile",
        4,
        "Recovery",
        "a" * 64,
        game.profile_id,
        game.revision,
        profile_sha256(game),
        ProfileConditions(1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(1,)),
        ProfileRecoveryLadderStaking(3, 4, "stop"),
        "all_rows/v1",
    )


def test_v4_recovery_request_roundtrip_explicit_nested_schema():
    """B-DOM-078: recovery v4 serializes explicit nested staking schema."""
    value = request()
    wire = serialize_profile_recovery_request(value)
    data = json.loads(wire)
    assert data["schema_version"] == 4
    assert data["staking"] == {
        "schema_version": 1,
        "target_margin": 3,
        "rounds": 4,
        "end_mode": "stop",
    }
    assert load_profile_recovery_request(wire) == value


@pytest.mark.parametrize("field", ["target_margin", "rounds", "end_mode"])
def test_v4_rejects_missing_recovery_parameters(field):
    """B-DOM-078: recovery v4 requires every recovery parameter."""
    data = json.loads(serialize_profile_recovery_request(request()))
    del data["staking"][field]
    with pytest.raises(ValueError):
        load_profile_recovery_request(json.dumps(data))


@pytest.mark.parametrize("end_mode", ["cycle", "stop"])
def test_v4_accepts_only_explicit_end_modes(end_mode):
    """B-DOM-078: recovery end mode is explicitly cycle or stop."""
    value = request()
    data = json.loads(serialize_profile_recovery_request(value))
    data["staking"]["end_mode"] = end_mode
    assert load_profile_recovery_request(json.dumps(data)).staking.end_mode == end_mode
    data["staking"]["end_mode"] = "other"
    with pytest.raises(ValueError):
        load_profile_recovery_request(json.dumps(data))
