"""Profile result wire is structural; only authenticated complete replay admits it."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import datetime

import pytest

from laboratorio.domain.contracts import GameProfile, SettlementMode
from laboratorio.domain.profile_request import ProfileExperimentRequest, profile_sha256
from laboratorio.domain.profile_result import (
    load_profile_result,
    serialize_profile_result,
    validate_profile_result,
)
from laboratorio.domain.profile_session import (
    ProfileConditions,
    ProfileDraw,
    ProfileOutcome,
    ProfileSelector,
    ProfileStaking,
    run_profile_session,
)

START = "2025-01-01 05:10"


def setup(*, random=False, repeats=True, rows=None, conditions=None):
    profile = GameProfile.model_validate(
        dict(
            schema_version=1,
            profile_id="non100",
            revision=2,
            universe_size=11,
            positions=3,
            allows_repeats=repeats,
            multipliers=[{"numerator": n, "denominator": 1} for n in (3, 2, 1)],
            currency="DOP",
            scale=2,
            stake_increment=2,
            minimum_stake=2,
            maximum_stake=20,
            max_coverage=2,
            max_exposure=40,
            best_rule="maximum-payout/v1",
        )
    )
    conditions = conditions or ProfileConditions(
        1, START, 20, 100, SettlementMode.ALL, max_elapsed_draws=3
    )
    selector = (
        ProfileSelector(
            1,
            "seeded-random/hash-sha256-v1",
            2,
            seed=17,
            algorithm_version="hash-sha256-v1",
        )
        if random
        else ProfileSelector(1, "static-numbers/v1", 2, numbers=(1, 2))
    )
    staking = ProfileStaking(1, "flat-per-number/v1", 2)
    request = ProfileExperimentRequest(
        "profile",
        1,
        "Fixture",
        "a" * 64,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        conditions,
        selector,
        staking,
        "all_rows/v1",
    )
    rows = rows if rows is not None else [draw(START, (1, 1, 2))]
    return request, profile, rows


def draw(label, results=(1, 1, 2), enter=True):
    time = datetime.strptime(label, "%Y-%m-%d %H:%M")
    minute = (time - datetime(1970, 1, 1)).days * 1440 + time.hour * 60 + time.minute
    return ProfileDraw(1, label, minute, results, enter)


def result_for(request, profile, rows, **kwargs):
    return run_profile_session(
        profile, request.conditions, request.selector, request.staking, rows, **kwargs
    )


@pytest.mark.parametrize("random", [False, True])
def test_roundtrip_and_known_valid_static_random_admission(random):
    request, profile, rows = setup(random=random)
    result = result_for(request, profile, rows)
    wire = serialize_profile_result(result)
    assert json.loads(wire)["kind"] == "profile"
    assert wire == json.dumps(json.loads(wire), sort_keys=True, separators=(",", ":"))
    assert load_profile_result(wire) == result
    assert validate_profile_result(load_profile_result(wire), request, profile, rows) == result
    with pytest.raises(FrozenInstanceError):
        result.final_balance = 0  # type: ignore[misc]


def test_repeated_positions_non100_and_exact_scaled_integer_accounting():
    request, profile, rows = setup()
    result = result_for(request, profile, rows)
    assert result.bets[0].results == (1, 1, 2)
    assert result.bets[0].stakes == ((1, 2), (2, 2))
    assert (result.wagered, result.paid, result.final_balance) == (4, 12, 28)
    assert validate_profile_result(result, request, profile, rows) == result
    no_repeats = profile.model_copy(update={"allows_repeats": False})
    request2 = replace(request, profile_sha256=profile_sha256(no_repeats))
    with pytest.raises(ValueError, match="repeat"):
        validate_profile_result(result, request2, no_repeats, rows)


@pytest.mark.parametrize(
    "path,bad",
    [
        (("final_balance",), 50),
        (("paid",), 11),
        (("wagered",), 7),
        (("elapsed_draws",), 2),
        (("bets", 0, "balance"), 50),
        (("bets", 0, "paid"), 4),
        (("bets", 0, "wagered"), 6),
        (("bets", 0, "stakes"), [[1, 2], [3, 2]]),
        (("bets", 0, "results"), [2, 1, 2]),
        (("bets", 0, "label"), "2025-01-01 05:15"),
        (("outcome",), "limit"),
        (("collisions",), ["max_elapsed_draws"]),
    ],
)
def test_structurally_valid_forgery_rejected_by_replay(path, bad):
    request, profile, rows = setup()
    value = json.loads(serialize_profile_result(result_for(request, profile, rows)))
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad
    forged = load_profile_result(json.dumps(value))
    with pytest.raises(ValueError, match="replay"):
        validate_profile_result(forged, request, profile, rows)


def test_counts_that_are_internally_inconsistent_rejected_at_parse():
    request, profile, rows = setup()
    value = json.loads(serialize_profile_result(result_for(request, profile, rows)))
    for changes in ({"bet_draws": 0}, {"elapsed_draws": 0}):
        with pytest.raises(ValueError, match="counts"):
            load_profile_result(json.dumps({**value, **changes}))


def test_profile_binding_and_source_rows_mismatch():
    request, profile, rows = setup()
    result = result_for(request, profile, rows)
    with pytest.raises(ValueError, match="binding"):
        validate_profile_result(replace(result, profile_id="other"), request, profile, rows)
    with pytest.raises(ValueError, match="binding"):
        validate_profile_result(result, replace(request, profile_sha256="b" * 64), profile, rows)
    with pytest.raises(ValueError, match="binding"):
        validate_profile_result(result, replace(request, profile_revision=3), profile, rows)
    with pytest.raises(ValueError, match="binding"):
        validate_profile_result(
            result, request, profile.model_copy(update={"currency": "USD"}), rows
        )
    with pytest.raises(ValueError, match="replay"):
        validate_profile_result(result, request, profile, [draw(START, (4, 4, 5))])
    with pytest.raises(ValueError, match="all_rows"):
        validate_profile_result(result, request, profile, [draw(START, enter=False)])
    with pytest.raises(ValueError, match="bounded"):
        validate_profile_result(result, request, profile, (row for row in rows))  # type: ignore[arg-type]


def test_request_configuration_is_bound_by_replay():
    request, profile, rows = setup(rows=[draw(START), draw("2025-01-01 05:15")])
    result = result_for(request, profile, rows)
    variants = (
        replace(request, selector=ProfileSelector(1, "static-numbers/v1", 2, numbers=(3, 4))),
        replace(request, staking=ProfileStaking(1, "flat-per-number/v1", 4)),
        replace(
            request,
            conditions=replace(request.conditions, start_draw="2025-01-01 05:15"),
        ),
    )
    for altered in variants:
        with pytest.raises(ValueError, match="replay"):
            validate_profile_result(result, altered, profile, rows)


def test_full_source_including_prestart_and_skipped_entries_is_required():
    earlier = draw("2025-01-01 05:05")
    request, profile, rows = setup(rows=[earlier, draw(START)])
    result = result_for(request, profile, rows)
    assert validate_profile_result(result, request, profile, rows) == result
    # An omitted pre-start row has identical replay; dataset binding is caller-owned.
    assert validate_profile_result(result, request, profile, rows[1:]) == result
    with pytest.raises(ValueError, match="all_rows"):
        validate_profile_result(result, request, profile, [earlier, draw(START, enter=False)])
    with pytest.raises(ValueError, match="replay"):
        validate_profile_result(result, request, profile, [draw(START), draw("2025-01-01 05:15")])


def test_cancelled_parses_but_cannot_admit_completed_job():
    request, profile, rows = setup(rows=[draw(START), draw("2025-01-01 05:15")])
    result = result_for(request, profile, rows, cancel_after_elapsed_draws=1)
    assert result.outcome is ProfileOutcome.CANCELLED
    assert load_profile_result(serialize_profile_result(result)) == result
    with pytest.raises(ValueError, match="cancelled"):
        validate_profile_result(result, request, profile, rows)
    assert (
        validate_profile_result(result, request, profile, rows, require_completed=False) == result
    )
    with pytest.raises(ValueError, match="require_completed"):
        validate_profile_result(result, request, profile, rows, require_completed=1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "path,bad",
    [
        (("kind",), "legacy"),
        (("kind",), True),
        (("schema_version",), 2),
        (("schema_version",), True),
        (("profile_revision",), 1.0),
        (("elapsed_draws",), True),
        (("paid",), 1.0),
        (("outcome",), "won"),
        (("collisions",), ["other"]),
        (("bets", 0, "stakes", 0, 0), True),
        (("bets", 0, "stakes", 0, 1), 2.0),
        (("bets", 0, "results", 0), True),
        (("bets", 0, "balance"), 1.0),
        (("bets", 0, "label"), "\ud800"),
    ],
)
def test_bad_wire_fields_rejected_with_value_error(path, bad):
    request, profile, rows = setup()
    value = json.loads(serialize_profile_result(result_for(request, profile, rows)))
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad
    with pytest.raises(ValueError):
        load_profile_result(json.dumps(value))


def test_missing_extra_duplicate_keys_and_invalid_unicode_are_controlled():
    request, profile, rows = setup()
    value = json.loads(serialize_profile_result(result_for(request, profile, rows)))
    for key in ("kind", "bets", "profile_id", "paid"):
        with pytest.raises(ValueError):
            load_profile_result(json.dumps({k: v for k, v in value.items() if k != key}))
    with pytest.raises(ValueError):
        load_profile_result(json.dumps({**value, "legacy": 1}))
    for field in ("label", "stakes", "results", "paid"):
        bad = json.loads(json.dumps(value))
        bad["bets"][0].pop(field)
        with pytest.raises(ValueError):
            load_profile_result(json.dumps(bad))
    bad = json.loads(json.dumps(value))
    bad["bets"][0]["legacy"] = 1
    with pytest.raises(ValueError):
        load_profile_result(json.dumps(bad))
    for text in (
        '{"kind":"profile","kind":"profile"}',
        json.dumps(value)[:-1] + ',"kind":"profile"}',
        json.dumps(value).replace('"paid": 12', '"paid": 12, "paid": 12'),
    ):
        with pytest.raises(ValueError, match="duplicate"):
            load_profile_result(text)
    for text in ("{", '"\\ud800"', "\ud800", json.dumps({**value, "profile_id": "\ud800"})):
        with pytest.raises(ValueError):
            load_profile_result(text)
    with pytest.raises(ValueError):
        load_profile_result(json.dumps({**value, "paid": float("nan")}))
    with pytest.raises(ValueError):
        serialize_profile_result(replace(result_for(request, profile, rows), profile_id="\ud800"))
