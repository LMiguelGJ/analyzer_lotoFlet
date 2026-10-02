"""Read-only projections for persisted profile-batch v5 sessions."""

from dataclasses import asdict

from fastapi import HTTPException

from laboratorio.domain.metrics import financial_metrics
from laboratorio.domain.profile_session import ProfileOutcome
from laboratorio.domain.profile_session_v5 import ProfileBatchResultV5


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
            "ordinal": run.ordinal,
            "configuration_id": run.configuration_id,
            "status": status,
            "result_kind": "profile",
            "result_schema_version": 5 if run.result_schema_version == 5 else None,
            "strategy": _strategy_context(strategy_ref, None),
            "result": None,
            "bets_count": 0,
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
    summary = {
        "ordinal": run.ordinal,
        "configuration_id": run.configuration_id,
        "status": run.status.value,
        "result_kind": "profile",
        "result_schema_version": 5,
        "strategy": _strategy_context(strategy_ref, strategy),
        "result": {
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
        },
        "bets_count": len(session.bets),
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
