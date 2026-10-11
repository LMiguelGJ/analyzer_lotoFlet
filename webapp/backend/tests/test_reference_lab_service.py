from dataclasses import dataclass, field
from types import SimpleNamespace

import numpy as np
import pytest

from laboratorio.domain.reference_labs import REFERENCE_LABS
from laboratorio.engine.reference_lab_service import ReferenceLabServiceError, execute_reference_lab
from laboratorio.settings import HISTORY_SHA256

SHA = HISTORY_SHA256


@dataclass(frozen=True)
class History:
    labels: tuple[str, ...] = ("2025-09-02 05:10",)
    nums: np.ndarray = field(default_factory=lambda: np.asarray([[1, 2, 3, 4, 5]], dtype=np.uint8))
    sha256: str = SHA


class Rankings:
    row_ids = np.asarray([0], dtype=np.int64)

    def family(self, system):
        return np.tile(np.arange(100, dtype=np.uint8), (1, 1))


@pytest.fixture
def lab_data(tmp_path):
    from laboratorio.settings import Settings

    settings = Settings(tmp_path, tmp_path / "history", tmp_path / "rankings", tmp_path)
    votes = np.asarray([0], dtype=np.int8)
    return SimpleNamespace(
        history=History(),
        rankings=Rankings(),
        settings=settings,
        parity_votes=lambda: votes,
    )


def test_execute_uses_loaded_frozen_data_and_returns_immutable_provenance(monkeypatch, lab_data):
    from laboratorio.engine import reference_lab_service
    from laboratorio.engine.reference_labs import ReferenceResult, ReferenceTotals

    expected = ReferenceResult(
        "transicion_1_audaz",
        (),
        ReferenceTotals(0, 0, 0, 0, 0, 0, 0, 0, 0, None),
        0,
        0,
        None,
        None,
        "b" * 64,
    )
    seen = {}

    def replay(lab, history, rankings, *, parity_votes=None):
        seen.update(lab=lab, history=history, rankings=rankings, parity_votes=parity_votes)
        return expected

    monkeypatch.setattr(reference_lab_service, "run_reference_lab", replay)
    execution = execute_reference_lab("transicion_1_audaz", SHA, lab_data)

    assert execution.result is expected
    assert execution.provenance.history_sha256 == SHA
    assert execution.provenance.history_origin == "frozen"
    assert execution.provenance.rankings_sha256 == (
        "b405041fff1f45fe24fd9ab09fed2c6709e979576811c703e7d27e57f3ded94d"
    )
    assert execution.contract_version == 1
    assert seen == {
        "lab": REFERENCE_LABS[0],
        "history": lab_data.history,
        "rankings": lab_data.rankings,
        "parity_votes": None,
    }
    with pytest.raises((AttributeError, TypeError)):
        execution.provenance.__setattr__("history_origin", "import")


@pytest.mark.parametrize("fingerprint", [None, 12, "A" * 64, "g" * 64, "a" * 63, "a" * 64 + "\n"])
def test_rejects_noncanonical_or_missing_fingerprint_before_replay(
    monkeypatch, lab_data, fingerprint
):
    from laboratorio.engine import reference_lab_service

    monkeypatch.setattr(
        reference_lab_service,
        "run_reference_lab",
        lambda *a, **k: pytest.fail("replay called"),
    )
    with pytest.raises(ReferenceLabServiceError):
        execute_reference_lab("transicion_1_audaz", fingerprint, lab_data)


def test_rejects_unknown_lab_and_non_frozen_source_before_replay(monkeypatch, lab_data):
    from laboratorio.engine import reference_lab_service

    monkeypatch.setattr(
        reference_lab_service,
        "run_reference_lab",
        lambda *a, **k: pytest.fail("replay called"),
    )
    with pytest.raises(ReferenceLabServiceError, match="unknown"):
        execute_reference_lab("not-a-lab", SHA, lab_data)
    with pytest.raises(ReferenceLabServiceError, match="frozen"):
        execute_reference_lab("transicion_1_audaz", "c" * 64, lab_data)


def test_rejects_corrupted_loaded_reference_source_before_replay(monkeypatch, lab_data):
    from dataclasses import replace

    from laboratorio.engine import reference_lab_service

    monkeypatch.setattr(
        reference_lab_service,
        "run_reference_lab",
        lambda *a, **k: pytest.fail("replay called"),
    )
    lab_data.history = replace(lab_data.history, sha256="c" * 64)
    with pytest.raises(ReferenceLabServiceError, match="pinned frozen source"):
        execute_reference_lab("transicion_1_audaz", "c" * 64, lab_data)


def test_parity_replay_receives_votes_from_loaded_lab_data(monkeypatch, lab_data):
    from laboratorio.engine import reference_lab_service

    seen = {}

    def replay(lab, history, rankings, *, parity_votes=None):
        seen.update(lab=lab, history=history, rankings=rankings, votes=parity_votes)
        return object()

    monkeypatch.setattr(reference_lab_service, "run_reference_lab", replay)
    execution = execute_reference_lab("paridad_50_audaz", SHA, lab_data)
    assert execution.provenance.history_origin == "frozen"
    assert seen["history"] is lab_data.history
    assert seen["rankings"] is lab_data.rankings
    assert seen["votes"] is lab_data.parity_votes()
