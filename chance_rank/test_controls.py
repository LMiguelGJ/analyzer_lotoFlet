"""Healthy/signal/order-null control streams and their acceptance gates."""

from datetime import date, timedelta

import numpy as np
import pytest

from chance_rank import controls, protocol
from chance_rank.data import make_history
from rng_audit import generators
from rng_audit.lottery_tests import Draws


def _manual_base(h, seed):
    months = np.array([int(h.dates[d][5:7]) for d in h.day.tolist()], dtype=np.int64)
    template = Draws(nums=h.nums, day=h.day, slot=h.slot, weekday=h.weekday, month=months)
    return generators.sha256_drbg(template, seed=seed)


def _daily_history(n_days, rows_per_day=4, host="premios.do"):
    entries = []
    for d in range(n_days):
        iso = (date(2024, 1, 1) + timedelta(days=d)).isoformat()
        for r in range(rows_per_day):
            hour, minute = divmod(5 + r * 5, 60)
            entries.append((iso, f"{hour:02d}:{minute:02d}", [0, 0, 0, 0, 0], host))
    return make_history(entries)


# --- healthy_history: reproduces sha256_drbg on a Draws template built from h --------


def test_healthy_history_matches_sha256_drbg_and_differs_by_seed():
    h = _daily_history(n_days=3, rows_per_day=4)
    seed = f"{protocol.PROTOCOL_ID}/healthy/001"
    expected = _manual_base(h, seed)

    healthy_1 = controls.healthy_history(h, 1)
    healthy_2 = controls.healthy_history(h, 2)

    assert healthy_1.nums.tolist() == expected.nums.reshape(-1, 5).tolist()
    assert healthy_1.nums.tolist() != healthy_2.nums.tolist()
    # calendar untouched
    assert healthy_1.day.tolist() == h.day.tolist()
    assert healthy_1.dates == h.dates


# --- signal_history: reproducibility and only-column-0 modification -----------------


def test_signal_history_is_reproducible():
    h = _daily_history(n_days=2, rows_per_day=6)
    history_a, info_a = controls.signal_history(h, "repeat", 0.5, 1)
    history_b, info_b = controls.signal_history(h, "repeat", 0.5, 1)
    assert history_a.nums.tolist() == history_b.nums.tolist()
    assert info_a == info_b


def test_signal_history_only_modifies_column_0():
    h = _daily_history(n_days=2, rows_per_day=6)
    seed = f"{protocol.PROTOCOL_ID}/signal/hour/0.5/001"
    base = _manual_base(h, seed)
    history, _info = controls.signal_history(h, "hour", 0.5, 1)
    assert history.nums[:, 1:].tolist() == base.nums.reshape(-1, 5)[:, 1:].tolist()


# --- repeat: q=1.0 chains every eligible row's first to its segment start -----------


def test_signal_repeat_q1_chains_within_segment():
    h = _daily_history(n_days=1, rows_per_day=4)  # 1 segment, rows 1-3 eligible
    history, info = controls.signal_history(h, "repeat", 1.0, 1)
    first = history.nums[:, 0]
    assert first[1] == first[0]
    assert first[2] == first[0]
    assert first[3] == first[0]
    assert info["opportunities"] == 3
    assert info["applied"] == 3
    assert info["rate"] == pytest.approx(1.0)


# --- carry: q=1.0 always copies the previous row's second column -------------------


def test_signal_carry_q1_copies_second_column_of_previous_row():
    h = _daily_history(n_days=1, rows_per_day=4)
    history, info = controls.signal_history(h, "carry", 1.0, 1)
    for t in range(1, h.n):
        assert history.nums[t, 0] == history.nums[t - 1, 1]
    assert info["opportunities"] == 3
    assert info["applied"] == 3


# --- hour: every row, q=1.0, value in [10*(hour%10), 10*(hour%10)+10) ----------------


def test_signal_hour_q1_within_decade_of_hour_mod_10():
    h = _daily_history(n_days=1, rows_per_day=6)
    history, info = controls.signal_history(h, "hour", 1.0, 1)
    first = history.nums[:, 0]
    for t in range(h.n):
        low = 10 * (int(h.hour[t]) % 10)
        assert low <= first[t] < low + 10
    assert info["opportunities"] == h.n
    assert info["applied"] == h.n


# --- shift: every row, q=1.0, day >= SIGNAL_SHIFT_DAY -> 0-9, else 90-99 -------------


def test_signal_shift_q1_respects_threshold_day(monkeypatch):
    monkeypatch.setattr(protocol, "SIGNAL_SHIFT_DAY", 3)
    h = _daily_history(n_days=5, rows_per_day=1)
    history, info = controls.signal_history(h, "shift", 1.0, 1)
    first = history.nums[:, 0]
    for t in range(h.n):
        if h.day[t] >= 3:
            assert 0 <= first[t] < 10
        else:
            assert 90 <= first[t] < 100
    assert info["opportunities"] == h.n


# --- streak: opportunity only after 3 consecutive same-parity firsts in one segment --


def test_signal_streak_q1_flips_parity_after_three_equal_parity_firsts(monkeypatch):
    h = _daily_history(n_days=1, rows_per_day=6)
    fixed_nums = np.zeros((h.n, 5), dtype=np.int64)
    fixed_nums[:, 0] = [10, 12, 14, 16, 21, 8]  # even, even, even, even, odd, even

    class _FakeBase:
        nums = fixed_nums

    monkeypatch.setattr(controls.generators, "sha256_drbg", lambda template, seed: _FakeBase())

    history, info = controls.signal_history(h, "streak", 1.0, 1)
    first = history.nums[:, 0]

    # t=3: firsts at t-1,t-2,t-3 = 14,12,10 all even -> opportunity, flipped to odd
    assert info["opportunities"] == 1
    assert info["applied"] == 1
    assert first[3] % 2 == 1
    # untouched rows keep the fixed base value
    assert first[0] == 10
    assert first[1] == 12
    assert first[2] == 14
    assert first[4] == 21
    assert first[5] == 8


# --- effective intervention rate close to q on a larger synthetic calendar -----------


def test_signal_effective_rate_close_to_q():
    h = _daily_history(n_days=100, rows_per_day=20)
    _history, info = controls.signal_history(h, "repeat", 0.10, 1)
    assert info["opportunities"] > 1000
    assert abs(info["rate"] - 0.10) < 0.03


# --- order_null_history: preserves each row's 5-tuple multiset within (day, source) --


def test_order_null_preserves_multiset_within_day_source_and_calendar():
    h = _daily_history(n_days=3, rows_per_day=6)
    generator_for_variety = protocol.rng("test-order-null-variety")
    varied_nums = generator_for_variety.integers(0, 100, size=(h.n, 5))
    h = h.with_nums(varied_nums)

    permuted = controls.order_null_history(h, 1)

    assert permuted.day.tolist() == h.day.tolist()
    assert permuted.source.tolist() == h.source.tolist()
    assert permuted.dates == h.dates

    for day_idx in range(len(h.dates)):
        for source_idx in range(len(h.sources)):
            group_mask = (h.day == day_idx) & (h.source == source_idx)
            if not group_mask.any():
                continue
            before = sorted(map(tuple, h.nums[group_mask].tolist()))
            after = sorted(map(tuple, permuted.nums[group_mask].tolist()))
            assert before == after


def test_order_null_is_deterministic_per_seed():
    h = _daily_history(n_days=2, rows_per_day=6)
    a = controls.order_null_history(h, 1)
    b = controls.order_null_history(h, 1)
    assert a.nums.tolist() == b.nums.tolist()


# --- RELEVANT_SYSTEM mapping (D11) ----------------------------------------------------


def test_relevant_system_mapping():
    assert controls.RELEVANT_SYSTEM == {
        "repeat": ["transition"],
        "carry": ["carry"],
        "hour": ["time"],
        "shift": ["decay", "freq_recent"],
        "streak": ["category"],
    }


# --- gates -----------------------------------------------------------------------------


def test_healthy_gate():
    assert controls.healthy_gate(0)["ok"] is True
    assert controls.healthy_gate(protocol.HEALTHY_MAX_REJECTING)["ok"] is True
    assert controls.healthy_gate(protocol.HEALTHY_MAX_REJECTING + 1)["ok"] is False


def test_signal_gate_requires_majority_of_three_streams():
    decisions = {"repeat": [True, True, False], "carry": [True, False, False]}
    result = controls.signal_gate(decisions)
    assert result["repeat"]["ok"] is True
    assert result["repeat"]["n_rejecting"] == 2
    assert result["carry"]["ok"] is False
    assert result["carry"]["n_rejecting"] == 1
