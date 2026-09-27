"""Reference examples from NIST SP 800-22 rev1a, section 2 (worked examples)."""

import numpy as np
import pytest

from rng_audit import nist_sp800_22 as nist


def bits(text):
    return np.array([int(c) for c in text], dtype=np.uint8)


def test_frequency():
    assert nist.frequency(bits("1011010101"))[0] == pytest.approx(0.527089, abs=1e-6)


def test_block_frequency():
    p = nist.block_frequency(bits("0110011010"), m=3)[0]
    assert p == pytest.approx(0.801252, abs=1e-6)


def test_runs():
    assert nist.runs(bits("1001101011"))[0] == pytest.approx(0.147232, abs=1e-6)


def test_cumulative_sums_forward():
    p_forward = nist.cumulative_sums(bits("1011010111"))[0]
    assert p_forward == pytest.approx(0.4116588, abs=1e-6)


def test_approximate_entropy():
    p = nist.approximate_entropy(bits("0100110101"), m=3)[0]
    assert p == pytest.approx(0.261961, abs=1e-6)


def test_serial():
    p1, p2 = nist.serial(bits("0011011101"), m=3)
    assert p1 == pytest.approx(0.808792, abs=1e-6)
    assert p2 == pytest.approx(0.670320, abs=1e-6)


def test_aperiodic_templates_m9_count():
    assert len(nist.aperiodic_templates(9)) == 148


def test_berlekamp_massey_known_sequence():
    # NIST example 2.10.8: 1101011110001 has linear complexity 4.
    assert nist.berlekamp_massey(bits("1101011110001")) == 4


def test_matrix_rank_gf2():
    assert nist.gf2_rank([0b100, 0b010, 0b110], 3) == 2
    assert nist.gf2_rank([0b100, 0b010, 0b001], 3) == 3


def test_suite_on_fair_bits_mostly_passes():
    rng = np.random.default_rng(12345)
    sample = rng.integers(0, 2, 1_000_000, dtype=np.uint8)
    results = nist.run_suite(sample)
    for name, pvals in results.items():
        if not pvals:
            continue
        passed = np.mean(np.asarray(pvals) >= 0.01)
        assert passed >= 0.9, (name, pvals[:5])


def test_suite_detects_biased_bits():
    rng = np.random.default_rng(7)
    sample = (rng.random(100_000) < 0.52).astype(np.uint8)
    assert nist.frequency(sample)[0] < 0.01
