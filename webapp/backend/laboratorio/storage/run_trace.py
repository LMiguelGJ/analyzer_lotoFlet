"""Bounded session and bet detail capture for persisted runs."""

import json
from dataclasses import dataclass

from laboratorio.domain.runs import RunConfig, RunResult
from laboratorio.domain.session import Draw

MAX_STORED_SESSIONS = 50_000
MAX_STORED_BETS = 250_000
MAX_DETAIL_BYTES = 32 * 1024 * 1024
_ENCODER = json.JSONEncoder(separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class PackedRun:
    session_rows: list[tuple]
    detail: dict


def pack_run(result: RunResult, rows: list[Draw], config: RunConfig) -> PackedRun:
    stored_rows = []
    stored_bets = 0
    detail_bytes = 0
    detail_blocked = False
    for session in result.sessions[:MAX_STORED_SESSIONS]:
        start = rows[session.start_index]
        end = rows[session.end_index]
        encoded = None
        bet_count = len(session.bets)
        if not detail_blocked and stored_bets + bet_count <= MAX_STORED_BETS:
            payload = [
                [bet.label, list(bet.numbers), list(bet.results), bet.paid, bet.balance]
                for bet in session.bets
            ]
            candidate = _ENCODER.encode(payload)
            size = len(candidate.encode("utf-8"))
            if detail_bytes + size <= MAX_DETAIL_BYTES:
                encoded = candidate
                stored_bets += bet_count
                detail_bytes += size
            else:
                detail_blocked = True
        else:
            detail_blocked = True
        stored_rows.append(
            (
                session.ordinal,
                session.outcome,
                session.start_index,
                session.end_index,
                start.label,
                end.label,
                session.draws,
                bet_count,
                session.wagered,
                session.paid,
                session.final_balance,
                encoded,
            )
        )
    truncated = len(result.sessions) > MAX_STORED_SESSIONS
    status = (
        "sessions_truncated"
        if truncated
        else (
            "complete"
            if len(stored_rows) == len(result.sessions)
            and all(row[-1] is not None or row[7] == 0 for row in stored_rows)
            else "partial"
        )
    )
    return PackedRun(
        stored_rows,
        {
            "status": status,
            "total_sessions": len(result.sessions),
            "stored_sessions": len(stored_rows),
            "total_bets": result.totals.bets,
            "stored_bets": stored_bets,
            "limits": {
                "sessions": MAX_STORED_SESSIONS,
                "bets": MAX_STORED_BETS,
                "bytes": MAX_DETAIL_BYTES,
            },
        },
    )
