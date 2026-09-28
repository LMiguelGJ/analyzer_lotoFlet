"""Single-history analysis pipeline: fixed system/Holm order, per-fold selection,
primary contrasts, a scoped secondary check, control-stream contrasts, source-restart,
and the resume/protocol-hash checkpoint mechanics.

Scope note: this covers exactly the test groups requested for this unit. The full
``analyze_secondary`` descriptive suite (waits/Kaplan-Meier, prob_summary, breakdowns,
ablation deltas, hit_correlation/jaccard) and the full ``run_interpretable`` control
orchestration (60 control streams, budget stops, run-log JSONL) are out of scope here;
see the handoff report for what remains open.
"""

import json
import os
import weakref
from datetime import date, timedelta

import numpy as np
import pytest

from chance_rank import controls, engine, pipeline, protocol, supervised, walkforward
from chance_rank.data import make_history


def _daily_history(n_days, rows_per_day, seed_label, host="premios.do", second_host=None,
                    second_host_from_day=None):
    generator = protocol.rng(seed_label)
    entries = []
    for d in range(n_days):
        iso = (date(2024, 1, 1) + timedelta(days=d)).isoformat()
        source = host
        if second_host is not None and second_host_from_day is not None and d >= second_host_from_day:
            source = second_host
        for r in range(rows_per_day):
            hour, minute = divmod(5 + r * 5, 60)
            nums = generator.integers(0, 100, size=5).tolist()
            entries.append((iso, f"{hour:02d}:{minute:02d}", nums, source))
    return make_history(entries)


def _explicit_folds(n_days, n_folds=2, test_block=6):
    """Small deterministic folds spanning the whole synthetic calendar."""
    folds = []
    start = n_days - n_folds * test_block
    for j in range(n_folds):
        a = start + j * test_block
        b = a + test_block
        inner = ((max(0, a - 12), max(0, a - 8)), (max(0, a - 8), max(0, a - 4)), (max(0, a - 4), a))
        folds.append(walkforward.Fold(index=j, test_days=(a, b), inner=inner))
    return folds


_SUBSET_CONFIGS = [
    "freq_hist:scope=position,window=none",
    "cold:scope=position",
    "decay:half_life=20",
    "transition:lam=100",
    "freq_recent:window=500",
]


# --- 1. system order / 32-contrast family fixed; N/A counted as p=1, stage partial ---

def test_systems_order_is_12_interpretable_plus_2_supervised_plus_2_selectors():
    expected = (*protocol.INTERPRETABLE_FAMILIES, "logistic", "tree",
                "select_interpretable", "select_all")
    assert expected == pipeline.SYSTEMS
    assert len(pipeline.SYSTEMS) == 16


def test_primary_holm_family_is_32_fixed_system_baseline_pairs():
    assert len(pipeline.PRIMARY_HOLM_FAMILY) == 32
    assert pipeline.PRIMARY_HOLM_FAMILY[0] == (pipeline.SYSTEMS[0], "uniform")
    assert pipeline.PRIMARY_HOLM_FAMILY[1] == (pipeline.SYSTEMS[0], "recent500")
    assert pipeline.PRIMARY_HOLM_FAMILY[-1] == (pipeline.SYSTEMS[-1], "recent500")


def test_analyze_primary_marks_absent_families_na_p1_and_stage_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-na")
    folds = _explicit_folds(len(h.dates))
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")

    result = pipeline.analyze_primary(h, store, folds, reps=200)

    assert result["stage"] == "partial"
    present_families = {"freq_hist", "cold", "decay", "transition", "freq_recent", "select_interpretable"}
    for system in pipeline.SYSTEMS:
        entry = result["systems"][system]
        if system in present_families:
            assert entry["available"] is True
        else:
            assert entry["available"] is False
            assert entry["classification"]["label"] == "no_disponible"

    # every absent system contributes as "available: False" (=> p=1 in Holm, D-stage partial)
    for system in pipeline.SYSTEMS:
        if system not in present_families:
            assert result["systems"][system].get("uniform") is None
    assert isinstance(result["mde"]["mde"], float)
    assert result["n_primary_targets"] > 0


def test_control_holm_keeps_32_slots_instead_of_24(monkeypatch):
    h = _daily_history(10, 3, "fixed-family")
    folds = _explicit_folds(10, 1, 3)
    monkeypatch.setattr(protocol, "WARMUP", 0)
    cid = pipeline.RECENT500_ID
    hits = np.zeros((1, h.n), dtype=bool)

    def contrast(*_args):
        result = {"available": True, "sensitivity": {"L1": {"p": 1.0}, "L14": {"p": 1.0}}}
        for baseline in pipeline.BASELINES_PRIMARY:
            result[baseline] = {"p": 0.001, "delta": 0.01, "fold_share": None}
        return result

    monkeypatch.setattr(pipeline, "_one_system_contrasts", contrast)
    monkeypatch.setattr(pipeline.inference, "classify", lambda _entry: {"label": "test"})
    full, *_ = pipeline._systems_contrast(h, [cid], ["freq_recent"], hits, folds,
                                            pipeline.SYSTEMS, reps=10)
    reduced, *_ = pipeline._systems_contrast(h, [cid], ["freq_recent"], hits, folds,
                                               pipeline.SYSTEMS[:12], reps=10)
    assert len(full) == 16
    assert full["logistic"]["available"] is False
    assert full["select_all"]["available"] is False
    assert full["freq_recent"]["uniform"]["p_adj"] == pytest.approx(0.032)
    assert reduced["freq_recent"]["uniform"]["p_adj"] == pytest.approx(0.024)


# --- 2. per-fold selection uses only inner rows; system hits == chosen config hits ---

def test_per_fold_choice_uses_inner_rows_only_and_hits_match_chosen_config(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-leakage")
    folds = _explicit_folds(len(h.dates))
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")
    hits = pipeline.target_hits(store["ranks_updated"], protocol.PRIMARY_K)
    config_ids, families_of = pipeline.candidate_entries(store["config_ids"].tolist())
    index = {cid: i for i, cid in enumerate(config_ids)}
    candidate_hits = np.array([np.asarray(hits)[list(store["config_ids"]).index(cid)] for cid in config_ids])
    primary_rows = walkforward.primary_mask(h)

    picks, _scores, test_rows = pipeline.per_fold_choice(h, config_ids, families_of, candidate_hits,
                                                          folds, primary_rows)

    for fold in folds:
        row_idx = test_rows[fold.index]["row_idx"]
        for system, cid in picks[fold.index].items():
            if cid is None:
                continue
            expected = candidate_hits[index[cid]][row_idx]
            assert np.array_equal(test_rows[fold.index]["hits"][system], expected)

    # alter test-day nums only -> inner-selection choices are unchanged (leakage guard)
    altered_nums = h.nums.copy()
    threshold_day = folds[0].test_days[0]
    future_rows = h.day >= threshold_day
    generator = protocol.rng("test-pipeline-alter-future")
    altered_nums[future_rows] = generator.integers(0, 100, size=(future_rows.sum(), 5))
    h_altered = h.with_nums(altered_nums)
    engine.compute_target_store(h_altered, _SUBSET_CONFIGS, str(tmp_path / "altered"), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store_altered = engine.load_store(str(tmp_path / "altered"), "pos1")
    hits_altered = pipeline.target_hits(store_altered["ranks_updated"], protocol.PRIMARY_K)
    candidate_hits_altered = np.array([np.asarray(hits_altered)[list(store_altered["config_ids"]).index(cid)]
                                        for cid in config_ids])
    picks_altered, _s2, _t2 = pipeline.per_fold_choice(h_altered, config_ids, families_of,
                                                        candidate_hits_altered, folds, primary_rows)
    assert picks[0] == picks_altered[0]  # fold 0's inner window ends before threshold_day


# --- 3. analyze_primary detects a planted repeat signal in transition vs a uniform draw

def test_analyze_primary_detects_planted_transition_signal(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(80, 12, "test-pipeline-signal-base")
    signal_h, _info = controls.signal_history(h, "repeat", 1.0, 1)
    folds = _explicit_folds(len(h.dates))

    engine.compute_target_store(signal_h, _SUBSET_CONFIGS, str(tmp_path / "signal"), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store_signal = engine.load_store(str(tmp_path / "signal"), "pos1")
    result_signal = pipeline.analyze_primary(signal_h, store_signal, folds, reps=200)
    assert result_signal["systems"]["transition"]["uniform"]["delta"] > 0

    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path / "uniform"), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store_uniform = engine.load_store(str(tmp_path / "uniform"), "pos1")
    result_uniform = pipeline.analyze_primary(h, store_uniform, folds, reps=200)
    assert abs(result_uniform["systems"]["transition"]["uniform"]["delta"]) < 0.05


# --- 4. secondary: random baseline nested across K; frozen H1 == updated H1; dropped --

def test_random_baseline_nested_hits_across_k():
    h = _daily_history(10, 8, "test-pipeline-random")
    rows = np.arange(h.n)
    result, ranks = pipeline.random_baseline_nested(h, 0, (1, 5, 10, 25), rows)
    hits = {k: ranks < k for k in (1, 5, 10, 25)}
    assert np.all(hits[1] <= hits[5])
    assert np.all(hits[5] <= hits[10])
    assert np.all(hits[10] <= hits[25])
    assert result[25]["rate"] == pytest.approx(float(hits[25].mean()))


def test_analyze_secondary_h1_frozen_matches_updated_and_reports_dropped(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-secondary")
    folds = _explicit_folds(len(h.dates))
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")

    result = pipeline.analyze_secondary(h, {"pos1": store}, folds, realizations=(0, 1))
    horizon = result["targets"]["pos1"]["horizon"]
    for system in ("freq_hist", "cold", "decay", "transition", "freq_recent"):
        entry = horizon[system][1]  # H=1
        assert entry["updated"]["mean_hits"] == pytest.approx(entry["frozen"]["mean_hits"])
        assert entry["updated"]["p_at_least_one"] == pytest.approx(entry["frozen"]["p_at_least_one"])
        assert isinstance(entry["dropped"], int)
        assert entry["population"] >= 0
    assert horizon["logistic"] is None  # absent family -> N/A, not a crash


def test_analyze_secondary_topk_nested_monotone_in_k_per_system(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-secondary-topk")
    folds = _explicit_folds(len(h.dates))
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")

    result = pipeline.analyze_secondary(h, {"pos1": store}, folds, realizations=(0, 1))
    topk = result["targets"]["pos1"]["topk"]
    for system in ("freq_hist", "cold", "decay", "transition", "freq_recent", "select_interpretable"):
        rates = [topk[system][k]["rate"] for k in protocol.K_VALUES]
        assert rates == sorted(rates)  # non-decreasing in K (nested Top-K)
    assert topk["logistic"] is None


def test_analyze_secondary_random_baseline_mean_is_constant_realization_nested_across_k(tmp_path,
                                                                                          monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-secondary-random")
    folds = _explicit_folds(len(h.dates))
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")

    result = pipeline.analyze_secondary(h, {"pos1": store}, folds, realizations=(0, 1, 2))
    random_baseline = result["targets"]["pos1"]["baselines"]["random"]
    means = [random_baseline[k]["mean"] for k in protocol.K_VALUES]
    assert means == sorted(means)
    for k in protocol.K_VALUES:
        assert random_baseline[k]["p2_5"] <= random_baseline[k]["mean"] <= random_baseline[k]["p97_5"]


def test_analyze_secondary_ablation_delta_equals_rate_minus_parent_rate(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-secondary-ablation")
    folds = _explicit_folds(len(h.dates))
    parent_id = protocol.config_id("notebook", {"weights": [0.45, 0.45, 0.10], "window": 20})
    configs = [*_SUBSET_CONFIGS, parent_id]
    engine.compute_target_store(h, configs, str(tmp_path), positions=(0,), include_any=False,
                                 ablations=True, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")

    result = pipeline.analyze_secondary(h, {"pos1": store}, folds, realizations=(0,))
    ablations = result["targets"]["pos1"]["ablations"]
    entry = ablations["ablation:notebook-no_hist,window=20"]
    assert entry["parent"] == parent_id
    assert entry["delta"] == pytest.approx(entry["rate"] - entry["parent_rate"])


def test_analyze_secondary_prob_summary_excludes_non_probabilistic_picks(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-secondary-prob")
    folds = _explicit_folds(len(h.dates))
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")

    result = pipeline.analyze_secondary(h, {"pos1": store}, folds, realizations=(0,))
    prob = result["targets"]["pos1"]["prob_summary"]
    # "cold" is not a probabilistic family: fully excluded, none of its rows enter the summary
    assert prob["cold"]["available"] is False
    assert prob["cold"]["excluded"] > 0
    # "freq_hist" is probabilistic: included, no exclusions
    assert prob["freq_hist"]["available"] is True
    assert prob["freq_hist"]["excluded"] == 0
    assert prob["freq_hist"]["n"] > 0


def test_analyze_secondary_jaccard_skipped_d13_hit_correlation_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-secondary-jaccard")
    folds = _explicit_folds(len(h.dates))
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")

    result = pipeline.analyze_secondary(h, {"pos1": store}, folds, realizations=(0,))
    cross_system = result["cross_system_pos1"]
    assert cross_system["jaccard"] == "skipped: memory budget (D13)"
    assert "cold|freq_hist" in cross_system["hit_correlation"]
    for value in cross_system["hit_correlation"].values():
        assert value is None or -1.0 <= value <= 1.0


def test_jaccard_and_hit_correlation_never_recomputes_scores(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-jaccard-no-recompute")
    folds = _explicit_folds(len(h.dates))
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")
    hits = pipeline.target_hits(store["ranks_updated"], protocol.PRIMARY_K)
    config_ids, families_of = pipeline.candidate_entries(store["config_ids"].tolist())
    index_of_all = {cid: i for i, cid in enumerate(store["config_ids"].tolist())}
    candidate_hits = np.array([np.asarray(hits)[index_of_all[cid]] for cid in config_ids])
    primary_rows = walkforward.primary_mask(h)
    _picks, _scores, test_rows = pipeline.per_fold_choice(h, config_ids, families_of, candidate_hits,
                                                           folds, primary_rows)

    def _boom(*_args, **_kwargs):
        raise AssertionError("score_config must not be called (D13: no recomputation path)")
    monkeypatch.setattr(pipeline.models, "score_config", _boom)

    result = pipeline.jaccard_and_hit_correlation(test_rows, folds)

    assert result["jaccard"] == "skipped: memory budget (D13)"
    expected = pipeline.hit_correlation_matrix(test_rows, folds, protocol.INTERPRETABLE_FAMILIES)
    assert result["hit_correlation"] == expected


# --- 5. resume: second call skips completed steps; a protocol hash change raises ------

def test_run_interpretable_resumes_and_raises_on_protocol_hash_change(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-resume")
    folds = _explicit_folds(len(h.dates))
    outdir = str(tmp_path / "run")

    result_1 = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                           reps=50, run_controls=False)
    assert result_1["status"] == "completed"
    assert set(result_1["steps"]) == set(pipeline._MAIN_STEPS)

    def _boom(*args, **kwargs):
        raise AssertionError("should not recompute a completed step")

    monkeypatch.setattr(pipeline, "analyze_primary", _boom)
    result_2 = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                           reps=50, run_controls=False)
    # JSON round-trips tuples as lists, so compare the checkpointed result normalized
    assert json.loads(json.dumps(result_2["steps"]["primary"])) == \
        json.loads(json.dumps(result_1["steps"]["primary"]))

    monkeypatch.undo()  # restore analyze_primary and WARMUP before changing protocol state
    monkeypatch.setattr(protocol, "WARMUP", 20)
    monkeypatch.setattr(protocol, "ALPHA", 0.05)
    with pytest.raises(ValueError):
        pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                    reps=50, run_controls=False)


def test_run_interpretable_mde_step_precedes_primary_in_run_log(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-mde-order")
    folds = _explicit_folds(len(h.dates))
    outdir = str(tmp_path / "run")

    pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                               reps=50, run_controls=False)

    assert os.path.exists(os.path.join(outdir, "steps", "mde.json"))
    assert os.path.exists(os.path.join(outdir, "protocol.json"))
    with open(os.path.join(outdir, "run_log.jsonl"), encoding="utf-8") as f:
        log_lines = [json.loads(line) for line in f]
    steps_in_order = [line["step"] for line in log_lines]
    assert steps_in_order.index("mde") < steps_in_order.index("primary")
    assert steps_in_order.index("primary") < steps_in_order.index("secondary")
    for line in log_lines:
        assert line["status"] == "completed"
        assert isinstance(line["seconds"], float)


def test_run_interpretable_stops_cleanly_at_zero_time_budget_then_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-timebox")
    folds = _explicit_folds(len(h.dates))
    outdir = str(tmp_path / "run")

    stopped = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                          reps=50, run_controls=False, max_seconds=0)
    assert stopped["status"] == "partial"
    assert stopped["reason"] == "time budget"
    assert stopped["next_step"] == pipeline._MAIN_STEPS[0]
    with open(os.path.join(outdir, "status.json"), encoding="utf-8") as f:
        status = json.load(f)
    assert status["state"] == "partial"

    resumed = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                          reps=50, run_controls=False)
    assert resumed["status"] == "completed"
    assert set(resumed["steps"]) == set(pipeline._MAIN_STEPS)


def test_run_interpretable_stops_when_disk_is_low_before_store(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-disk")
    folds = _explicit_folds(len(h.dates))
    outdir = str(tmp_path / "run")

    class _LowDisk:
        free = 1

    monkeypatch.setattr(pipeline.shutil, "disk_usage", lambda path: _LowDisk())
    result = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                         reps=50, run_controls=False)
    assert result["status"] == "partial"
    assert result["reason"] == "insufficient disk"
    assert result["next_step"] == "store"
    assert not os.path.exists(os.path.join(outdir, "store"))


def test_run_interpretable_resumes_control_streams_individually(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    monkeypatch.setattr(protocol, "HEALTHY_STREAMS", 2)
    monkeypatch.setattr(protocol, "SIGNAL_TYPES", ("repeat",))
    monkeypatch.setattr(protocol, "SIGNAL_Q", (0.10,))
    monkeypatch.setattr(protocol, "SIGNAL_SEEDS", 1)
    monkeypatch.setattr(protocol, "ORDER_PERMUTATIONS", 2)
    h = _daily_history(80, 12, "test-pipeline-controls-resume")
    folds = _explicit_folds(len(h.dates))
    outdir = str(tmp_path / "run")

    result_1 = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS, reps=50)
    assert result_1["status"] == "completed"
    expected_names = {pipeline._control_stream_id(e) for e in pipeline._control_stream_names()}
    assert set(result_1["controls"]) == expected_names
    assert result_1["steps"]["metrics"]["status"] == "partial: supervised pending"

    def _boom(*args, **kwargs):
        raise AssertionError("should not recompute a completed control stream")

    monkeypatch.setattr(pipeline, "run_control", _boom)
    result_2 = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS, reps=50)
    assert result_2["status"] == "completed"
    assert set(result_2["controls"]) == expected_names


def test_run_interpretable_control_protocol_hash_mismatch_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    monkeypatch.setattr(protocol, "HEALTHY_STREAMS", 1)
    monkeypatch.setattr(protocol, "SIGNAL_TYPES", ("repeat",))
    monkeypatch.setattr(protocol, "SIGNAL_Q", (0.10,))
    monkeypatch.setattr(protocol, "SIGNAL_SEEDS", 1)
    monkeypatch.setattr(protocol, "ORDER_PERMUTATIONS", 1)
    h = _daily_history(80, 12, "test-pipeline-controls-hash")
    folds = _explicit_folds(len(h.dates))
    outdir = str(tmp_path / "run")

    result_1 = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS, reps=50)
    assert result_1["status"] == "completed"

    monkeypatch.setattr(protocol, "ALPHA", 0.05)
    with pytest.raises(ValueError):
        pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS, reps=50)


def test_export_checkpoint_follows_secondary_and_resume_preserves_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-export")
    folds = _explicit_folds(len(h.dates))
    outdir = str(tmp_path / "run")
    result = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                        reps=50, run_controls=False)
    assert result["status"] == "completed"
    from chance_rank import artifacts
    pred = artifacts.predictions_path(outdir, "pos1")
    with np.load(pred) as data:
        order = data["ranking100__freq_hist"]
        rows = data["row_ids"]
        assert "y_true" not in data.files
        assert "winner_rank__freq_hist" not in data.files
    with np.load(artifacts.results_path(outdir, "pos1")) as actual:
        assert np.array_equal((order == h.nums[rows, 0, None]).argmax(axis=1),
                              actual["winner_rank__freq_hist"])
    assert os.path.exists(artifacts.schema_path(outdir))
    before = os.stat(pred).st_mtime_ns
    monkeypatch.setattr(artifacts, "export_all", lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("recompute")))
    pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                               reps=50, run_controls=False)
    assert os.stat(pred).st_mtime_ns == before
    with open(os.path.join(outdir, "run_log.jsonl"), encoding="utf-8") as f:
        steps = [json.loads(line)["step"] for line in f]
    assert steps.index("secondary") < steps.index("export") < steps.index("source_restart")
    with pytest.raises(ValueError, match="data sha changed"):
        pipeline._step_done(outdir, "export", "other")


def test_export_step_releases_previous_target_store_before_next(tmp_path, monkeypatch):
    """The export step never holds more than one target's store array set in memory:
    each target's store is released (and garbage-collected) before the next target's
    store is exported."""
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(30, 8, "test-pipeline-export-memory")
    folds = _explicit_folds(len(h.dates), n_folds=1, test_block=4)
    outdir = str(tmp_path / "run")
    from chance_rank import artifacts

    weakrefs = []
    original = artifacts.export_one_target

    def wrapped(history, outdir_arg, target_name, store, folds_arg, primary_rows=None,
               systems=pipeline.SYSTEMS):
        for prior_target, ref in weakrefs:
            assert ref() is None, (
                f"store for target {prior_target!r} was still alive in memory while "
                f"exporting {target_name!r}")
        result = original(history, outdir_arg, target_name, store, folds_arg,
                          primary_rows=primary_rows, systems=systems)
        weakrefs.append((target_name, weakref.ref(store["ranks_updated"])))
        return result

    monkeypatch.setattr(artifacts, "export_one_target", wrapped)
    result = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                        reps=50, run_controls=False)

    assert result["status"] == "completed"
    assert [t for t, _ref in weakrefs] == list(protocol.TARGETS)


def test_export_step_resumes_only_remaining_targets_after_partial_crash(tmp_path, monkeypatch):
    """If the export step is killed after some targets finished, a resumed run must
    only recompute the targets that never got a per-target checkpoint -- not the whole
    monolithic export step."""
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-export-resume-per-target")
    folds = _explicit_folds(len(h.dates))
    outdir = str(tmp_path / "run")
    result = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                        reps=50, run_controls=False)
    assert result["status"] == "completed"

    from chance_rank import artifacts

    mtimes_before = {t: os.stat(artifacts.predictions_path(outdir, t)).st_mtime_ns
                     for t in protocol.TARGETS}

    # Simulate a crash that killed the process after pos1..pos4/any finished but
    # before pos5's per-target checkpoint (and the overall "export" checkpoint) were
    # written: drop only the overall step marker and pos5's sub-checkpoint.
    os.remove(pipeline._step_path(outdir, "export"))
    os.remove(pipeline._step_path(outdir, "export_pos5"))

    calls = []
    original = artifacts.export_one_target

    def tracking(history, outdir_arg, target_name, store, folds_arg, primary_rows=None,
                systems=pipeline.SYSTEMS):
        calls.append(target_name)
        return original(history, outdir_arg, target_name, store, folds_arg,
                        primary_rows=primary_rows, systems=systems)

    monkeypatch.setattr(artifacts, "export_one_target", tracking)
    result = pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                        reps=50, run_controls=False)

    assert result["status"] == "completed"
    assert calls == ["pos5"]
    for target in protocol.TARGETS:
        after = os.stat(artifacts.predictions_path(outdir, target)).st_mtime_ns
        if target == "pos5":
            assert after != mtimes_before[target]
        else:
            assert after == mtimes_before[target]
    with open(artifacts.schema_path(outdir), encoding="utf-8") as f:
        schema = json.load(f)
    assert set(schema["targets"]) == set(protocol.TARGETS)


@pytest.mark.skipif(os.environ.get("CHANCE_RANK_BENCH") != "1", reason="explicit synthetic benchmark only")
def test_export_step_memory_budget_synthetic_20k_rows():
    """Opt-in per-target export memory check: fabricated store arrays with the real protocol
    config-id set (110 configs, matching a real store built with ablations), real
    calendar-prefix timestamps, and synthetic rank values -- avoids paying for a full
    (expensive) synthetic store computation while still exercising the export step's true
    per-target array shapes for a 20,000-row history, the full 16-entry ``pipeline.SYSTEMS``
    set, and a real walk-forward fold. Asserts peak process RSS stays under the 1.5 GiB safety threshold and
    the whole check finishes within the 300s hard cap; extrapolates (linear, labeled
    ESTIMATE) to the real 105,426-row history.
    """
    import dataclasses
    import gc
    import tempfile
    import time
    from pathlib import Path

    import psutil

    from chance_rank import artifacts, models
    from chance_rank.data import load_history

    real_path = Path(__file__).resolve().parent.parent / "chance_express_history.json"
    if not real_path.exists():
        pytest.skip("chance_express_history.json not present")

    start = time.monotonic()
    n_rows = 20000
    real_h = load_history(real_path, expected_sha=None)
    n_rows = min(n_rows, real_h.n)
    prefix = dataclasses.replace(
        real_h, nums=real_h.nums[:n_rows], day=real_h.day[:n_rows], slot=real_h.slot[:n_rows],
        hour=real_h.hour[:n_rows], weekday=real_h.weekday[:n_rows], day_pos=real_h.day_pos[:n_rows],
        source=real_h.source[:n_rows], eligible=real_h.eligible[:n_rows],
        segment=real_h.segment[:n_rows], sha256="synthetic-calendar-prefix", provenance={})
    synthetic_nums = protocol.rng("chance-rank-v1/export-mem-bench").integers(0, 100, size=(n_rows, 5))
    h = prefix.with_nums(synthetic_nums)

    interp_ids = [cid for cid, _family, _params in protocol.all_configs(False)]
    ablation_ids = [aid for aid, _kind, _params in models.ABLATIONS]
    config_ids = interp_ids + ablation_ids
    n_cfg = len(config_ids)

    all_folds = walkforward.outer_folds(len(h.dates))
    folds = [f for f in all_folds if f.test_days[1] <= len(h.dates)][:1]
    assert folds, "synthetic 20k-row calendar prefix produced no usable folds"

    rng = protocol.rng("chance-rank-v1/export-mem-bench-store")
    process = psutil.Process()
    peak = process.memory_info().rss
    with tempfile.TemporaryDirectory(prefix="chance-rank-export-bench-") as workdir:
        for target in protocol.TARGETS:
            if target == "any":
                ranks_updated = rng.integers(0, 100, size=(n_cfg, n_rows, 5)).astype(np.uint8)
                ranks_frozen = np.empty((n_cfg, 0, 20, 5), dtype=np.uint8)
            else:
                ranks_updated = rng.integers(0, 100, size=(n_cfg, n_rows)).astype(np.uint8)
                ranks_frozen = np.empty((n_cfg, 0, 20), dtype=np.uint8)
            p_true = np.full((n_cfg, n_rows), np.nan, dtype=np.float32)
            engine._atomic_save_npz(
                engine._target_path(workdir, target), config_ids=np.array(config_ids),
                ranks_updated=ranks_updated, blocks=np.empty(0, dtype=np.int64),
                fold_id_per_block=np.empty(0, dtype=np.int64), ranks_frozen=ranks_frozen,
                dropped_per_fold=np.zeros(len(folds), dtype=np.int64),
                p_true=p_true, topk_mass=p_true.copy(), brier=p_true.copy())
            peak = max(peak, process.memory_info().rss)
            del ranks_updated, ranks_frozen, p_true
            gc.collect()

        primary_rows = walkforward.primary_mask(h)
        manifest = {}
        for target in protocol.TARGETS:
            store = engine.load_store(workdir, target)
            manifest[target] = artifacts.export_one_target(h, workdir, target, store, folds,
                                                            primary_rows=primary_rows,
                                                            systems=pipeline.SYSTEMS)
            del store
            gc.collect()
            peak = max(peak, process.memory_info().rss)

    elapsed = time.monotonic() - start
    peak_gib = peak / 1024 ** 3
    extrapolated_gib = peak_gib * (105426 / n_rows)  # linear estimate, documented as such
    print(f"export step synthetic bench: rows={n_rows} n_cfg={n_cfg} folds={len(folds)} "
          f"seconds={elapsed:.1f} peak_rss_gib={peak_gib:.3f} "
          f"extrapolated_105426_rows_peak_rss_gib_ESTIMATE={extrapolated_gib:.3f}")
    assert elapsed < 300
    assert peak_gib < 1.5
    assert set(manifest) == set(protocol.TARGETS)


# --- 6. control runner schema and gate wiring; control store deleted after analysis --

def test_run_control_schema_and_gate_wiring(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-pipeline-control-base")
    folds = _explicit_folds(len(h.dates))
    healthy_h = controls.healthy_history(h, 1)
    workdir = str(tmp_path / "control")

    result = pipeline.run_control(healthy_h, workdir, folds, _SUBSET_CONFIGS, reps=200)

    assert "systems" in result and "recent_decay" in result["systems"]
    assert result["holm_family_order"] == list(pipeline.PRIMARY_HOLM_FAMILY)
    for name in ("logistic", "tree", "select_all"):
        assert result["systems"][name]["available"] is False
    assert result["signal_holm_family_order"] == [(s, "uniform") for s in
        ("transition", "carry", "time", "recent_decay", "category")]
    assert len(result["signal_systems"]) == 5
    signal_p = [result["signal_systems"][s]["uniform"]["p"]
                if result["signal_systems"][s]["available"] else None
                for s, _ in result["signal_holm_family_order"]]
    from chance_rank import inference
    expected = inference.holm(signal_p)
    for (s, _), adj in zip(result["signal_holm_family_order"], expected, strict=True):
        if adj is not None:
            assert result["signal_systems"][s]["uniform"]["p_adj"] == adj
    for family in ("freq_hist", "cold", "decay", "transition", "freq_recent"):
        entry = result["systems"][family]
        assert entry["available"] is True
        assert "holm_reject" in entry["uniform"]

    rejects = pipeline.stream_rejects(result)
    gate = controls.healthy_gate(1 if rejects else 0)
    assert gate["ok"] is True

    assert not os.path.exists(engine._target_path(workdir, "pos1"))
    assert not os.path.exists(engine._meta_path(workdir, "pos1"))


def test_stream_rejects_ignores_auxiliary_signal():
    result: dict[str, dict[str, dict[str, object]]] = {"systems": {s: {"available": False}
                                                               for s in pipeline.SYSTEMS}}
    result["systems"]["recent_decay"] = {"available": True,
        "uniform": {"holm_reject": True}, "recent500": {"holm_reject": True}}
    assert pipeline.stream_rejects(result) is False


def test_resume_identity_rejects_changed_inputs_before_writing(tmp_path, monkeypatch):
    h = _daily_history(10, 3, "identity-fixture")
    folds = _explicit_folds(10, n_folds=1, test_block=3)
    outdir = str(tmp_path / "run")
    pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                               reps=50, max_seconds=0, run_controls=False)
    status_path = os.path.join(outdir, "status.json")
    with open(status_path, encoding="utf-8") as f:
        before = f.read()
    variants = [{"configs": _SUBSET_CONFIGS[:-1]}, {"folds": _explicit_folds(10, 1, 4)},
                {"reps": 51}]
    for variant in variants:
        args = {"folds": folds, "configs": _SUBSET_CONFIGS, "reps": 50}
        args.update(variant)
        with pytest.raises(ValueError, match="identity"):
            pipeline.run_interpretable(h, outdir, max_seconds=0, run_controls=False, **args)
        with open(status_path, encoding="utf-8") as f:
            assert f.read() == before
    monkeypatch.setattr(pipeline, "_code_hash", lambda: "different-code")
    with pytest.raises(ValueError, match="identity"):
        pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                   reps=50, max_seconds=0, run_controls=False)
    with open(status_path, encoding="utf-8") as f:
        assert f.read() == before


def test_run_preflights_any_accumulator_before_time_budget_stop(tmp_path):
    h = _daily_history(10, 3, "accumulator-preflight")
    folds = _explicit_folds(10, 1, 3)
    outdir = str(tmp_path / "run")
    pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                               reps=50, max_seconds=0, run_controls=False)
    store = tmp_path / "run" / "store"
    store.mkdir()
    (store / "_any_accumulator.0.int16.dat").write_bytes(b"bad")
    with pytest.raises(ValueError, match="accumulator checkpoint"):
        pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                   reps=50, max_seconds=0, run_controls=False)


def test_resume_preflights_later_checkpoint_before_first_step(tmp_path):
    h = _daily_history(10, 3, "late-checkpoint")
    folds = _explicit_folds(10, 1, 3)
    outdir = str(tmp_path / "run")
    pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                               reps=50, max_seconds=0, run_controls=False)
    status_path = os.path.join(outdir, "status.json")
    with open(status_path, encoding="utf-8") as f:
        before = f.read()
    pipeline._mark_step_done(outdir, "export", h.sha256, {"test": True}, {"wrong": "identity"})
    with pytest.raises(ValueError, match="identity"):
        pipeline.run_interpretable(h, outdir, folds=folds, configs=_SUBSET_CONFIGS,
                                   reps=50, max_seconds=0, run_controls=False)
    with open(status_path, encoding="utf-8") as f:
        assert f.read() == before


def test_inventory_releases_derived_cache_between_candidates(monkeypatch):
    h = _daily_history(3, 4, "inventory-memory")
    cid = "transition:lam=100"
    original = pipeline.models.score_config
    snapshots = []

    def capture(history, config, pos, cache=None):
        assert cache is not None
        snapshots.append(len(cache._cond_cache))
        return original(history, config, pos, cache=cache)

    monkeypatch.setattr(pipeline.models, "score_config", capture)
    pipeline._candidate_inventory(h, [cid, cid])
    assert snapshots == [0, 0]


def test_default_time_budget_and_out_of_scope_override(tmp_path, monkeypatch):
    h = _daily_history(3, 2, "budget-default")
    folds = _explicit_folds(3, 1, 1)
    monkeypatch.setattr(pipeline, "_MAIN_STEPS", ("validation",))
    ticks = iter((0.0, 7201.0))
    monkeypatch.setattr(pipeline.time, "monotonic", lambda: next(ticks, 7201.0))
    result = pipeline.run_interpretable(h, str(tmp_path / "default"), folds=folds,
                                        configs=_SUBSET_CONFIGS, run_controls=False)
    assert result["next_step"] == "validation"
    with pytest.raises(ValueError, match="7200"):
        pipeline.run_interpretable(h, str(tmp_path / "override"), folds=folds,
                                   configs=_SUBSET_CONFIGS, max_seconds=7201,
                                   run_controls=False)
    assert not (tmp_path / "override").exists()


# --- 7. source_restart never uses rows before the switch -----------------------------

def test_source_restart_uses_exact_tie_key(monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 0)
    h = _daily_history(5, 8, "restart-tie", second_host="loteka.com.do",
                       second_host_from_day=2)
    folds = _explicit_folds(5, 1, 2)
    cid = next(cid for cid, family, _ in protocol.all_configs(False) if family == "mix")
    picks = {folds[0].index: {"select_interpretable": cid}}
    switch_row = int(np.argmax(h.source == 1))
    sub = make_history([(h.dates[h.day[i]], f"{h.hour[i]:02d}:{h.slot[i] % 60:02d}",
                         h.nums[i].tolist(), h.sources[h.source[i]])
                        for i in range(switch_row, h.n)], sources=h.sources)
    key = pipeline.models.ranking_key_config(sub, cid, 0)
    rows = np.nonzero((h.day[switch_row:] >= folds[0].test_days[0])
                      & (h.day[switch_row:] < folds[0].test_days[1])
                      & walkforward.primary_mask(sub))[0]
    expected = float((pipeline.ranking.winner_rank(key[rows], sub.nums[rows, 0])
                      < protocol.PRIMARY_K).mean())
    observed = []
    original_rank = pipeline.ranking.winner_rank

    def capture_rank(scores, winners):
        observed.append(scores.copy())
        return original_rank(scores, winners)

    monkeypatch.setattr(pipeline.ranking, "winner_rank", capture_rank)
    pipeline.source_restart(h, folds, picks)
    assert len(observed) == 1
    assert np.array_equal(observed[0], key[rows])
    assert float((original_rank(observed[0], sub.nums[rows, 0]) < protocol.PRIMARY_K).mean()) == expected


def test_source_restart_ignores_rows_before_the_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 0)
    h = _daily_history(30, 8, "test-pipeline-restart", host="premios.do",
                       second_host="loteka.com.do", second_host_from_day=15)
    folds = _explicit_folds(len(h.dates), n_folds=1, test_block=6)
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")
    hits = pipeline.target_hits(store["ranks_updated"], protocol.PRIMARY_K)
    config_ids, families_of = pipeline.candidate_entries(store["config_ids"].tolist())
    candidate_hits = np.array([np.asarray(hits)[list(store["config_ids"]).index(cid)] for cid in config_ids])
    primary_rows = walkforward.primary_mask(h)
    picks, _scores, _test_rows = pipeline.per_fold_choice(h, config_ids, families_of, candidate_hits,
                                                           folds, primary_rows)

    result = pipeline.source_restart(h, folds, picks)

    switch_row = int(np.argmax(h.source == 1))
    altered_nums = h.nums.copy()
    generator = protocol.rng("test-pipeline-restart-alter-pre-switch")
    altered_nums[:switch_row] = generator.integers(0, 100, size=(switch_row, 5))
    h_altered = h.with_nums(altered_nums)
    result_altered = pipeline.source_restart(h_altered, folds, picks)

    assert result == result_altered


def test_supervised_reduced_not_in_main_steps_and_not_triggered_by_run_interpretable():
    """CR-7 opt-in step: must never run inside the currently-running CR-6 process."""
    assert "supervised_reduced" not in pipeline._MAIN_STEPS


def test_run_supervised_reduced_writes_labeled_output_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 0)
    h = _daily_history(40, 8, "test-pipeline-supervised-reduced")
    folds = _explicit_folds(len(h.dates), n_folds=2, test_block=4)
    outdir = str(tmp_path / "run")

    result_1 = pipeline.run_supervised_reduced(h, outdir, folds=folds)

    assert "muestra reducida exploratoria" in result_1["label"]
    assert "ventana fija de 30000" in result_1["label"]
    assert "refit una vez por fold externo" in result_1["label"]
    assert "no cada 7" in result_1["label"]
    with open(os.path.join(outdir, "supervised_reduced.json"), encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["result"] == result_1

    def _boom(*args, **kwargs):
        raise AssertionError("should not recompute a completed supervised_reduced run")

    monkeypatch.setattr(pipeline.supervised, "reduced_run", _boom)
    result_2 = pipeline.run_supervised_reduced(h, outdir, folds=folds)
    assert result_2 == result_1


def test_run_supervised_reduced_raises_on_identity_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 0)
    h = _daily_history(40, 8, "test-pipeline-supervised-reduced-mismatch")
    folds = _explicit_folds(len(h.dates), n_folds=2, test_block=4)
    outdir = str(tmp_path / "run")

    pipeline.run_supervised_reduced(h, outdir, folds=folds)

    monkeypatch.setattr(protocol, "ALPHA", 0.05)
    with pytest.raises(ValueError):
        pipeline.run_supervised_reduced(h, outdir, folds=folds)


def _freeze_reduced_fit_clock(monkeypatch):
    """Deterministic per-fit elapsed time so two independent runs (interrupted+resumed
    vs. straight-through) assemble bit-for-bit identical results, including timings."""
    counter = {"t": 0.0}

    def _fake_perf_counter():
        counter["t"] += 0.5
        return counter["t"]

    monkeypatch.setattr(supervised.time, "perf_counter", _fake_perf_counter)


def test_run_supervised_reduced_checkpoints_every_fit_and_resumes(tmp_path, monkeypatch):
    """2 families x 2 positions x 2 folds = 8 fits. Interrupt after 3, verify 3 partial
    files exist, then resume and verify only the remaining 5 are computed."""
    monkeypatch.setattr(protocol, "WARMUP", 0)
    h = _daily_history(40, 8, "test-pipeline-supervised-reduced-granular")
    folds = _explicit_folds(len(h.dates), n_folds=2, test_block=4)
    outdir = str(tmp_path / "run")
    positions = (0, 1)

    _freeze_reduced_fit_clock(monkeypatch)
    calls = {"n": 0}
    original = supervised.reduced_fit_one

    def _counting(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] > 3:
            raise RuntimeError("simulated kill mid-run")
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline.supervised, "reduced_fit_one", _counting)

    with pytest.raises(RuntimeError, match="simulated kill mid-run"):
        pipeline.run_supervised_reduced(h, outdir, folds=folds, positions=positions)

    partial_dir = os.path.join(outdir, "supervised_reduced_partial")
    partial_files = sorted(os.listdir(partial_dir))
    assert len(partial_files) == 3
    assert not os.path.exists(os.path.join(outdir, "supervised_reduced.json"))

    # Resume: already-completed fits must not be recomputed -- a fresh counter with no
    # raise threshold must see exactly the 5 remaining fits, not all 8.
    resume_calls = {"n": 0}

    def _counting_resume(*args, **kwargs):
        resume_calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline.supervised, "reduced_fit_one", _counting_resume)
    result_resumed = pipeline.run_supervised_reduced(h, outdir, folds=folds, positions=positions)

    assert resume_calls["n"] == 5
    assert len(os.listdir(partial_dir)) == 8
    with open(os.path.join(outdir, "supervised_reduced.json"), encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["result"] == result_resumed


def test_run_supervised_reduced_resumed_run_matches_straight_through_run(tmp_path, monkeypatch):
    """An interrupted-then-resumed run must assemble the exact same final result,
    including timings, as a straight-through run over the same inputs."""
    monkeypatch.setattr(protocol, "WARMUP", 0)
    h = _daily_history(40, 8, "test-pipeline-supervised-reduced-bitforbit")
    folds = _explicit_folds(len(h.dates), n_folds=2, test_block=4)
    positions = (0, 1)

    _freeze_reduced_fit_clock(monkeypatch)
    straight_outdir = str(tmp_path / "straight")
    result_straight = pipeline.run_supervised_reduced(h, straight_outdir, folds=folds, positions=positions)

    _freeze_reduced_fit_clock(monkeypatch)
    interrupted_outdir = str(tmp_path / "interrupted")
    calls = {"n": 0}
    original = supervised.reduced_fit_one

    def _boom_after_two(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] > 2:
            raise RuntimeError("simulated kill mid-run")
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline.supervised, "reduced_fit_one", _boom_after_two)
    with pytest.raises(RuntimeError, match="simulated kill mid-run"):
        pipeline.run_supervised_reduced(h, interrupted_outdir, folds=folds, positions=positions)

    monkeypatch.setattr(pipeline.supervised, "reduced_fit_one", original)
    result_resumed = pipeline.run_supervised_reduced(h, interrupted_outdir, folds=folds, positions=positions)

    assert result_resumed == result_straight


def test_run_supervised_reduced_partial_fit_identity_mismatch_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 0)
    h = _daily_history(40, 8, "test-pipeline-supervised-reduced-partial-mismatch")
    folds = _explicit_folds(len(h.dates), n_folds=2, test_block=4)
    outdir = str(tmp_path / "run")
    positions = (0,)

    calls = {"n": 0}
    original = supervised.reduced_fit_one

    def _boom_after_one(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("simulated kill mid-run")
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline.supervised, "reduced_fit_one", _boom_after_one)
    with pytest.raises(RuntimeError, match="simulated kill mid-run"):
        pipeline.run_supervised_reduced(h, outdir, folds=folds, positions=positions)

    partial_dir = os.path.join(outdir, "supervised_reduced_partial")
    partial_file = os.path.join(partial_dir, os.listdir(partial_dir)[0])
    with open(partial_file, encoding="utf-8") as f:
        record = json.load(f)
    record["identity"]["protocol_hash"] = "tampered"
    with open(partial_file, "w", encoding="utf-8") as f:
        json.dump(record, f)

    monkeypatch.setattr(pipeline.supervised, "reduced_fit_one", original)
    with pytest.raises(ValueError):
        pipeline.run_supervised_reduced(h, outdir, folds=folds, positions=positions)
