"""Strict v1 profile result wire and independent trusted admission.

Parsing and serialization check shape and exact types, not financial correctness.
Admission reruns the deterministic session over the caller's authenticated, complete
chronological dataset (including pre-start rows), at most 10,000 rows. The caller
must bind those rows to request.dataset_sha256 using the importer's own digest
convention before calling this module; a result contains no dataset proof. Replay
cost is O(rows + bet draws * universe_size * log(universe_size)) for seeded random
selection, plus settlement/profile validation. No database or legacy result path.
"""

import json
import re

from laboratorio.domain.contracts import (
    MAX_MONEY,
    MAX_PROFILE_REVISION,
    MAX_PROFILE_UNIVERSE,
    GameProfile,
)
from laboratorio.domain.profile_request import (
    ENTRY_POLICY,
    ProfileExperimentRequest,
    profile_sha256,
)
from laboratorio.domain.profile_session import (
    MAX_SESSION_ROWS,
    SESSION_VERSION,
    ProfileBet,
    ProfileDraw,
    ProfileOutcome,
    ProfileSessionResult,
    _minute,
    run_profile_session,
)

RESULT_KIND = "profile"
RESULT_VERSION = 1
_RESULT_KEYS = set(ProfileSessionResult.__dataclass_fields__) | {"kind"}
_BET_KEYS = set(ProfileBet.__dataclass_fields__)
_PROFILE_ID = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
_COLLISIONS = {
    "end_minute",
    "duration_minutes",
    "goal",
    "ruin",
    "max_bet_draws",
    "max_elapsed_draws",
}


def _keys(value: object, expected: set[str], name: str) -> dict:
    if type(value) is not dict or value.keys() != expected:
        raise ValueError(f"{name} must contain exactly {sorted(expected)}")
    return value


def _integer(value: object, name: str, ceiling: int) -> None:
    if type(value) is not int or not 0 <= value <= ceiling:
        raise ValueError(f"{name} must be an exact bounded integer")


def _utf8(value: object) -> None:
    """Reject lone surrogates even when escaped in JSON text."""
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("result contains invalid UTF-8 text") from exc
    elif type(value) is list:
        for item in value:
            _utf8(item)
    elif type(value) is dict:
        for key, item in value.items():
            _utf8(key)
            _utf8(item)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _bad_constant(value: str) -> None:
    raise ValueError(f"non-JSON number: {value}")


def _load_profile_result(
    payload: str, allowed_collisions: set[str] = _COLLISIONS
) -> ProfileSessionResult:
    """Parse the exact result shape with a caller-selected closed collision vocabulary."""
    if type(payload) is not str:
        raise ValueError("result payload must be a JSON string")
    _utf8(payload)
    try:
        raw = _keys(
            json.loads(payload, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant),
            _RESULT_KEYS,
            "result",
        )
    except json.JSONDecodeError as exc:
        raise ValueError("invalid profile result JSON") from exc
    _utf8(raw)
    if type(raw["kind"]) is not str or raw["kind"] != RESULT_KIND:
        raise ValueError("unsupported result kind")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != RESULT_VERSION:
        raise ValueError("unsupported result version")
    if type(raw["profile_id"]) is not str or not _PROFILE_ID.fullmatch(raw["profile_id"]):
        raise ValueError("invalid profile_id")
    _integer(raw["profile_revision"], "profile_revision", MAX_PROFILE_REVISION)
    if raw["profile_revision"] == 0:
        raise ValueError("invalid profile_revision")
    if type(raw["outcome"]) is not str:
        raise ValueError("invalid outcome")
    try:
        outcome = ProfileOutcome(raw["outcome"])
    except ValueError as exc:
        raise ValueError("invalid outcome") from exc
    collisions = raw["collisions"]
    if (
        type(collisions) is not list
        or any(type(reason) is not str or reason not in allowed_collisions for reason in collisions)
        or len(set(collisions)) != len(collisions)
    ):
        raise ValueError("invalid collisions")
    for field, ceiling in (
        ("elapsed_draws", MAX_SESSION_ROWS),
        ("bet_draws", MAX_SESSION_ROWS),
        ("wagered", MAX_MONEY),
        ("paid", MAX_MONEY),
        ("final_balance", MAX_MONEY),
    ):
        _integer(raw[field], field, ceiling)
    if type(raw["bets"]) is not list or len(raw["bets"]) > MAX_SESSION_ROWS:
        raise ValueError("bets must be a bounded array")
    bets = []
    for value in raw["bets"]:
        bet = _keys(value, _BET_KEYS, "bet")
        _minute(bet["label"])
        if type(bet["stakes"]) is not list or not bet["stakes"]:
            raise ValueError("stakes must be a nonempty array")
        stakes = []
        for pair in bet["stakes"]:
            if type(pair) is not list or len(pair) != 2:
                raise ValueError("each stake must be a [number, amount] pair")
            _integer(pair[0], "selected number", MAX_PROFILE_UNIVERSE - 1)
            _integer(pair[1], "stake", MAX_MONEY)
            if pair[1] == 0:
                raise ValueError("stake must be positive")
            stakes.append(tuple(pair))
        if len({number for number, _ in stakes}) != len(stakes):
            raise ValueError("selected numbers must be distinct")
        if type(bet["results"]) is not list or not bet["results"]:
            raise ValueError("results must be a nonempty array")
        for number in bet["results"]:
            _integer(number, "result number", MAX_PROFILE_UNIVERSE - 1)
        for field in ("wagered", "paid", "balance"):
            _integer(bet[field], field, MAX_MONEY)
        bets.append(
            ProfileBet(
                bet["label"],
                tuple(stakes),
                tuple(bet["results"]),
                bet["wagered"],
                bet["paid"],
                bet["balance"],
            )
        )
    if raw["bet_draws"] > raw["elapsed_draws"] or raw["bet_draws"] != len(bets):
        raise ValueError("invalid result counts")
    return ProfileSessionResult(
        SESSION_VERSION,
        raw["profile_id"],
        raw["profile_revision"],
        outcome,
        tuple(collisions),
        raw["elapsed_draws"],
        raw["bet_draws"],
        raw["wagered"],
        raw["paid"],
        raw["final_balance"],
        tuple(bets),
    )


def load_profile_result(payload: str) -> ProfileSessionResult:
    """Parse the exact v1 wire; v1's collision vocabulary is intentionally fixed."""
    return _load_profile_result(payload)


def _serialize_profile_result(
    result: ProfileSessionResult, allowed_collisions: set[str] = _COLLISIONS
) -> str:
    """Canonical JSON shape with an explicit closed collision vocabulary."""
    if type(result) is not ProfileSessionResult:
        raise ValueError("result must be a ProfileSessionResult")
    try:
        raw = {
            "kind": RESULT_KIND,
            "schema_version": result.schema_version,
            "profile_id": result.profile_id,
            "profile_revision": result.profile_revision,
            "outcome": result.outcome.value,
            "collisions": list(result.collisions),
            "elapsed_draws": result.elapsed_draws,
            "bet_draws": result.bet_draws,
            "wagered": result.wagered,
            "paid": result.paid,
            "final_balance": result.final_balance,
            "bets": [
                {
                    "label": bet.label,
                    "stakes": [list(pair) for pair in bet.stakes],
                    "results": list(bet.results),
                    "wagered": bet.wagered,
                    "paid": bet.paid,
                    "balance": bet.balance,
                }
                for bet in result.bets
            ],
        }
    except (AttributeError, TypeError) as exc:
        raise ValueError("invalid typed profile result") from exc
    _utf8(raw)
    text = json.dumps(
        raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    _load_profile_result(text, allowed_collisions)  # shape only, never finances
    return text


def serialize_profile_result(result: ProfileSessionResult) -> str:
    """Canonical v1 JSON; never accepts schema-4 collision vocabulary."""
    return _serialize_profile_result(result)


def validate_profile_result(
    result: ProfileSessionResult,
    request: ProfileExperimentRequest,
    profile: GameProfile,
    trusted_draws: list[ProfileDraw] | tuple[ProfileDraw, ...],
    *,
    require_completed: bool = True,
) -> ProfileSessionResult:
    """Admit only an exact deterministic replay of caller-authenticated source rows.

    The caller must authenticate the complete ordered rows against the request's
    dataset_sha256 and verify job/request ownership independently. This API does
    not fetch data or infer a digest from the result. Cancellation is rejected for
    completed jobs by default; opting out replays its explicit elapsed cutoff.
    """
    if type(require_completed) is not bool:
        raise ValueError("require_completed must be a bool")
    result = load_profile_result(serialize_profile_result(result))
    if type(request) is not ProfileExperimentRequest:
        raise ValueError("request must be a ProfileExperimentRequest")
    request.__post_init__()
    if type(profile) is not GameProfile:
        raise ValueError("profile must be a GameProfile")
    if (
        request.profile_id != profile.profile_id
        or request.profile_revision != profile.revision
        or request.profile_sha256 != profile_sha256(profile)
        or result.profile_id != request.profile_id
        or result.profile_revision != request.profile_revision
        or request.entry_policy != ENTRY_POLICY
    ):
        raise ValueError("profile result/request/profile binding mismatch")
    if type(trusted_draws) not in (list, tuple) or len(trusted_draws) > MAX_SESSION_ROWS:
        raise ValueError("trusted draws must be a bounded materialized sequence")
    if any(
        type(row) is not ProfileDraw or type(row.enter) is not bool or not row.enter
        for row in trusted_draws
    ):
        raise ValueError("all_rows/v1 requires every trusted source row to enter")
    if require_completed and result.outcome is ProfileOutcome.CANCELLED:
        raise ValueError("cancelled result cannot complete a job")
    expected = run_profile_session(
        profile,
        request.conditions,
        request.selector,
        request.staking,
        trusted_draws,
        cancel_after_elapsed_draws=(
            result.elapsed_draws if result.outcome is ProfileOutcome.CANCELLED else None
        ),
    )
    if result != expected:
        raise ValueError("profile result differs from trusted deterministic replay")
    return result
