import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from laboratorio.domain.reference_labs import REFERENCE_LABS, get_reference_lab
from laboratorio.engine.reference_labs import run_reference_lab

ROOT = Path(__file__).resolve().parents[3]


def test_catalog_is_immutable_and_has_the_fourteen_archived_scenarios():
    assert tuple(lab.lab_id for lab in REFERENCE_LABS) == (
        "transicion_1_audaz",
        "frios_1_audaz",
        "selector_1_audaz",
        "mezclas_1_audaz",
        "ensemble_5_audaz",
        "ensemble_10_audaz",
        "ensemble_20_audaz",
        "frios_25_escalera",
        "mezclas_50_audaz",
        "transicion_50_audaz",
        "paridad_50_audaz",
        "frios_50_escalera",
        "paridad_50_escalera",
        "paridad_50_plana",
    )
    assert tuple(
        (lab.system, lab.coverage, lab.stake_style, lab.selection_kind) for lab in REFERENCE_LABS
    ) == (
        ("transition", 1, "bold", "ranking"),
        ("cold", 1, "bold", "ranking"),
        ("select_interpretable", 1, "bold", "ranking"),
        ("mix", 1, "bold", "ranking"),
        ("ensemble", 5, "bold", "ranking"),
        ("ensemble", 10, "bold", "ranking"),
        ("ensemble", 20, "bold", "ranking"),
        ("cold", 25, "ladder", "ranking"),
        ("mix", 50, "bold", "ranking"),
        ("transition", 50, "bold", "ranking"),
        ("parity", 50, "bold", "parity"),
        ("cold", 50, "ladder", "ranking"),
        ("parity", 50, "ladder", "parity"),
        ("parity", 50, "flat", "parity"),
    )
    assert all(
        (lab.capital, lab.goal, lab.prizes, lab.window_start, lab.window_end)
        == (2000, 2800, (80, 8, 4, 2, 1), "2025-09-02 05:10", "2026-09-25 18:20")
        for lab in REFERENCE_LABS
    )
    assert get_reference_lab("transicion_1_audaz") is REFERENCE_LABS[0]


@pytest.mark.parametrize("lab", [lab for lab in REFERENCE_LABS if lab.selection_kind == "ranking"])
@pytest.mark.parametrize("has_archived_row", [True, False])
def test_ranking_lab_with_no_eligible_draws_returns_empty_result(lab, has_archived_row):
    label = "2025-09-02 05:10" if not has_archived_row else "2025-09-01 05:10"
    history = SimpleNamespace(labels=(label,), nums=np.asarray([[0, 1, 2, 3, 4]]))
    row_ids = np.asarray([0]) if has_archived_row else np.asarray([], dtype=np.int64)
    rankings = SimpleNamespace(
        row_ids=row_ids,
        family=lambda system: np.tile(np.arange(100, dtype=np.uint8), (len(row_ids), 1)),
    )

    result = run_reference_lab(lab, history, rankings)

    assert result.sessions == ()
    assert result.totals.completed == 0
    assert result.totals.incomplete == 0
    assert result.totals.goals == 0
    assert result.totals.ruins == 0
    assert result.totals.sessions_total == 0
    assert result.totals.total_wagered == 0
    assert result.totals.total_paid == 0
    assert result.totals.total_net == 0
    assert result.totals.total_steps == 0
    assert result.totals.mean_net_closed is None
    assert result.eligible_draws == 0
    assert result.gaps == 0
    assert result.first is None
    assert result.last is None
    assert result.session_sha256 == (
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    )


def test_parity_lab_requires_aligned_binary_causal_votes():
    history = SimpleNamespace(labels=("2025-09-02 05:10",), nums=np.asarray([[0, 1, 2, 3, 4]]))
    rankings = SimpleNamespace(row_ids=np.asarray([0]))
    lab = get_reference_lab("paridad_50_audaz")
    with pytest.raises(ValueError, match="requires one causal vote"):
        run_reference_lab(lab, history, rankings)
    with pytest.raises(ValueError, match="binary value"):
        run_reference_lab(lab, history, rankings, parity_votes=np.asarray([2]))


def test_first_lab_matches_readonly_reference_oracle():
    sys.path[:0] = [str(ROOT), str(ROOT / "repo_ref"), str(ROOT / "main")]
    import importlib

    compare = importlib.import_module("quiniela_compare")
    sim = importlib.import_module("quiniela_sim")
    runner = importlib.import_module("simuladores.runner")
    historical_scenario = compare.historical_scenario
    ranking_family = compare.ranking_family
    replay = compare.replay
    selected_payments = compare.selected_payments
    load_validated_history = sim.load_validated_history
    HISTORY = ROOT / "chance_express_history.json"
    RANKINGS = ROOT / "repo_ref/reports/chance_rank_v1/predictions/pos1.npz"
    ranking_context = runner.ranking_context

    from laboratorio.engine.adapter import load_history, load_rankings
    from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256

    runner.verify_input(HISTORY, runner.HISTORY_SHA256)
    runner.verify_input(RANKINGS, runner.RANKINGS_SHA256)
    oracle_history = load_validated_history(HISTORY)
    context = ranking_context(oracle_history, RANKINGS)
    oracle_row = historical_scenario(
        oracle_history, RANKINGS, "transition", 1, "bold", context=context
    )
    oracle_ranks = ranking_family(RANKINGS, "transition", context)
    payments, first_hits = selected_payments(
        oracle_history.nums[context.row_ids], oracle_ranks, 1, "all"
    )
    oracle_sessions = replay("bold", 1, payments, first_hits)

    history = load_history(HISTORY, HISTORY_SHA256)
    rankings = load_rankings(RANKINGS, RANKINGS_SHA256, history)
    assert history.sha256 == HISTORY_SHA256
    result = run_reference_lab(get_reference_lab("transicion_1_audaz"), history, rankings)
    oracle_payload = []
    start = 0
    for session in oracle_sessions:
        outcome = "goal" if session.reached else "ruin" if session.ruined else "incomplete"
        end = start + session.steps - 1
        oracle_payload.append(
            (
                outcome,
                start,
                end,
                session.steps,
                session.final_balance,
                session.wagered,
                session.paid,
            )
        )
        start = end + 1
    import hashlib
    import json

    oracle_digest = hashlib.sha256(
        json.dumps(oracle_payload, separators=(",", ":")).encode()
    ).hexdigest()
    assert result.session_sha256 == oracle_digest
    assert result.totals.total_steps == oracle_row["total_steps"]
    assert result.totals.completed == oracle_row["completed"]
    assert result.totals.incomplete == oracle_row["incomplete"]
    assert result.totals.goals == oracle_row["goal_count"]
    assert result.totals.ruins == oracle_row["ruin_count"]
    assert result.totals.total_wagered == oracle_row["total_stake"]
    assert result.totals.total_paid == oracle_row["total_paid"]
    assert result.totals.total_net == oracle_row["total_net"]
    assert len(result.sessions) == len(oracle_sessions)
    assert result.eligible_draws == 65235
    assert result.gaps == context.gaps == 6543
    assert len(oracle_history.nums) == 105426
    assert result.first == "2025-09-02 05:10"
    assert result.last == "2026-09-25 18:20"
    assert result.totals.completed == 963
    assert result.totals.incomplete == 1
    assert result.totals.goals == 681
    assert result.totals.ruins == 282
    assert result.totals.sessions_total == 964
    assert result.totals.total_wagered == 1182452
    assert result.totals.total_paid == 1190701
    assert result.totals.total_net == 8249
    assert result.totals.total_steps == 65235
    assert result.totals.mean_net_closed == 10.28348909657321
    assert oracle_row["mean_net"] == 10.28348909657321
    assert round(oracle_row["mean_net"], 1) == 10.3
    assert tuple(
        (s.outcome, s.draws, s.final_balance, s.wagered, s.paid) for s in result.sessions[:3]
    ) == (
        ("goal", 60, 2802, 822, 1624),
        ("goal", 33, 2816, 392, 1208),
        ("goal", 12, 2873, 133, 1006),
    )
    assert (
        result.sessions[-1].outcome,
        result.sessions[-1].draws,
        result.sessions[-1].final_balance,
        result.sessions[-1].wagered,
        result.sessions[-1].paid,
    ) == ("incomplete", 105, 346, 2163, 509)
    assert result.session_sha256 == (
        "e7e9d68a1ac0078b4e5a42366f6e989f8b4871f95cb6673717c17839ba69fbc4"
    )
