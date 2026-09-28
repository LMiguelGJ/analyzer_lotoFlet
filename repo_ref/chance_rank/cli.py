"""Command-line interface for validated, retrospective Chance Express analysis."""
import argparse
import json
import sys
from bisect import bisect_left
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from chance_rank import artifacts, data, models, pipeline, protocol, ranking, report


def _parser():
    parser = argparse.ArgumentParser(prog="chance_rank")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--input", required=True)
    smoke = commands.add_parser("smoke")
    smoke.add_argument("--protocol", required=True)
    run = commands.add_parser("run")
    run.add_argument("--input", required=True)
    run.add_argument("--protocol", required=True)
    run.add_argument("--stage", choices=("interpretable", "supervised"), required=True)
    run.add_argument("--out", default="reports/chance_rank_v1")
    run.add_argument("--max-seconds", type=float)
    render = commands.add_parser("report")
    render.add_argument("--run", required=True)
    inspect_cmd = commands.add_parser("inspect")
    inspect_cmd.add_argument("--run", required=True)
    inspect_cmd.add_argument("--at", required=True)
    inspect_cmd.add_argument("--model", required=True)
    inspect_cmd.add_argument("--k", type=int, required=True)
    inspect_cmd.add_argument("--horizon", type=int, required=True)
    inspect_cmd.add_argument("--reveal", action="store_true")
    inspect_cmd.add_argument("--input")
    return parser


def _history_inspection(h, at, model):
    labels = [h.label(i) for i in range(h.n)]
    i = bisect_left(labels, at)
    if i >= h.n or labels[i] != at:
        before = labels[i - 1] if i else "N/A"
        after = labels[i] if i < h.n else "N/A"
        print(f"Fecha ausente; vecinos: {before} / {after}", file=sys.stderr)
        return None
    if model != "notebook":
        raise ValueError("Fuera de evaluación solo se admite notebook reciente500")
    cid = protocol.config_id("notebook", {"weights": [0.45, 0.45, 0.10], "window": 500})
    # Materialize only the observed prefix. The target is a metadata-only placeholder;
    # neither its values nor any future rows reach the scorer.
    nums = h.nums[:i + 1].copy()
    nums[i] = 0
    prefix = replace(h, nums=nums, **{field: getattr(h, field)[:i + 1]
                                        for field in ("day", "slot", "hour", "weekday", "day_pos",
                                                      "source", "eligible", "segment")})
    key = models.ranking_key_config(prefix, cid, 0)
    order = ranking.rank_matrix(key[i:i + 1])[0].tolist()
    end = i + 1
    while end < min(h.n, i + protocol.HORIZONS[-1]) and h.segment[end] == h.segment[i]:
        end += 1
    return {"ranking100": order, "cutoff": labels[i - 1] if i else "sin historial",
            "status": "demostración/no evaluado", "result": h.nums[i].tolist(),
            "horizon_results": h.nums[i:end].tolist(),
            "horizon_available": end - i}


def inspect(run_dir, at, model, k, horizon, *, reveal=False, history=None, input_path=None,
            expected_sha: str | None = protocol.EXPECTED_SHA256):
    """Read evaluated rankings from the saved export, or causal notebook on a prefix."""
    if not (1 <= k <= 100) or horizon not in protocol.HORIZONS:
        raise ValueError("K debe ser 1..100 y horizonte uno de 1,5,10,20")
    root = Path(run_dir)
    frozen = root / "protocol.json"
    if frozen.exists():
        try:
            saved = json.loads(frozen.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Protocolo guardado ilegible") from exc
        if saved.get("protocol_hash") != protocol.protocol_hash():
            raise ValueError("Incompatibilidad de protocolo en ejecución guardada")
    pred_path = artifacts.predictions_path(str(root), "pos1")
    if Path(pred_path).is_file():
        with np.load(pred_path) as pred:
            timestamps = pred["timestamps"].tolist()
            matches = [j for j, stamp in enumerate(timestamps) if stamp == at]
            if matches:
                j = matches[0]
                system = model
                if model == "family":
                    system = "freq_hist"
                elif model == "selector":
                    system = "select_interpretable"
                elif ":" in model:
                    fold_index = int(pred["fold_id"][j])
                    matches_config = [s for s in pred["systems"].tolist()
                                      if f"ranking100__{s}" in pred.files
                                      and f"config_id__{s}" in pred.files
                                      and str(pred[f"config_id__{s}"][fold_index]) == model]
                    if not matches_config:
                        raise ValueError(f"Configuración no seleccionada en este fold: {model}")
                    system = matches_config[0]
                elif model == "config":
                    raise ValueError("--model config requiere el identificador concreto de la configuración guardada")
                key = f"ranking100__{system}"
                if key not in pred.files:
                    raise ValueError(f"Sistema no disponible en export: {system}")
                order = pred[key][j].tolist()
                cid = pred[f"config_id__{system}"][int(pred["fold_id"][j])] if f"config_id__{system}" in pred.files else pipeline.RECENT500_ID
                end = j + 1
                while end < min(len(timestamps), j + horizon):
                    if (int(pred["row_ids"][end]) != int(pred["row_ids"][end - 1]) + 1
                            or int(pred["fold_id"][end]) != int(pred["fold_id"][j])
                            or str(pred["cutoff"][end]) != timestamps[end - 1]):
                        break
                    end += 1
                result = {"ranking100": order, "cutoff": str(pred["cutoff"][j]),
                          "status": "evaluado (retrospectivo)", "config": str(cid),
                          "horizon_observed": end - j}
                if reveal:
                    with np.load(artifacts.results_path(str(root), "pos1")) as actual:
                        if not np.array_equal(actual["row_ids"], pred["row_ids"]):
                            raise ValueError("Resultados no alineados con predicciones")
                        result["result"] = actual["y_true"][j:end].astype(int).tolist()
                        rank_key = f"winner_rank__{system}"
                        if rank_key in actual.files and len(actual[rank_key]) > j:
                            rank = int(actual[rank_key][j])
                            if order[rank] != int(actual["y_true"][j]):
                                raise ValueError("Outcome rank does not align with saved ranking")
                            result["winner_rank"] = rank
                    any_path = artifacts.results_path(str(root), "any")
                    if Path(any_path).is_file():
                        with np.load(any_path) as all_positions:
                            if np.array_equal(all_positions["row_ids"][j:end], pred["row_ids"][j:end]):
                                values = all_positions["y_true"][j:end].astype(int).tolist()
                                result["result"] = values[0] if len(values) == 1 else values
                if reveal:
                    values = result["result"]
                    draws = values if values and isinstance(values[0], list) else [values]
                    result["hits"] = [sum(v in order[:k] for v in draw) for draw in draws]
                _print_inspection(result, k, horizon, reveal)
                return result
            if input_path is None and history is None:
                ordered = sorted(timestamps)
                index = bisect_left(ordered, at)
                before = ordered[index - 1] if index else "N/A"
                after = ordered[index] if index < len(ordered) else "N/A"
                print(f"Fecha ausente o fuera de evaluación; vecinos: {before} / {after}; "
                      "--input para demostración", file=sys.stderr)
                return None
    if history is None:
        if input_path is None:
            raise ValueError("--input requerido fuera de filas evaluadas exportadas")
        history = data.load_history(input_path, expected_sha=expected_sha)
    result = _history_inspection(history, at, model)
    if result is None:
        return None
    result["horizon_observed"] = min(horizon, result.pop("horizon_available"))
    if reveal:
        if result["horizon_observed"] > 1:
            result["result"] = result["horizon_results"][:result["horizon_observed"]]
    else:
        result.pop("result")
    result.pop("horizon_results")
    _print_inspection(result, k, horizon, reveal)
    return result


def _print_inspection(result, k, horizon, reveal):
    print(f"{result['status']} | corte: {result['cutoff']} | K={k} H={horizon}")
    print("lista congelada:", " ".join(f"{v:02d}" for v in result["ranking100"][:k]))
    if result.get("horizon_observed", 1) < horizon:
        print(f"Horizonte truncado: {result['horizon_observed']} de {horizon} por límite de segmento/fold/export.")
    if reveal:
        values = result["result"]
        draws = values if values and isinstance(values[0], list) else [values]
        print("resultado:", " / ".join(" ".join(f"{v:02d}" for v in draw) for draw in draws))
        print("aciertos:", result.get("hits", [sum(v in result["ranking100"][:k] for v in draw)
                                              for draw in draws]))


def _smoke():
    rng = protocol.rng("chance-rank-v1/smoke")
    entries = []
    for day in range(3):
        stamp = (date(2024, 1, 1) + timedelta(days=day)).isoformat()
        for r in range(8):
            entries.append((stamp, f"00:{r * 5:02d}", rng.integers(0, 100, 5).tolist(), "synthetic.example"))
    h = data.make_history(entries)
    cid = protocol.config_id("freq_recent", {"window": 500})
    order = ranking.rank_matrix(models.ranking_key_config(h, cid, 0))
    assert order.shape == (h.n, 100) and np.array_equal(np.sort(order, axis=1)[0], np.arange(100))
    print("smoke sintético: OK; sin datos reales ni métricas predictivas")


def main(argv=None, *, expected_sha: str | None = protocol.EXPECTED_SHA256):
    args = _parser().parse_args(argv)
    try:
        if args.command in ("smoke", "run") and args.protocol != protocol.PROTOCOL_ID:
            raise ValueError("Protocolo incompatible")
        if args.command == "validate":
            print(json.dumps(data.validation_report(data.load_history(args.input, expected_sha=expected_sha)),
                             ensure_ascii=False))
        elif args.command == "smoke":
            _smoke()
        elif args.command == "run":
            if args.stage == "supervised":
                raise ValueError("Fase supervisada pendiente de CR-7")
            result = pipeline.run_interpretable(data.load_history(args.input, expected_sha=expected_sha),
                                                 args.out, max_seconds=args.max_seconds)
            print(json.dumps({k: result[k] for k in ("status", "reason", "next_step") if k in result}))
        elif args.command == "report":
            report.build_report(args.run)
            print(str(Path(args.run) / "resumen.md"))
        else:
            found = inspect(args.run, args.at, args.model, args.k, args.horizon,
                            reveal=args.reveal, input_path=args.input, expected_sha=expected_sha)
            if found is None:
                return 2
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0
