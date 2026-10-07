"""Lossless run read envelopes with native legacy/profile and batch adapters."""

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from fastapi import HTTPException

from laboratorio.domain.contracts import RunStatus
from laboratorio.domain.metrics import financial_metrics
from laboratorio.domain.profile_result_v2 import ProfileCyclingResult
from laboratorio.domain.profile_result_v3 import ProfileAudazResult
from laboratorio.domain.profile_result_v4 import ProfileRecoveryResult
from laboratorio.domain.profile_session import ProfileOutcome
from laboratorio.domain.profile_session_v5 import ProfileBatchResultV5

if TYPE_CHECKING:
    from laboratorio.storage.repository import SavedRun


class NativeRunContext(TypedDict, total=False):
    result_kind: Literal["profile"]
    result_schema_version: int | None
    strategy: dict[str, Any]


class RunEnvelope(NativeRunContext):
    ordinal: int
    configuration_id: str | None
    status: RunStatus | str
    result: dict[str, Any] | None
    bets_count: int


@dataclass(frozen=True)
class BatchRunContext:
    """Persisted admission context, not an inferred request or financial result."""

    source_count: int
    requested: dict[str, Any]
    effective: dict[str, Any]
    strategy_ref: dict[str, Any]


def _run_envelope(
    run: "SavedRun",
    result: dict[str, Any] | None,
    bets_count: int,
    *,
    status: RunStatus | str,
    before_result: NativeRunContext | None = None,
) -> RunEnvelope:
    return {
        "ordinal": run.ordinal,
        "configuration_id": run.configuration_id,
        "status": status,
        **(before_result or {}),
        "result": result,
        "bets_count": bets_count,
    }


def run_summary(
    run: "SavedRun", capital: int, *, batch_context: BatchRunContext | None = None
) -> dict[str, Any]:
    """Common consumed read boundary; result payloads stay native to their adapter."""
    if batch_context is not None:
        return v5_run_summary(
            run,
            capital,
            batch_context.source_count,
            batch_context.requested,
            batch_context.effective,
            batch_context.strategy_ref,
        )
    return _legacy_run_summary(run, capital)


def _legacy_run_summary(run, capital):
    result = run.result
    if isinstance(result, (ProfileCyclingResult, ProfileAudazResult, ProfileRecoveryResult)):
        result = result.session
    payload = (
        None
        if result is None
        else {
            **{key: value for key, value in asdict(result).items() if key != "bets"},
            "delta": result.final_balance - capital,
            **financial_metrics(result, capital),
        }
    )
    summary = {
        **_run_envelope(run, payload, 0 if result is None else len(result.bets), status=run.status)
    }
    if run.result_kind == "profile":
        summary["result_kind"] = "profile"
    if run.result_schema_version in (2, 3, 4) and summary["result"] is not None:
        summary["result"]["schema_version"] = run.result_schema_version
    return summary


def v5_strategy_result(run):
    result = run.result
    if type(result) is not ProfileBatchResultV5 or len(result.results) != 1:
        raise HTTPException(409, "stored profile batch run result is not publicly supported")
    strategy = result.results[0]
    if strategy.ordinal != 0:
        raise HTTPException(409, "stored profile batch strategy ordinal is corrupt")
    return strategy


def v5_run_summary(run, capital, source_count, requested, effective, strategy_ref):
    if run.result is None:
        status = run.status.value
        return {
            **_run_envelope(
                run,
                None,
                0,
                status=status,
                before_result={
                    "result_kind": "profile",
                    "result_schema_version": 5 if run.result_schema_version == 5 else None,
                    "strategy": _strategy_context(strategy_ref, None),
                },
            ),
            "complete": False,
            "completion": "unavailable",
            "stop_category": "interrupted" if status in ("cancelled", "interrupted") else "unknown",
            "stop_reason": status,
            "stop_code": "unknown",
            "error": getattr(run, "error", None),
        }

    strategy = v5_strategy_result(run)
    session = strategy.session
    session_data = {key: value for key, value in asdict(session).items() if key != "bets"}
    stop_category, stop_reason, complete = _stop(
        session.outcome,
        session.collisions,
        session.elapsed_draws,
        strategy.start_draw_index,
        source_count,
        requested,
        effective,
    )
    payload = {
        **session_data,
        "schema_version": 5,
        "definition_name": strategy.definition.name,
        "delta": session.final_balance - capital,
        **financial_metrics(session, capital),
        "start_draw_index": strategy.start_draw_index,
        "prior_cutoff": strategy.prior_cutoff,
        "dataset_sha256": strategy.dataset_sha256,
        "source_count": source_count,
        "requested_conditions": requested,
        "effective_conditions": effective,
        "stop_category": stop_category,
        "stop_reason": stop_reason,
        "complete": complete,
    }
    summary = {
        **_run_envelope(
            run,
            payload,
            len(session.bets),
            status=run.status.value,
            before_result={
                "result_kind": "profile",
                "result_schema_version": 5,
                "strategy": _strategy_context(strategy_ref, strategy),
            },
        ),
        "complete": run.status.value == "completed" and complete,
        "completion": "complete" if run.status.value == "completed" and complete else "incomplete",
        "stop_category": stop_category,
        "stop_reason": stop_reason,
        "stop_code": stop_category,
        "error": getattr(run, "error", None),
    }
    return summary


def _strategy_context(reference, strategy):
    return {
        "id": reference["id"],
        "revision": reference["revision"],
        "definition_sha256": reference["definition_sha256"],
        "name": None if strategy is None else strategy.definition.name,
    }


def _stop(outcome, collisions, elapsed, start, source_count, requested, effective):
    if "goal" in collisions or outcome is ProfileOutcome.GOAL:
        return "financial_goal", "financial goal reached", True
    if "ruin" in collisions or outcome is ProfileOutcome.RUIN:
        return "financial_ruin", "financial quiebre reached", True
    if "recovery_round_limit" in collisions:
        return "recovery_end", "recovery ladder end reached", True
    if outcome is ProfileOutcome.CANCELLED:
        return "interrupted", "session cancelled", False
    if outcome is ProfileOutcome.LIMIT:
        if any(item in collisions for item in ("end_minute", "duration_minutes")):
            return "configured_limit", ", ".join(collisions), True
        limits = (("max_bet_draws", "max_bet_draws"), ("max_elapsed_draws", "max_elapsed_draws"))
        for field, code in limits:
            if field in collisions:
                wanted = requested.get(field)
                actual = effective.get(field)
                if wanted is not None and wanted == actual:
                    return "configured_limit", code, True
                return "operational_budget", code, False
        return "configured_limit", ", ".join(collisions) or "configured limit", True
    end = start + elapsed
    if end < source_count:
        return "operational_window", "bounded draw window ended before source end", False
    return "source_end", "full saved source ended", True


def attach_source_indices(points, bets, source_indices):
    """Map reducer-local bet offsets to canonical source rows without shifting replay offsets."""
    for point in points["points"]:
        bet_index = point["source_index"]
        point["bet_index"] = bet_index
        point["source_index"] = source_indices[bet_index]
    for extremum in (points["minimum"], points["maximum"]):
        bet_index = extremum["source_index"]
        if bet_index is not None:
            extremum["bet_index"] = bet_index
            extremum["source_index"] = source_indices[bet_index]
    return points
