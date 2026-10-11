"""Independent regression coverage for the frozen-history causal parity voters."""

import hashlib
import importlib
import sys
from pathlib import Path

import numpy as np

from laboratorio.domain.selection import parity_votes as production_parity_votes
from laboratorio.engine.adapter import load_history
from laboratorio.settings import HISTORY_SHA256

ROOT = Path(__file__).resolve().parents[3]
_EXPECTED_VOTES_SHA256 = "5100eb5d81f2fe8c894741261a66c9674ac63d2dbb397db476458ef8164040ec"


def _voters():
    sys.path[:0] = [str(ROOT), str(ROOT / "repo_ref")]
    reference_module = importlib.import_module("quiniela_sim")
    assert reference_module.__file__ is not None
    assert Path(reference_module.__file__).resolve() == (ROOT / "repo_ref" / "quiniela_sim.py")
    reference_parity_votes = reference_module.consensus_parity
    assert production_parity_votes is not reference_parity_votes
    return production_parity_votes, reference_parity_votes


def _assert_binary_vector(votes, expected_length):
    assert votes.shape == (expected_length,)
    assert np.all((votes == 0) | (votes == 1))
    assert votes.dtype == np.int8


def test_distinct_parity_voters_match_on_validated_frozen_history():
    production, reference = _voters()
    history = load_history(ROOT / "chance_express_history.json", HISTORY_SHA256)
    assert history.sha256 == HISTORY_SHA256
    first_numbers = history.nums[:, 0]
    assert len(first_numbers) == 105426

    production_votes = production(first_numbers)
    reference_votes = reference(first_numbers)
    _assert_binary_vector(production_votes, len(first_numbers))
    _assert_binary_vector(reference_votes, len(first_numbers))
    np.testing.assert_array_equal(production_votes, reference_votes)

    production_bytes = np.asarray(production_votes, dtype=np.int8).tobytes()
    reference_bytes = np.asarray(reference_votes, dtype=np.int8).tobytes()
    assert hashlib.sha256(production_bytes).hexdigest() == _EXPECTED_VOTES_SHA256
    assert hashlib.sha256(reference_bytes).hexdigest() == _EXPECTED_VOTES_SHA256


def test_parity_voter_prefixes_ignore_the_current_draw_and_later_suffix():
    voters = _voters()
    sequence = np.asarray([(index * 37 + (index // 3) * 11) % 100 for index in range(72)])
    cutoff = 29
    changed_suffix = sequence.copy()
    changed_suffix[cutoff:] = (changed_suffix[cutoff:] + 41) % 100

    for voter in voters:
        full_votes = voter(sequence)
        prefix_votes = voter(sequence[:cutoff])
        changed_votes = voter(changed_suffix)
        _assert_binary_vector(full_votes, len(sequence))
        np.testing.assert_array_equal(prefix_votes, full_votes[:cutoff])
        np.testing.assert_array_equal(changed_votes[: cutoff + 1], full_votes[: cutoff + 1])
