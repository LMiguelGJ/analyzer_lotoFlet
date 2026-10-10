import json

from laboratorio.domain.runs import RunConfig, run_sessions
from laboratorio.domain.session import Draw
from laboratorio.engine.run_data import RunStrategy, RunWindow, build_run_rows, source_from_lab
from laboratorio.storage.run_trace import pack_run


def test_pack_run_preserves_session_labels_and_compact_bets(lab_data, monkeypatch):
    config = RunConfig(20, 100, 2, 1, (60,), 1, 3)
    strategy = RunStrategy("parity", (), 2)
    rows = build_run_rows(
        source_from_lab(lab_data),
        lab_data.rankings,
        strategy,
        RunWindow(None, None),
        parity_votes=lab_data.parity_votes(),
    ).rows[:12]
    result = run_sessions(config, rows)
    packed = pack_run(result, rows, config)
    assert len(packed.session_rows) == result.totals.sessions
    assert packed.detail["status"] == "complete"
    saved = json.loads(packed.session_rows[0][-1])
    assert saved[0][0] == rows[result.sessions[0].start_index].label
    assert saved[0][1] == list(result.sessions[0].bets[0].numbers)
    assert saved[0][2] == list(result.sessions[0].bets[0].results)


def test_pack_run_reports_partial_and_session_truncation(lab_data, monkeypatch):
    from laboratorio.storage import run_trace

    config = RunConfig(10, 1000, 1, 1, (60,), 1, 1)
    rows = [
        Draw(f"2025-01-{index + 1:02d} 00:00", index, (0, 1, 2, 3, 4), (9,)) for index in range(5)
    ]
    result = run_sessions(config, rows)
    monkeypatch.setattr(run_trace, "MAX_STORED_BETS", 1)
    partial = pack_run(result, rows, config)
    assert partial.detail["status"] == "partial"
    assert sum(row[-1] is not None for row in partial.session_rows) == 1
    monkeypatch.setattr(run_trace, "MAX_STORED_BETS", 100)
    monkeypatch.setattr(run_trace, "MAX_DETAIL_BYTES", 1)
    byte_limited = pack_run(result, rows, config)
    assert byte_limited.detail["status"] == "partial"
    assert byte_limited.detail["stored_bets"] == 0
    monkeypatch.setattr(run_trace, "MAX_STORED_SESSIONS", 2)
    truncated = pack_run(result, rows, config)
    assert truncated.detail["status"] == "sessions_truncated"
    assert len(truncated.session_rows) == 2
