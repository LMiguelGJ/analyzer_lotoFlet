"""CLI boundaries and prefix-only inspection on synthetic histories."""
import json
from datetime import date, timedelta

import numpy as np

from chance_rank import cli, protocol
from chance_rank.data import make_history


def _history():
    rng = protocol.rng("cli-fixture")
    return make_history([((date(2024, 1, 1) + timedelta(days=d)).isoformat(),
                          f"00:{5*r:02d}", rng.integers(0, 100, 5).tolist(), "example.org")
                         for d in range(4) for r in range(8)])


def test_validate_enforces_sha_and_accepts_explicit_synthetic_override(tmp_path, capsys):
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"sorteos_por_fecha": {"2024-01-01": [
        {"hora": "00:00", "numeros": ["01"] * 5, "source_url": "https://example.org"}]}}), encoding="utf-8")
    assert cli.main(["validate", "--input", str(path)]) == 2
    assert cli.main(["validate", "--input", str(path)], expected_sha=None) == 0
    assert "rows" in capsys.readouterr().out


def test_supervised_and_bad_protocol_fail_without_running(tmp_path):
    assert cli.main(["run", "--input", "unused", "--protocol", "chance-rank-v1",
                     "--stage", "supervised", "--out", str(tmp_path)]) == 2
    assert cli.main(["smoke", "--protocol", "wrong"]) == 2
    assert not list(tmp_path.iterdir())


def test_inspect_notebook_uses_prefix_and_hides_target(tmp_path, capsys):
    h = _history()
    stamp = h.label(17)
    result = cli.inspect(tmp_path, stamp, "notebook", 25, 1, history=h)
    output = capsys.readouterr().out
    assert result is not None
    assert result["status"] == "demostración/no evaluado"
    assert "no evaluado" in output and "resultado:" not in output
    assert len(result["ranking100"]) == 100
    altered = h.nums.copy()
    altered[17:] = 99
    other = cli.inspect(tmp_path, stamp, "notebook", 25, 1, history=h.with_nums(altered))
    assert other is not None
    assert result["ranking100"] == other["ranking100"]
    revealed = cli.inspect(tmp_path, stamp, "notebook", 25, 1, history=h, reveal=True)
    assert revealed is not None
    assert revealed["result"] == h.nums[17].tolist()
    assert "resultado:" in capsys.readouterr().out


def test_inspect_missing_timestamp_suggests_neighbors(tmp_path, capsys):
    assert cli.inspect(tmp_path, "2024-01-01 00:12", "notebook", 25, 1, history=_history()) is None
    error = capsys.readouterr().err
    assert "00:10" in error and "00:15" in error


def test_inspect_horizon_reveal_requires_contiguous_saved_targets(tmp_path, capsys):
    folder = tmp_path / "predictions"
    folder.mkdir()
    order = np.arange(100, dtype=np.uint8)
    np.savez(folder / "pos1.npz", timestamps=np.array(["2024-01-01 00:05", "2024-01-01 00:10", "2024-01-01 00:20"]),
             cutoff=np.array(["2024-01-01 00:00", "2024-01-01 00:05", "2024-01-01 00:15"]),
             row_ids=np.array([1, 2, 4]), fold_id=np.array([0, 0, 0]), systems=np.array(["freq_hist"]),
             config_id__freq_hist=np.array(["freq_hist:scope=position,window=none"]),
             ranking100__freq_hist=np.tile(order, (3, 1)))
    np.savez(folder / "results_pos1.npz", row_ids=np.array([1, 2, 4]), y_true=np.array([3, 7, 9]))
    result = cli.inspect(tmp_path, "2024-01-01 00:05", "freq_hist", 5, 5, reveal=True)
    assert result is not None
    assert result["result"] == [3, 7]
    assert result["horizon_observed"] == 2
    assert "horizonte truncado" in capsys.readouterr().out.lower()


def test_inspect_evaluated_reads_saved_order_without_scoring(tmp_path, capsys, monkeypatch):
    from chance_rank import artifacts
    h = _history()
    target = 17
    stamp = h.label(target)
    folder = tmp_path / "predictions"
    folder.mkdir()
    order = np.arange(100, dtype=np.uint8)[::-1]
    np.savez(folder / "pos1.npz", timestamps=np.array([stamp]), cutoff=np.array([h.label(16)]),
             row_ids=np.array([target]), fold_id=np.array([0]), systems=np.array(["freq_hist"]),
             config_id__freq_hist=np.array(["freq_hist:scope=position,window=none"]),
             ranking100__freq_hist=order.reshape(1, 100))
    np.savez(folder / "results_pos1.npz", row_ids=np.array([target]), y_true=np.array([7]))
    monkeypatch.setattr("chance_rank.models.score_config", lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("recompute")))
    result = cli.inspect(tmp_path, stamp, "freq_hist", 25, 1)
    assert result is not None
    assert result["ranking100"] == order.tolist()
    assert "resultado:" not in capsys.readouterr().out
    assert "winner_rank" not in result and "hits" not in result
    revealed = cli.inspect(tmp_path, stamp, "freq_hist", 25, 1, reveal=True)
    assert revealed is not None and revealed["result"] == [7]
    assert revealed["hits"] == [int(7 in order[:25])]
    assert artifacts.predictions_path(str(tmp_path), "pos1").endswith("pos1.npz")
    config = cli.inspect(tmp_path, stamp, "freq_hist:scope=position,window=none", 25, 1)
    assert config is not None and config["ranking100"] == order.tolist()


def test_inspect_only_opens_results_on_reveal_and_checks_rank_alignment(tmp_path, monkeypatch):
    import pytest

    from chance_rank import artifacts

    folder = tmp_path / "predictions"
    folder.mkdir()
    order = np.arange(100, dtype=np.uint8)
    np.savez(folder / "pos1.npz", timestamps=np.array(["2024-01-01 00:05"]),
             cutoff=np.array(["2024-01-01 00:00"]), row_ids=np.array([1]),
             fold_id=np.array([0]), systems=np.array(["freq_hist"]),
             config_id__freq_hist=np.array(["freq_hist:scope=position,window=none"]),
             ranking100__freq_hist=order.reshape(1, 100))
    np.savez(folder / "results_pos1.npz", row_ids=np.array([1]), y_true=np.array([7]),
             winner_rank__freq_hist=np.array([8], dtype=np.uint8))
    real_load = np.load

    def guarded(path, *args, **kwargs):
        if str(path) == artifacts.results_path(str(tmp_path), "pos1"):
            raise AssertionError("results opened without reveal")
        return real_load(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(cli.np, "load", guarded)
        hidden = cli.inspect(tmp_path, "2024-01-01 00:05", "freq_hist", 25, 1)
        assert hidden is not None and "result" not in hidden
    with pytest.raises(ValueError, match="rank does not align"):
        cli.inspect(tmp_path, "2024-01-01 00:05", "freq_hist", 25, 1, reveal=True)
    np.savez(folder / "results_pos1.npz", row_ids=np.array([1]), y_true=np.array([7]),
             winner_rank__freq_hist=np.array([7], dtype=np.uint8))
    revealed = cli.inspect(tmp_path, "2024-01-01 00:05", "freq_hist", 25, 1, reveal=True)
    assert revealed is not None and revealed["winner_rank"] == 7
    assert revealed["hits"] == [1]
