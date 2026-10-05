import json

import pytest
from test_import_records import profile

from laboratorio.domain.contracts import SettlementMode
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.profile_request_v2 import load_profile_cycling_request
from laboratorio.domain.profile_request_v3 import (
    ProfileAudazRequest,
    load_profile_audaz_request,
    serialize_profile_audaz_request,
)
from laboratorio.domain.profile_session import ProfileConditions, ProfileSelector
from laboratorio.domain.profile_staking import ProfileAudazStaking


def make_request():
    game = profile()
    return ProfileAudazRequest(
        "profile", 3, "Audaz test", "a" * 64, game.profile_id, game.revision,
        profile_sha256(game),
        ProfileConditions(1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(1,)),
        ProfileAudazStaking(), "all_rows/v1",
    )


def test_schema3_roundtrip_is_distinct_from_v1_and_v2():
    """B-DOM-077: Audaz v3 has distinct schema and never infers a stake."""
    request = make_request()
    wire = serialize_profile_audaz_request(request)
    assert json.loads(wire)["schema_version"] == 3
    assert load_profile_audaz_request(wire) == request
    with pytest.raises(ValueError):
        load_profile_cycling_request(wire)
    with pytest.raises(ValueError):
        load_profile_audaz_request(wire.replace('"schema_version":3', '"schema_version":2'))


def test_v3_does_not_infer_stake_and_rejects_unknown_fields_and_types():
    """B-DOM-077: v3 rejects inferred stake, unknown fields, and malformed types."""
    request = make_request()
    body = json.loads(serialize_profile_audaz_request(request))
    assert "per_number_stake" not in body["staking"]
    bad = json.loads(serialize_profile_audaz_request(request))
    bad["staking"]["per_number_stake"] = 1
    with pytest.raises(ValueError):
        load_profile_audaz_request(json.dumps(bad))
    bad = json.loads(serialize_profile_audaz_request(request))
    bad["schema_version"] = True
    with pytest.raises(ValueError):
        load_profile_audaz_request(json.dumps(bad))
