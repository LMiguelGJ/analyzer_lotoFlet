"""Private strict v5 result codec and authenticated deterministic replay gate."""

import json
import re

from laboratorio.domain.contracts import GameProfile
from laboratorio.domain.profile_archive import ArchivedBinding
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.profile_request_v5 import ProfileBatchRequestV5
from laboratorio.domain.profile_result import (
    _COLLISIONS,
    _load_profile_result,
    _serialize_profile_result,
)
from laboratorio.domain.profile_session_v5 import (
    ProfileBatchResultV5,
    ProfileStrategyResultV5,
    run_profile_batch_v5,
)
from laboratorio.importing.datasets import SavedDataset

RESULT_KIND = "profile_batch_result"
RESULT_VERSION = 5
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PROFILE_ID = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
_V5_COLLISIONS = _COLLISIONS | {"recovery_round_limit"}


def serialize_profile_batch_result_v5(result: ProfileBatchResultV5) -> str:
    _validate_envelope(result)
    return json.dumps(
        {
            "schema_version": 5,
            "kind": RESULT_KIND,
            "profile_id": result.profile_id,
            "profile_revision": result.profile_revision,
            "profile_sha256": result.profile_sha256,
            "dataset_sha256": result.dataset_sha256,
            "results": [
                {
                    "ordinal": item.ordinal,
                    "definition": _definition(item.definition),
                    "session": _session_dict(item.session),
                    "start_draw_index": item.start_draw_index,
                    "prior_cutoff": item.prior_cutoff,
                    "dataset_sha256": item.dataset_sha256,
                }
                for item in result.results
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def load_profile_batch_result_v5(payload: str) -> ProfileBatchResultV5:
    """Load exact shape and values; this codec alone does not establish source trust."""
    if type(payload) is not str:
        raise TypeError("payload must be a JSON string")
    try:
        raw = json.loads(payload, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid profile batch result JSON") from exc
    _keys(
        raw,
        {
            "schema_version",
            "kind",
            "profile_id",
            "profile_revision",
            "profile_sha256",
            "dataset_sha256",
            "results",
        },
        "result",
    )
    if type(raw["schema_version"]) is not int or raw["schema_version"] != RESULT_VERSION:
        raise ValueError("unsupported profile batch result version")
    if raw["kind"] != RESULT_KIND or type(raw["kind"]) is not str:
        raise ValueError("unsupported profile batch result kind")
    if type(raw["results"]) is not list or not 1 <= len(raw["results"]) <= 3:
        raise ValueError("results must contain one to three sessions")
    from laboratorio.domain.profile_request_v5 import _load_definition

    results = []
    for ordinal, item in enumerate(raw["results"]):
        _keys(
            item,
            {
                "ordinal",
                "definition",
                "session",
                "start_draw_index",
                "prior_cutoff",
                "dataset_sha256",
            },
            "strategy result",
        )
        if type(item["ordinal"]) is not int or item["ordinal"] != ordinal:
            raise ValueError("strategy ordinals must be contiguous and ordered")
        session_text = json.dumps(
            item["session"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        session = _load_profile_result(session_text, _V5_COLLISIONS)
        results.append(
            ProfileStrategyResultV5(
                ordinal,
                _load_definition(item["definition"]),
                session,
                item["start_draw_index"],
                item["prior_cutoff"],
                item["dataset_sha256"],
            )
        )
    result = ProfileBatchResultV5(
        5,
        RESULT_KIND,
        raw["profile_id"],
        raw["profile_revision"],
        raw["profile_sha256"],
        raw["dataset_sha256"],
        tuple(results),
    )
    _validate_envelope(result)
    return result


def validate_profile_batch_result_v5(
    result: ProfileBatchResultV5,
    request: ProfileBatchRequestV5,
    profile: GameProfile,
    dataset: SavedDataset,
    binding: ArchivedBinding | None,
    *,
    operation_budget: int,
) -> ProfileBatchResultV5:
    """Require exact replay against full checked data and, for archive modes, binding."""
    result = load_profile_batch_result_v5(serialize_profile_batch_result_v5(result))
    if type(request) is not ProfileBatchRequestV5:
        raise ValueError("request must be a ProfileBatchRequestV5")
    request.__post_init__()
    if profile_sha256(profile) != request.profile_sha256:
        raise ValueError("request/profile source binding mismatch")
    replay = run_profile_batch_v5(
        request, profile, dataset, binding, operation_budget=operation_budget
    )
    if result != replay:
        raise ValueError("profile batch result does not match authenticated deterministic replay")
    return result


def _validate_envelope(result: ProfileBatchResultV5) -> None:
    if type(result) is not ProfileBatchResultV5:
        raise ValueError("result must be ProfileBatchResultV5")
    if result.schema_version != 5 or result.kind != RESULT_KIND:
        raise ValueError("unsupported profile batch result version or kind")
    if (
        type(result.profile_id) is not str
        or not _PROFILE_ID.fullmatch(result.profile_id)
        or type(result.profile_revision) is not int
        or result.profile_revision < 1
    ):
        raise ValueError("invalid result profile identity")
    if type(result.profile_sha256) is not str or not _HEX64.fullmatch(result.profile_sha256):
        raise ValueError("invalid profile hash")
    if type(result.dataset_sha256) is not str or not _HEX64.fullmatch(result.dataset_sha256):
        raise ValueError("invalid dataset hash")
    if type(result.results) is not tuple or not 1 <= len(result.results) <= 3:
        raise ValueError("results must contain one to three sessions")
    for ordinal, item in enumerate(result.results):
        if type(item) is not ProfileStrategyResultV5 or item.ordinal != ordinal:
            raise ValueError("strategy results must be exact ordered result objects")
        item.definition.__post_init__()
        if item.dataset_sha256 != result.dataset_sha256:
            raise ValueError("strategy result dataset binding mismatch")
        if (
            item.session.profile_id != result.profile_id
            or item.session.profile_revision != result.profile_revision
        ):
            raise ValueError("strategy result profile binding mismatch")
        if type(item.start_draw_index) is not int or item.start_draw_index < 0:
            raise ValueError("invalid start draw index")
        if item.prior_cutoff is not None and type(item.prior_cutoff) is not str:
            raise ValueError("invalid prior cutoff")


def _session_dict(session) -> dict:
    try:
        return json.loads(_serialize_profile_result(session, _V5_COLLISIONS))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid typed profile session result") from exc


def _definition(definition) -> dict:
    from laboratorio.domain.profile_request_v5 import _definition_dict

    return _definition_dict(definition)


def _keys(value: object, expected: set[str], name: str) -> dict:
    if type(value) is not dict or value.keys() != expected:
        raise ValueError(f"{name} must contain exactly {sorted(expected)}")
    return value


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError(f"duplicate JSON field: {key}")
        values[key] = value
    return values


def _bad_constant(value: str) -> None:
    raise ValueError(f"non-JSON number: {value}")
