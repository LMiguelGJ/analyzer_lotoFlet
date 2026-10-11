import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from laboratorio.domain.reference_labs import REFERENCE_LABS, ReferenceLab
from laboratorio.engine.adapter import LabData, load_history, load_rankings
from laboratorio.engine.reference_labs import run_reference_lab
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256, Settings

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_PATH = Path(__file__).parent / "fixtures" / "reference_labs_golden.json"
GOLDEN = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def inputs():
    sys.path[:0] = [str(ROOT), str(ROOT / "repo_ref"), str(ROOT / "repo_ref" / "main")]
    runner = importlib.import_module("simuladores.runner")
    compare = importlib.import_module("quiniela_compare")
    sim = importlib.import_module("quiniela_sim")
    history_path = ROOT / "chance_express_history.json"
    rankings_path = ROOT / "repo_ref" / "reports" / "chance_rank_v1" / "predictions" / "pos1.npz"
    runner.verify_input(history_path, runner.HISTORY_SHA256)
    runner.verify_input(rankings_path, runner.RANKINGS_SHA256)
    reference_history = sim.load_validated_history(history_path)
    context = compare.ranking_context(reference_history, rankings_path)
    reference_labels = tuple(reference_history.label(i) for i in range(reference_history.n))
    in_window = np.asarray(
        ["2025-09-02 05:10" <= label <= "2026-09-25 18:20" for label in reference_labels],
        dtype=bool,
    )
    eligible = context.row_ids[in_window[context.row_ids]]
    systems = {lab.system for lab in REFERENCE_LABS if lab.selection_kind == "ranking"}
    reference_families = {
        system: compare.ranking_family(rankings_path, system, context) for system in systems
    }

    history = load_history(history_path, HISTORY_SHA256)
    rankings = load_rankings(rankings_path, RANKINGS_SHA256, history)
    assert history.sha256 == HISTORY_SHA256
    assert len(history.labels) == 105426
    assert len(context.row_ids) == 65235
    return SimpleNamespace(
        reference_history=reference_history,
        history=history,
        rankings=rankings,
        context=context,
        eligible=eligible,
        reference_labels=reference_labels,
        reference_families=reference_families,
        runner=runner,
        compare=compare,
    )


def _session_payload(sessions):
    return [
        (
            "goal" if session.reached else "ruin" if session.ruined else "incomplete",
            start,
            start + session.steps - 1,
            session.steps,
            session.final_balance,
            session.wagered,
            session.paid,
        )
        for start, session in _session_starts(sessions)
    ]


def _session_starts(sessions):
    start = 0
    for session in sessions:
        yield start, session
        start += session.steps


def _digest(payload):
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def _reference_case(lab, inputs, votes):
    compare = inputs.compare
    context = inputs.context
    history = inputs.reference_history
    row_ids = context.row_ids
    selected_nums = history.nums[row_ids]
    if lab.selection_kind == "parity":
        even = np.arange(0, 100, 2, dtype=np.uint8)
        odd = np.arange(1, 100, 2, dtype=np.uint8)
        orders = np.where(
            votes[row_ids, None] == 0,
            np.concatenate((even, odd))[None, :],
            np.concatenate((odd, even))[None, :],
        )
    else:
        orders = inputs.reference_families[lab.system]
    payments, first_hits = compare.selected_payments(selected_nums, orders, lab.coverage, "all")
    reference_sessions = compare.replay(
        lab.stake_style,
        lab.coverage,
        payments,
        first_hits,
        lab.capital,
        lab.goal,
    )
    payload = _session_payload(reference_sessions)
    complete = [s for s in reference_sessions if s.reached or s.ruined]
    totals = {
        "completed": len(complete),
        "incomplete": sum(not (s.reached or s.ruined) for s in reference_sessions),
        "goals": sum(s.reached for s in complete),
        "ruins": sum(s.ruined for s in complete),
        "sessions_total": len(reference_sessions),
        "total_wagered": sum(s.wagered for s in reference_sessions),
        "total_paid": sum(s.paid for s in reference_sessions),
        "total_net": sum(s.final_balance - lab.capital for s in reference_sessions),
        "total_steps": sum(s.steps for s in reference_sessions),
        "mean_net_closed": (
            sum(s.final_balance - lab.capital for s in complete) / len(complete)
            if complete
            else None
        ),
    }
    labels = inputs.reference_labels
    eligible = inputs.eligible
    return {
        "eligible_draws": len(eligible),
        "gaps": int(eligible[-1] - eligible[0] + 1 - len(eligible)) if len(eligible) else 0,
        "first": labels[int(eligible[0])] if len(eligible) else None,
        "last": labels[int(eligible[-1])] if len(eligible) else None,
        "totals": totals,
        "session_sha256": _digest(payload),
        "session_count": len(payload),
        "boundary_sessions": _boundaries(payload),
    }


def _boundaries(payload):
    selected = {}
    for index, session in enumerate(payload):
        outcome = session[0]
        if outcome in ("goal", "ruin") and outcome not in selected:
            selected[outcome] = {"index": index, "session": list(session)}
    for index in range(len(payload) - 1, -1, -1):
        if payload[index][0] == "incomplete":
            selected["incomplete"] = {"index": index, "session": list(payload[index])}
            break
    if payload:
        selected["first"] = {"index": 0, "session": list(payload[0])}
        selected["last"] = {"index": len(payload) - 1, "session": list(payload[-1])}
    return selected


def test_all_fourteen_laboratories_match_independent_history_and_frozen_golden(inputs, monkeypatch):
    adapter = importlib.import_module("laboratorio.engine.adapter")
    monkeypatch.setattr(adapter, "_load_cached_parity", lambda *args: None)
    monkeypatch.setattr(adapter, "_write_cached_parity", lambda *args: None)
    settings = Settings(
        data_dir=ROOT / "webapp" / "backend" / "tests" / "fixtures",
        history_path=ROOT / "chance_express_history.json",
        rankings_path=ROOT / "repo_ref" / "reports" / "chance_rank_v1" / "predictions" / "pos1.npz",
        frontend_dist=ROOT / "webapp" / "frontend" / "dist",
    )
    data = LabData(inputs.history, inputs.rankings, settings)
    votes = data.parity_votes()
    assert votes.shape == (105426,)
    assert np.all((votes == 0) | (votes == 1))
    golden_by_id = {row["lab_id"]: row for row in GOLDEN["laboratories"]}
    assert tuple(golden_by_id) == tuple(lab.lab_id for lab in REFERENCE_LABS)

    for lab in REFERENCE_LABS:
        expected = golden_by_id[lab.lab_id]
        assert (expected["system"], expected["coverage"], expected["stake_style"]) == (
            lab.system,
            lab.coverage,
            lab.stake_style,
        )
        assert (expected["capital"], expected["goal"], expected["prizes"]) == (
            lab.capital,
            lab.goal,
            list(lab.prizes),
        )
        assert (expected["window_start"], expected["window_end"]) == (
            lab.window_start,
            lab.window_end,
        )
        oracle = _reference_case(lab, inputs, votes)
        assert oracle == {key: expected[key] for key in oracle}, lab.lab_id
        result = run_reference_lab(
            lab,
            inputs.history,
            inputs.rankings,
            parity_votes=votes if lab.selection_kind == "parity" else None,
        )
        actual = {
            "eligible_draws": result.eligible_draws,
            "gaps": result.gaps,
            "first": result.first,
            "last": result.last,
            "totals": {name: getattr(result.totals, name) for name in expected["totals"]},
            "session_sha256": result.session_sha256,
            "session_count": len(result.sessions),
        }
        assert {key: expected[key] for key in actual} == actual, lab.lab_id
        assert result.totals.mean_net_closed == expected["totals"]["mean_net_closed"], lab.lab_id
        actual_payload = [
            (s.outcome, s.start_index, s.end_index, s.draws, s.final_balance, s.wagered, s.paid)
            for s in result.sessions
        ]
        assert _boundaries(actual_payload) == expected["boundary_sessions"], lab.lab_id


def test_independent_literal_bold_goal_reset_and_incomplete_tail():
    lab = ReferenceLab("synthetic", "parity", 1, "bold", "parity")
    history = SimpleNamespace(
        labels=(
            "2025-09-02 05:09",
            "2025-09-02 05:10",
            "2025-09-02 05:11",
            "2026-09-25 18:20",
            "2026-09-25 18:21",
        ),
        nums=np.asarray(
            [
                [9, 8, 7, 6, 5],
                [0, 90, 91, 92, 93],
                [1, 91, 92, 93, 94],
                [1, 91, 92, 93, 94],
                [0, 90, 91, 92, 93],
            ],
            dtype=np.uint8,
        ),
    )
    rankings = SimpleNamespace(row_ids=np.asarray([0, 1, 3, 4], dtype=np.int64))
    votes = np.asarray([0, 0, 0, 0, 0], dtype=np.int8)
    result = run_reference_lab(lab, history, rankings, parity_votes=votes)
    assert result.eligible_draws == 2
    assert result.gaps == 1
    assert result.first == "2025-09-02 05:10"
    assert result.last == "2026-09-25 18:20"
    # The first eligible even number wins; the window-end odd number misses.
    assert [
        (s.outcome, s.start_index, s.end_index, s.draws, s.final_balance, s.wagered, s.paid)
        for s in result.sessions
    ] == [
        ("goal", 0, 0, 1, 2869, 11, 880),
        ("incomplete", 1, 1, 1, 1989, 11, 0),
    ]
    assert result.totals.total_steps == 2
    assert result.totals.total_wagered == 22
    assert result.totals.total_paid == 880
    assert result.totals.total_net == 858


def test_independent_literal_bold_accumulates_payouts_at_multiple_positions():
    lab = ReferenceLab("synthetic", "parity", 1, "bold", "parity")
    history = SimpleNamespace(
        labels=("2025-09-02 05:10",),
        nums=np.asarray([[0, 90, 0, 92, 93]], dtype=np.uint8),
    )
    rankings = SimpleNamespace(row_ids=np.asarray([0], dtype=np.int64))
    result = run_reference_lab(lab, history, rankings, parity_votes=np.asarray([0], dtype=np.int8))
    assert [(s.outcome, s.draws, s.final_balance, s.wagered, s.paid) for s in result.sessions] == [
        ("goal", 1, 2913, 11, 924)
    ]
    assert result.totals.total_paid == 924
    assert result.totals.total_net == 913


def test_independent_literal_ladder_round_progression_affordability_and_reset():
    lab = ReferenceLab("synthetic", "parity", 50, "ladder", "parity")
    labels = tuple(f"2025-09-02 05:{10 + i:02d}" for i in range(5))
    history = SimpleNamespace(
        labels=labels,
        nums=np.asarray([[1, 3, 5, 7, 9]] * 5, dtype=np.uint8),
    )
    rankings = SimpleNamespace(row_ids=np.arange(5, dtype=np.int64))
    votes = np.zeros(5, dtype=np.int8)  # even-number set: all five outcomes miss
    result = run_reference_lab(lab, history, rankings, parity_votes=votes)
    assert [
        (s.outcome, s.start_index, s.end_index, s.draws, s.final_balance, s.wagered, s.paid)
        for s in result.sessions
    ] == [
        ("ruin", 0, 3, 4, 750, 1250, 0),
        ("incomplete", 4, 4, 1, 1950, 50, 0),
    ]
    assert result.totals.completed == 1
    assert result.totals.ruins == 1
    assert result.totals.incomplete == 1
    assert result.totals.total_steps == 5
    assert result.totals.total_wagered == 1300
    assert result.totals.total_paid == 0
    assert result.totals.total_net == -1300


def test_independent_literal_flat_uses_single_stake_and_keeps_censored_loss():
    lab = ReferenceLab("synthetic", "parity", 50, "flat", "parity")
    history = SimpleNamespace(
        labels=("2025-09-02 05:10",),
        nums=np.asarray([[1, 3, 5, 7, 9]], dtype=np.uint8),
    )
    rankings = SimpleNamespace(row_ids=np.asarray([0], dtype=np.int64))
    result = run_reference_lab(lab, history, rankings, parity_votes=np.asarray([0], dtype=np.int8))
    assert [
        (s.outcome, s.start_index, s.end_index, s.draws, s.final_balance, s.wagered, s.paid)
        for s in result.sessions
    ] == [("incomplete", 0, 0, 1, 1950, 50, 0)]
    assert result.totals.completed == 0
    assert result.totals.incomplete == 1
    assert result.totals.mean_net_closed is None
    assert result.totals.total_net == -50


def test_golden_provenance_pins_actual_reference_inputs_and_sources():
    provenance = GOLDEN["provenance"]
    assert provenance["history"]["relative_path"] == "chance_express_history.json"
    assert provenance["history"]["sha256"] == HISTORY_SHA256
    assert provenance["rankings"]["relative_path"] == (
        "repo_ref/reports/chance_rank_v1/predictions/pos1.npz"
    )
    assert provenance["rankings"]["sha256"] == RANKINGS_SHA256
    source_files = provenance["sources"]
    assert "repo_ref/quiniela_compare.py" in source_files
    assert "repo_ref/quiniela_sim.py" in source_files
    assert "repo_ref/strategy_tests/rules.py" in source_files
    assert "repo_ref/simuladores/runner.py" in source_files
    assert len([path for path in source_files if path.endswith("/ejecutar.py")]) == 14
    for relative_path, expected_sha in source_files.items():
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected_sha, relative_path
    assert GOLDEN["reference_contract"] == {
        "capital": 2000,
        "goal": 2800,
        "prizes": [80, 8, 4, 2, 1],
        "window_start": "2025-09-02 05:10",
        "window_end": "2026-09-25 18:20",
        "ranked_draws": 65235,
        "gaps": 6543,
        "history_draws": 105426,
        "ranked_first": "2025-09-02 05:10",
        "ranked_last": "2026-09-25 18:20",
    }


def test_golden_baseline_first_laboratory_remains_exactly_frozen():
    first = GOLDEN["laboratories"][0]
    assert first["lab_id"] == "transicion_1_audaz"
    assert first["eligible_draws"] == 65235
    assert first["gaps"] == 6543
    assert first["totals"]["completed"] == 963
    assert first["totals"]["goals"] == 681
    assert first["totals"]["ruins"] == 282
    assert first["totals"]["incomplete"] == 1
    assert first["totals"]["total_wagered"] == 1182452
    assert first["totals"]["total_paid"] == 1190701
    assert first["totals"]["total_net"] == 8249
    assert first["session_sha256"] == (
        "e7e9d68a1ac0078b4e5a42366f6e989f8b4871f95cb6673717c17839ba69fbc4"
    )
