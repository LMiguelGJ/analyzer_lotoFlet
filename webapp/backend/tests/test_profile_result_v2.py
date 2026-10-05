"""Schema-2 result replay is private and policy-bound, not a v1 admission."""

import json
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from laboratorio.domain.contracts import GameProfile, SettlementMode, legacy_quiniela_80_profile
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.profile_request_v2 import ProfileCyclingRequest
from laboratorio.domain.profile_result import load_profile_result, serialize_profile_result
from laboratorio.domain.profile_result_v2 import (
    ProfileCyclingResult,
    load_profile_cycling_result,
    serialize_profile_cycling_result,
    validate_profile_cycling_result,
)
from laboratorio.domain.profile_session import (
    ProfileConditions,
    ProfileDraw,
    ProfileOutcome,
    ProfileSelector,
    Q80CyclingStaking,
    run_profile_session,
)

START = datetime(2025, 1, 1, 5, 10)


def draw(index, results=(1, 2, 3, 4, 5), enter=True):
    moment = START + timedelta(minutes=5 * index)
    return ProfileDraw(
        1,
        moment.strftime("%Y-%m-%d %H:%M"),
        (moment - datetime(1970, 1, 1)).days * 1440 + moment.hour * 60 + moment.minute,
        results,
        enter,
    )


def setup(rows=None, *, settlement=SettlementMode.ALL, coverage=50, capital=1_000_000):
    profile = legacy_quiniela_80_profile()
    conditions = ProfileConditions(1, draw(0).label, capital, 2_000_000, settlement)
    selector = ProfileSelector(
        1, "static-numbers/v1", coverage, numbers=tuple(range(50, 50 + coverage))
    )
    request = ProfileCyclingRequest(
        "profile",
        2,
        "Cycling",
        "a" * 64,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        conditions,
        selector,
        Q80CyclingStaking(),
        "all_rows/v1",
    )
    rows = rows if rows is not None else [draw(0)]
    session = run_profile_session(profile, conditions, selector, request.staking, rows)
    return request, profile, rows, ProfileCyclingResult("profile", 2, session)


def admitted(request, profile, rows, result):
    text = serialize_profile_cycling_result(result)
    assert load_profile_cycling_result(text) == result
    assert (
        validate_profile_cycling_result(load_profile_cycling_result(text), request, profile, rows)
        == result
    )
    with pytest.raises(ValueError):
        load_profile_result(text)
    with pytest.raises(ValueError):
        serialize_profile_result(result)  # type: ignore[arg-type]
    return result.session


def test_roundtrip_and_crossversion_rejection_with_canonical_bytes():
    """B-DOM-089: cycling result v2 has canonical private wire disjoint from v1."""
    request, profile, rows, result = setup()
    admitted(request, profile, rows, result)
    wire = serialize_profile_cycling_result(result)
    assert wire == json.dumps(json.loads(wire), sort_keys=True, separators=(",", ":"))
    assert json.loads(wire)["schema_version"] == 2
    assert result.session.schema_version == 1
    with pytest.raises(ValueError):
        load_profile_cycling_result(serialize_profile_result(result.session))
    with pytest.raises(ValueError):
        serialize_profile_cycling_result(result.session)  # type: ignore[arg-type]


@pytest.mark.parametrize("settlement,paid", [(SettlementMode.ALL, 184), (SettlementMode.BEST, 160)])
def test_secondary_payout_first_hit_reset_and_tamper_replay(settlement, paid):
    """B-DOM-090: cycling secondary payout/reset and replay tampering are verified."""
    rows = [draw(0, (1, 7, 2, 3, 4)), draw(1, (50, 50, 50, 7, 9)), draw(2)]
    request, profile, rows, result = setup(rows, settlement=settlement, capital=2000)
    session = admitted(request, profile, rows, result)
    assert [(bet.stakes[0][1], bet.paid) for bet in session.bets] == [
        (1, 0),
        (2, paid),
        (1, 0),
    ]
    for change in (
        replace(session, paid=session.paid + 1),
        replace(session, outcome=ProfileOutcome.LIMIT),
        replace(session, bets=(replace(session.bets[0], paid=1), *session.bets[1:])),
        replace(
            session,
            bets=(
                replace(session.bets[0], stakes=((50, 2), *session.bets[0].stakes[1:])),
                *session.bets[1:],
            ),
        ),
        replace(session, bets=(session.bets[1], session.bets[0], session.bets[2])),
    ):
        with pytest.raises(ValueError, match="replay"):
            validate_profile_cycling_result(replace(result, session=change), request, profile, rows)
    with pytest.raises(ValueError, match="replay"):
        validate_profile_cycling_result(result, request, profile, [draw(0), draw(1), draw(2)])


def test_ten_misses_cycle_and_policy_profile_source_binding():
    """B-DOM-091: cycling sequence and policy/profile/source binding are verified."""
    rows = [draw(i) for i in range(11)]
    request, profile, rows, result = setup(rows)
    assert [bet.wagered for bet in admitted(request, profile, rows, result).bets] == [
        50,
        100,
        300,
        800,
        2100,
        5600,
        14950,
        39850,
        106300,
        283450,
        50,
    ]
    with pytest.raises(ValueError, match="binding"):
        validate_profile_cycling_result(
            result, replace(request, profile_sha256="b" * 64), profile, rows
        )
    with pytest.raises(ValueError, match="binding"):
        validate_profile_cycling_result(
            result,
            request,
            profile.model_copy(update={"profile_id": "other-q80", "currency": "USD"}),
            rows,
        )
    with pytest.raises(ValueError, match="replay"):
        changed = replace(
            request,
            selector=ProfileSelector(1, "static-numbers/v1", 50, numbers=tuple(range(49, 99))),
        )
        validate_profile_cycling_result(result, changed, profile, rows)
    with pytest.raises(ValueError, match="bounded"):
        validate_profile_cycling_result(result, request, profile, (row for row in rows))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="all_rows"):
        validate_profile_cycling_result(result, request, profile, [draw(0, enter=False), *rows[1:]])


def test_non_q80_and_full_ladder_caps_rejected_on_trusted_admission():
    """B-DOM-092: cycling admission requires compatible Q80 and full ladder caps."""
    request, profile, rows, result = setup()
    profile_data = profile.model_dump(mode="python")
    profile_data.update(
        profile_id="non-q80",
        positions=3,
        best_rule="maximum-payout/v1",
        multipliers=profile_data["multipliers"][:3],
    )
    incompatible = GameProfile.model_validate(profile_data)
    altered = replace(
        request,
        profile_id=incompatible.profile_id,
        profile_sha256=profile_sha256(incompatible),
    )
    rebound = replace(result, session=replace(result.session, profile_id=incompatible.profile_id))
    with pytest.raises(ValueError, match="Q80 positions"):
        validate_profile_cycling_result(rebound, altered, incompatible, rows)
    capped = profile.model_copy(
        update={
            "profile_id": "capped-q80",
            "best_rule": "maximum-payout/v1",
            "maximum_stake": 5668,
        }
    )
    altered = replace(request, profile_id=capped.profile_id, profile_sha256=profile_sha256(capped))
    rebound = replace(result, session=replace(result.session, profile_id=capped.profile_id))
    with pytest.raises(ValueError, match="maximum stake"):
        validate_profile_cycling_result(rebound, altered, capped, rows)
    poor_request = replace(request, conditions=replace(request.conditions, capital=49))
    with pytest.raises(ValueError, match="afford"):
        validate_profile_cycling_result(result, poor_request, profile, rows)


def test_cancellation_requires_opt_in_and_no_prestart_provenance_inference():
    """B-DOM-093: cancelled cycling result needs opt-in; prior provenance is not inferred."""
    rows = [draw(-1), draw(0), draw(1)]
    request, profile, rows, _ = setup(rows)
    cancelled = ProfileCyclingResult(
        "profile",
        2,
        run_profile_session(
            profile,
            request.conditions,
            request.selector,
            request.staking,
            rows,
            cancel_after_elapsed_draws=1,
        ),
    )
    with pytest.raises(ValueError, match="cancelled"):
        validate_profile_cycling_result(cancelled, request, profile, rows)
    assert (
        validate_profile_cycling_result(cancelled, request, profile, rows, require_completed=False)
        == cancelled
    )
    assert (
        validate_profile_cycling_result(
            cancelled, request, profile, rows[1:], require_completed=False
        )
        == cancelled
    )
    with pytest.raises(ValueError, match="require_completed"):
        validate_profile_cycling_result(cancelled, request, profile, rows, require_completed=1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "path,bad",
    [
        (("kind",), "legacy"),
        (("schema_version",), True),
        (("schema_version",), 1),
        (("profile_revision",), 1.0),
        (("paid",), True),
        (("outcome",), "other"),
        (("bets", 0, "stakes", 0, 1), 1.0),
        (("bets", 0, "label"), "\ud800"),
        (("bets", 0, "results", 0), True),
    ],
)
def test_malformed_wire_rejected(path, bad):
    """B-DOM-094: cycling result rejects malformed wire types and values."""
    _, _, _, result = setup()
    value = json.loads(serialize_profile_cycling_result(result))
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad
    with pytest.raises(ValueError):
        load_profile_cycling_result(json.dumps(value))


def test_extra_missing_nested_duplicate_and_non_json_rejected():
    """B-DOM-094: cycling result rejects extra/missing/duplicate and non-JSON fields."""
    _, _, _, result = setup()
    value = json.loads(serialize_profile_cycling_result(result))
    for changed in (
        {**value, "extra": 1},
        {k: v for k, v in value.items() if k != "kind"},
        {**value, "bets": [{**value["bets"][0], "extra": 1}]},
    ):
        with pytest.raises(ValueError):
            load_profile_cycling_result(json.dumps(changed))
    text = json.dumps(value)
    for bad in (
        text[:-1] + ',"paid":0}',
        text.replace('"balance": ', '"balance": 0, "balance": ', 1),
        text.replace('"paid": 0', '"paid": NaN', 1),
        json.dumps({**value, "bets": [{**value["bets"][0], "results": ["\ud800"]}]}),
    ):
        with pytest.raises(ValueError):
            load_profile_cycling_result(bad)
