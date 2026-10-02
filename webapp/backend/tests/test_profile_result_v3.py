import json

import pytest
from test_import_records import profile

from laboratorio.domain.contracts import GameProfile, SettlementMode
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.profile_request_v3 import ProfileAudazRequest
from laboratorio.domain.profile_result_v3 import (
    ProfileAudazResult,
    load_profile_audaz_result,
    serialize_profile_audaz_result,
    validate_profile_audaz_result,
)
from laboratorio.domain.profile_session import (
    ProfileConditions,
    ProfileDraw,
    ProfileSelector,
    _minute,
    run_profile_session,
)
from laboratorio.domain.profile_staking import ProfileAudazStaking


def setup_case():
    game = profile()
    request = ProfileAudazRequest(
        "profile", 3, "Audaz", "a" * 64, game.profile_id, game.revision,
        profile_sha256(game),
        ProfileConditions(1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(1,)),
        ProfileAudazStaking(), "all_rows/v1",
    )
    draws = tuple(
        ProfileDraw(1, label, _minute(label), (0, 1, 2), True)
        for label in ("2025-09-01 05:10", "2025-09-02 05:10")
    )
    return game, request, draws


def test_v3_result_roundtrip_and_replay_include_prestart_rows():
    game, request, draws = setup_case()
    session = run_profile_session(
        game, request.conditions, request.selector, request.staking, draws
    )
    result = ProfileAudazResult("profile", 3, session)
    wire = serialize_profile_audaz_result(result)
    assert json.loads(wire)["schema_version"] == 3
    parsed = load_profile_audaz_result(wire)
    assert parsed == result
    assert validate_profile_audaz_result(parsed, request, game, draws) == result
    # The dataset digest is verified by the repository before this pure replay
    # validator is called; pre-start rows are still part of this complete input.
    forged = json.loads(wire)
    forged["final_balance"] += 1
    with pytest.raises(ValueError, match="differs"):
        validate_profile_audaz_result(
            load_profile_audaz_result(json.dumps(forged)), request, game, draws
        )


def test_audaz_executes_alternate_universe_rational_scaled_profile():
    game = GameProfile.model_validate({
        "schema_version": 1, "profile_id": "compact-rational", "revision": 1,
        "universe_size": 10, "positions": 3, "allows_repeats": True,
        "multipliers": [
            {"numerator": 7, "denominator": 2},
            {"numerator": 1, "denominator": 2},
            {"numerator": 1, "denominator": 4},
        ],
        "currency": "DOP", "scale": 1, "stake_increment": 4,
        "minimum_stake": 4, "maximum_stake": 12, "max_coverage": 10,
        "max_exposure": 120, "best_rule": "maximum-payout/v1",
    })
    request = ProfileAudazRequest(
        "profile", 3, "Rational audaz", "b" * 64, game.profile_id, game.revision,
        profile_sha256(game),
        ProfileConditions(1, "2025-09-02 05:10", 10, 30, SettlementMode.ALL),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(0,)),
        ProfileAudazStaking(), "all_rows/v1",
    )
    draw = ProfileDraw(1, "2025-09-02 05:10", _minute("2025-09-02 05:10"), (0, 1, 1), True)
    result = run_profile_session(
        game, request.conditions, request.selector, request.staking, (draw,)
    )
    assert result.outcome.value == "goal"
    assert result.bets[0].stakes[0][1] % game.stake_increment == 0
    assert result.bets[0].wagered <= game.max_exposure
    wrapped = ProfileAudazResult("profile", 3, result)
    assert validate_profile_audaz_result(wrapped, request, game, (draw,)) == wrapped
