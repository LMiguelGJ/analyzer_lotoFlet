"""Feature-vector contract for the supervised stage (protocol section 3): causal, fixed width,
plus the CR-7 reduced exploratory fit/predict and aggregation over the pre-declared grid."""

from datetime import date, timedelta

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from chance_rank import protocol, supervised, walkforward
from chance_rank.data import make_history
from chance_rank.protocol import rng
from chance_rank.ranking import winner_rank


def _synthetic_history(n_rows, seed_label="test-supervised-synthetic"):
    """Multi-day synthetic history with occasional 10-minute gaps, one source."""
    generator = rng(seed_label)
    nums = generator.integers(0, 100, size=(n_rows, 5))
    entries = []
    day_index = 0
    minute = 5
    rows_in_day = 0
    for i in range(n_rows):
        if rows_in_day >= 40 or (rows_in_day > 0 and generator.random() < 0.05):
            day_index += 1
            minute = 5
            rows_in_day = 0
        elif rows_in_day > 0:
            minute += 15 if generator.random() < 0.05 else 5
        hour, mm = divmod(minute, 60)
        hour += 5
        iso_date = (date(2025, 3, 5) + timedelta(days=day_index)).isoformat()
        entries.append((iso_date, f"{hour:02d}:{mm:02d}", nums[i].tolist(), "premios.do"))
        rows_in_day += 1
    return make_history(entries)


def test_feature_matrix_fixed_width_across_sizes_and_positions():
    h_small = _synthetic_history(30)
    h_big = _synthetic_history(90, seed_label="test-supervised-big")

    m_small = supervised.build_feature_matrix(h_small, pos=2)
    m_big = supervised.build_feature_matrix(h_big, pos=2)
    m_other_pos = supervised.build_feature_matrix(h_small, pos=4)

    assert m_small.shape == (h_small.n, supervised.N_FEATURES)
    assert m_big.shape == (h_big.n, supervised.N_FEATURES)
    assert m_other_pos.shape[1] == m_small.shape[1]


def test_feature_matrix_causal_under_future_change():
    h = _synthetic_history(60)
    matrix = supervised.build_feature_matrix(h, pos=0)

    changed_nums = h.nums.copy()
    changed_nums[41:] = (changed_nums[41:] + 7) % 100
    h_changed = h.with_nums(changed_nums)
    matrix_changed = supervised.build_feature_matrix(h_changed, pos=0)

    np.testing.assert_array_equal(matrix[:41], matrix_changed[:41])
    assert not np.array_equal(matrix[41:], matrix_changed[41:])


def test_feature_matrix_no_nan_or_inf():
    h = _synthetic_history(50)
    matrix = supervised.build_feature_matrix(h, pos=4)
    assert np.isfinite(matrix).all()


def test_feature_matrix_row_zero_is_fully_censored():
    h = _synthetic_history(20)
    matrix = supervised.build_feature_matrix(h, pos=1)
    row0 = matrix[0]
    assert np.count_nonzero(row0) < supervised.N_FEATURES


def _fold(test_start, test_end):
    return walkforward.Fold(index=0, test_days=(test_start, test_end),
                             inner=((0, 0), (0, 0), (0, 0)))


def test_fit_predict_fold_never_fits_on_test_day_rows(monkeypatch):
    monkeypatch.setattr("chance_rank.protocol.WARMUP", 0)
    h = _synthetic_history(300)
    n_days = len(h.dates)
    fold = _fold(n_days - 3, n_days)
    window = 200

    captured = {}
    original_fit = LogisticRegression.fit

    def _spy_fit(self, X, y, *args, **kwargs):
        captured["X"], captured["y"] = X, y
        return original_fit(self, X, y, *args, **kwargs)

    monkeypatch.setattr(LogisticRegression, "fit", _spy_fit)

    supervised.fit_predict_fold(h, pos=0, fold=fold, window=window,
                                 config=supervised.REDUCED_LOGISTIC_CONFIG, family="logistic")

    train_mask = walkforward.primary_mask(h) & (h.day < fold.test_days[0])
    train_idx = np.nonzero(train_mask)[0][-window:]
    expected_matrix = supervised.build_feature_matrix(h, pos=0)[train_idx]

    # The exact rows sklearn fit on: strictly before the fold's test window, never a
    # test-day row, regardless of what those test rows' targets/features hold.
    assert captured["X"].shape[0] == train_idx.size
    np.testing.assert_array_equal(captured["X"], expected_matrix)
    np.testing.assert_array_equal(captured["y"], h.nums[train_idx, 0])
    assert train_idx.max() < np.nonzero(walkforward.rows_in_days(h, *fold.test_days))[0].min()


def test_fit_predict_fold_class_vector_alignment_with_missing_classes(monkeypatch):
    monkeypatch.setattr("chance_rank.protocol.WARMUP", 0)
    h = _synthetic_history(200)
    n_days = len(h.dates)
    fold = _fold(n_days - 2, n_days)
    train_mask = walkforward.primary_mask(h) & (h.day < fold.test_days[0])

    # Collapse the training window's target position to only 3 distinct digits so
    # sklearn's classes_ never spans the full 0..99 range.
    restricted_nums = h.nums.copy()
    restricted_nums[train_mask, 0] = np.array([3, 7, 42])[np.arange(train_mask.sum()) % 3]
    h_restricted = h.with_nums(restricted_nums)

    row_idx, S = supervised.fit_predict_fold(h_restricted, pos=0, fold=fold, window=1000,
                                              config=supervised.REDUCED_TREE_CONFIG,
                                              family="tree")

    assert S.shape == (row_idx.size, 100)
    present = {3, 7, 42}
    absent_cols = [v for v in range(100) if v not in present]
    assert np.all(S[:, absent_cols] == 0.0)
    np.testing.assert_allclose(S.sum(axis=1), 1.0)


def test_reduced_run_labels_and_shape(monkeypatch):
    monkeypatch.setattr("chance_rank.protocol.WARMUP", 0)
    h = _synthetic_history(250)
    n_days = len(h.dates)
    folds = [_fold(n_days - 6, n_days - 3), _fold(n_days - 3, n_days)]

    result = supervised.reduced_run(h, folds, positions=(0, 1))

    assert result["label"] == "muestra reducida exploratoria"
    assert set(result["families"]) == {"logistic", "tree"}
    for family in ("logistic", "tree"):
        positions = result["families"][family]["positions"]
        assert set(positions) == {"pos1", "pos2"}
        for pos_key in positions:
            entry = positions[pos_key]
            assert entry["targets"] >= 0
            assert len(entry["fold_wall_time_seconds"]) == len(folds)
            if entry["targets"] > 0:
                assert 0.0 <= entry["hit_rate_top25"] <= 1.0
        assert result["families"][family]["wall_time_seconds"] >= 0.0
    assert set(result["primary_pos1"]) == {"logistic", "tree"}
    assert result["total_wall_time_seconds"] >= 0.0


def test_reduced_run_uses_pre_declared_grid_exactly():
    assert supervised.REDUCED_LOGISTIC_CONFIG == {"C": 0.1, "solver": "lbfgs",
                                                   "max_iter": 500, "tol": 1e-4}
    assert supervised.REDUCED_TREE_CONFIG == {"max_depth": 5, "min_samples_leaf": 200}
    assert supervised.REDUCED_WINDOW == 30000


def test_reduced_fit_one_matches_fit_predict_fold_aggregation(monkeypatch):
    """``reduced_fit_one`` is the single (family, pos, fold) building block granular
    checkpointing callers use; its hits/targets must match manually aggregating
    ``fit_predict_fold`` + ``winner_rank`` for the same inputs."""
    monkeypatch.setattr("chance_rank.protocol.WARMUP", 0)
    h = _synthetic_history(250)
    n_days = len(h.dates)
    fold = _fold(n_days - 3, n_days)
    matrix = supervised.build_feature_matrix(h, 0)

    result = supervised.reduced_fit_one(h, 0, fold, "tree", matrix=matrix)

    row_idx, S = supervised.fit_predict_fold(h, 0, fold, supervised.REDUCED_WINDOW,
                                              supervised.REDUCED_TREE_CONFIG, "tree", matrix=matrix)
    expected_hits, expected_targets = 0, 0
    if row_idx.size:
        Y = h.nums[row_idx, 0]
        ranks = winner_rank(S, Y)
        expected_hits = int((ranks < protocol.PRIMARY_K).sum())
        expected_targets = int(row_idx.size)

    assert result["hits"] == expected_hits
    assert result["targets"] == expected_targets
    assert result["elapsed_seconds"] >= 0.0
    assert set(result) == {"hits", "targets", "elapsed_seconds"}


def test_reduced_fit_one_unknown_family_raises():
    h = _synthetic_history(60)
    fold = _fold(len(h.dates) - 2, len(h.dates))
    with pytest.raises(ValueError):
        supervised.reduced_fit_one(h, 0, fold, "forest")


def test_reduced_run_matches_manual_reduced_fit_one_aggregation(monkeypatch):
    """``reduced_run`` must stay a thin aggregator over ``reduced_fit_one`` so pipeline-level
    per-fit checkpointing and the standalone aggregate produce identical numbers."""
    monkeypatch.setattr("chance_rank.protocol.WARMUP", 0)
    h = _synthetic_history(250)
    n_days = len(h.dates)
    folds = [_fold(n_days - 6, n_days - 3), _fold(n_days - 3, n_days)]

    result = supervised.reduced_run(h, folds, positions=(0, 1))

    for pos in (0, 1):
        matrix = supervised.build_feature_matrix(h, pos)
        for family in ("logistic", "tree"):
            hits, targets = 0, 0
            for fold in folds:
                fit = supervised.reduced_fit_one(h, pos, fold, family, matrix=matrix)
                hits += fit["hits"]
                targets += fit["targets"]
            entry = result["families"][family]["positions"][f"pos{pos + 1}"]
            assert entry["hits"] == hits
            assert entry["targets"] == targets
