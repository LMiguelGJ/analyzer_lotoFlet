"""Report rendering from persisted, incomplete run evidence."""
import json

from chance_rank import report


def test_partial_report_has_fourteen_sections_and_no_false_success(tmp_path, monkeypatch):
    (tmp_path / "metrics.json").write_text(json.dumps({"primary": {"stage": "partial", "n_primary_targets": 12,
        "systems": {"freq_hist": {"available": True, "uniform": {"delta": -0.01},
                                 "recent500": {"delta": 0.0}, "classification": {"label": "inconclusive"}}},
        "holm_family_order": [["freq_hist", "uniform"]]}, "status": "partial: supervised pending"}), encoding="utf-8")
    (tmp_path / "protocol.json").write_text(json.dumps({"protocol_hash": "abc", "protocol": {"protocol_id": "chance-rank-v1"}}), encoding="utf-8")
    (tmp_path / "status.json").write_text(json.dumps({"state": "partial", "reason": "budget"}), encoding="utf-8")
    def forbidden(*_args, **_kwargs):
        raise AssertionError("report must not compute models or load the history")
    monkeypatch.setattr("chance_rank.models.score_config", forbidden)
    text = report.build_report(tmp_path)
    assert [" ".join(line.split(" ", 2)[:2]) for line in text.splitlines() if line.startswith("## ")] == [f"## {i}." for i in range(1, 15)]
    assert "retrospectivo" in text.lower() and "exploratorio" in text.lower()
    assert "no constituye confirmación prospectiva" in text.lower()
    assert "supervisada pendiente" in text.lower()
    assert "N/A" in text and "freq_hist" in text
    assert (tmp_path / "resumen.md").read_text(encoding="utf-8") == text


def test_report_without_metrics_is_explicitly_partial(tmp_path):
    text = report.build_report(tmp_path)
    assert "N/A" in text and "incompleto" in text.lower()
