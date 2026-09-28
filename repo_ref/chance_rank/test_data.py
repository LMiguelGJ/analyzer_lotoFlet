"""Validated loading and canonical chronology of Chance Express draws."""

import hashlib
import json
from pathlib import Path

import pytest

from chance_rank.data import (
    DataError,
    fmt,
    load_history,
    make_history,
    row_at,
    validation_report,
)
from chance_rank.protocol import EXPECTED_SHA256

REPO_HISTORY = Path(__file__).resolve().parent.parent / "chance_express_history.json"


def _write(tmp_path, sorteos_por_fecha):
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"sorteos_por_fecha": sorteos_por_fecha}, ensure_ascii=False),
                     encoding="utf-8")
    return path


def _rec(hora, nums, host="premios.do"):
    return {"hora": hora, "numeros": [fmt(n) for n in nums],
            "source_url": f"https://{host}/x"}


def test_unsorted_dates_and_times_are_sorted(tmp_path):
    path = _write(tmp_path, {
        "2025-03-06": [_rec("05:10", [1, 1, 1, 1, 1]), _rec("05:05", [0, 0, 0, 0, 0])],
        "2025-03-05": [_rec("05:05", [9, 9, 9, 9, 9])],
    })
    h = load_history(path, expected_sha=None)
    assert h.dates == ("2025-03-05", "2025-03-06")
    assert h.label(0) == "2025-03-05 05:05"
    assert h.label(1) == "2025-03-06 05:05"
    assert h.label(2) == "2025-03-06 05:10"


def test_five_minute_chain_eligibility_and_new_segment_after_gap(tmp_path):
    path = _write(tmp_path, {
        "2025-03-05": [
            _rec("05:05", [0, 0, 0, 0, 0]),
            _rec("05:10", [1, 1, 1, 1, 1]),
            _rec("05:20", [2, 2, 2, 2, 2]),  # 10-minute gap after the previous row
            _rec("05:25", [3, 3, 3, 3, 3]),
        ],
    })
    h = load_history(path, expected_sha=None)
    assert h.eligible.tolist() == [False, True, False, True]
    assert h.segment.tolist() == [0, 0, 1, 1]


def test_day_boundary_resets_segment(tmp_path):
    path = _write(tmp_path, {
        "2025-03-05": [_rec("21:55", [0, 0, 0, 0, 0])],
        "2025-03-06": [_rec("05:05", [1, 1, 1, 1, 1])],
    })
    h = load_history(path, expected_sha=None)
    assert h.eligible.tolist() == [False, False]
    assert h.segment.tolist() == [0, 1]


def test_empty_date_recorded_separately_and_not_in_dates(tmp_path):
    path = _write(tmp_path, {
        "2025-03-05": [_rec("05:05", [0, 0, 0, 0, 0])],
        "2025-03-06": [],
    })
    h = load_history(path, expected_sha=None)
    assert h.dates == ("2025-03-05",)
    assert h.empty_dates == ("2025-03-06",)
    assert h.n == 1


def test_identical_duplicate_timestamp_is_merged_with_both_urls_in_provenance(tmp_path):
    path = _write(tmp_path, {
        "2025-03-05": [
            _rec("05:05", [0, 0, 0, 0, 0], host="premios.do"),
            _rec("05:05", [0, 0, 0, 0, 0], host="loteka.com.do"),
        ],
    })
    h = load_history(path, expected_sha=None)
    assert h.n == 1
    assert 0 in h.provenance
    assert len(h.provenance[0]) == 2
    assert any("premios.do" in u for u in h.provenance[0])
    assert any("loteka.com.do" in u for u in h.provenance[0])


def test_conflicting_duplicate_raises_data_error(tmp_path):
    path = _write(tmp_path, {
        "2025-03-05": [
            _rec("05:05", [0, 0, 0, 0, 0]),
            _rec("05:05", [1, 1, 1, 1, 1]),
        ],
    })
    with pytest.raises(DataError, match="[Cc]onflict"):
        load_history(path, expected_sha=None)


@pytest.mark.parametrize("bad_numeros", [
    ["100", "01", "02", "03", "04"],
    ["7", "01", "02", "03", "04"],
    ["00", "01", "02", "03"],
    [7, 1, 2, 3, 4],
])
def test_invalid_numeros_raise_data_error(tmp_path, bad_numeros):
    path = _write(tmp_path, {"2025-03-05": [{"hora": "05:05", "numeros": bad_numeros,
                                              "source_url": "https://premios.do/x"}]})
    with pytest.raises(DataError):
        load_history(path, expected_sha=None)


@pytest.mark.parametrize("bad_hora", ["24:00", "05:60", "5:05", "0505", "05:05\n"])
def test_invalid_hora_raises_data_error(tmp_path, bad_hora):
    path = _write(tmp_path, {"2025-03-05": [{"hora": bad_hora,
                                              "numeros": ["00", "01", "02", "03", "04"],
                                              "source_url": "https://premios.do/x"}]})
    with pytest.raises(DataError):
        load_history(path, expected_sha=None)


@pytest.mark.parametrize("bad_numeros", [
    ["01\n", "01", "02", "03", "04"],
])
def test_trailing_newline_number_raises_data_error(tmp_path, bad_numeros):
    path = _write(tmp_path, {"2025-03-05": [{"hora": "05:05", "numeros": bad_numeros,
                                              "source_url": "https://premios.do/x"}]})
    with pytest.raises(DataError):
        load_history(path, expected_sha=None)


def test_non_dict_record_raises_data_error(tmp_path):
    path = _write(tmp_path, {"2025-03-05": ["not-a-dict"]})
    with pytest.raises(DataError):
        load_history(path, expected_sha=None)


def test_non_string_source_url_raises_data_error(tmp_path):
    path = _write(tmp_path, {"2025-03-05": [{"hora": "05:05",
                                              "numeros": ["00", "01", "02", "03", "04"],
                                              "source_url": 12345}]})
    with pytest.raises(DataError):
        load_history(path, expected_sha=None)


@pytest.mark.parametrize("bad_date_key", ["20250305", "2025-W10-3"])
def test_malformed_date_key_raises_data_error(tmp_path, bad_date_key):
    path = _write(tmp_path, {bad_date_key: [_rec("05:05", [0, 0, 0, 0, 0])]})
    with pytest.raises(DataError):
        load_history(path, expected_sha=None)


def test_sha_mismatch_raises_and_none_skips_check(tmp_path):
    path = _write(tmp_path, {"2025-03-05": [_rec("05:05", [0, 0, 0, 0, 0])]})
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(DataError, match=actual[:8]):
        load_history(path, expected_sha="0" * 64)
    load_history(path, expected_sha=None)
    load_history(path, expected_sha=actual)


def test_load_history_defaults_to_protocol_expected_sha(tmp_path):
    path = _write(tmp_path, {"2025-03-05": [_rec("05:05", [0, 0, 0, 0, 0])]})
    with pytest.raises(DataError, match="SHA-256 mismatch"):
        load_history(path)


def test_fmt_renders_two_digit_strings():
    assert fmt(0) == "00"
    assert fmt(7) == "07"
    assert fmt(99) == "99"


def test_row_at_exact_and_missing_label_lists_neighbors(tmp_path):
    path = _write(tmp_path, {
        "2025-03-05": [_rec("05:05", [0, 0, 0, 0, 0]), _rec("05:10", [1, 1, 1, 1, 1])],
        "2025-03-06": [_rec("05:05", [2, 2, 2, 2, 2])],
    })
    h = load_history(path, expected_sha=None)
    assert row_at(h, "2025-03-05 05:10") == 1
    with pytest.raises(DataError, match="2025-03-05 05:05"):
        row_at(h, "2025-03-05 05:07")


def test_with_nums_keeps_calendar_and_rejects_out_of_range(tmp_path):
    import numpy as np

    path = _write(tmp_path, {
        "2025-03-05": [_rec("05:05", [0, 0, 0, 0, 0]), _rec("05:10", [1, 1, 1, 1, 1])],
    })
    h = load_history(path, expected_sha=None)
    replaced = h.with_nums(np.array([[9, 9, 9, 9, 9], [8, 8, 8, 8, 8]]))
    assert replaced.dates == h.dates
    assert replaced.eligible.tolist() == h.eligible.tolist()
    assert replaced.nums.tolist() == [[9, 9, 9, 9, 9], [8, 8, 8, 8, 8]]
    with pytest.raises(DataError):
        h.with_nums(np.array([[100, 0, 0, 0, 0], [0, 0, 0, 0, 0]]))
    with pytest.raises(DataError):
        h.with_nums(np.array([[0, 0, 0, 0, 0]]))


def test_validation_report_step_histogram_and_counts(tmp_path):
    path = _write(tmp_path, {
        "2025-03-05": [
            _rec("05:05", [0, 0, 0, 0, 0]),
            _rec("05:10", [1, 1, 1, 1, 1]),
            _rec("05:20", [2, 2, 2, 2, 2]),
        ],
        "2025-03-06": [],
    })
    h = load_history(path, expected_sha=None)
    report = validation_report(h)
    assert report["rows"] == 3
    assert report["observed_days"] == 1
    assert report["empty_dates"] == ["2025-03-06"]
    assert report["step_histogram"] == {"5": 1, "10": 1}
    assert report["eligible_count"] == 1
    assert report["non_eligible_count"] == 2
    assert report["merged_duplicates"] == 0
    assert report["segments_count"] == 2


def test_make_history_builds_via_the_same_code_path():
    h = make_history([
        ("2025-03-05", "05:05", [0, 0, 0, 0, 0], "premios.do"),
        ("2025-03-05", "05:10", [1, 1, 1, 1, 1], "premios.do"),
    ])
    assert h.sha256 == "synthetic"
    assert h.dates == ("2025-03-05",)
    assert h.sources == ("premios.do",)
    assert h.eligible.tolist() == [False, True]


@pytest.mark.skipif(not REPO_HISTORY.exists(), reason="chance_express_history.json not present")
def test_real_history_loads_with_default_sha():
    load_history(REPO_HISTORY)


@pytest.mark.skipif(not REPO_HISTORY.exists(), reason="chance_express_history.json not present")
def test_real_history_file_loads_expected_shape():
    before = hashlib.sha256(REPO_HISTORY.read_bytes()).hexdigest()
    h = load_history(REPO_HISTORY, expected_sha=EXPECTED_SHA256)
    assert h.n == 105426
    assert len(h.dates) == 566
    assert len(h.empty_dates) == 4
    assert int(h.eligible.sum()) == 95818
    assert h.sources == ("premios.do", "loteka.com.do")
    counts = {name: int((h.source == i).sum()) for i, name in enumerate(h.sources)}
    assert counts["premios.do"] == 76896
    assert counts["loteka.com.do"] == 28530
    assert h.nums.min() >= 0
    assert h.nums.max() <= 99
    after = hashlib.sha256(REPO_HISTORY.read_bytes()).hexdigest()
    assert after == before
