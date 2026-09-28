"""One-shot prospective E5 healthy-control CI coverage calibration.

Usage: py -B -m strategy_tests.calibrate_e5
The twenty seeds and acceptance rule were frozen in odd/tasks/strategy-tests.md.
"""

import hashlib
import json
import time
from datetime import date

import numpy as np

from rng_audit.generators import sha256_drbg
from rng_audit.run_audit import load_draws
from strategy_tests import experiments as ex
from strategy_tests.rules import expected_return, payout_matrix
from strategy_tests.run_experiments import RANDOM_RETURN, REPORT_DIR, ROOT, TRAIN_SHARE

SEEDS = tuple(f"E5-healthy-cal-v1-{i:03d}" for i in range(1, 21))
THRESHOLD = 18
BOOTSTRAP_SEED = 7
EXPECTED_HASHES = {
    "strategy_tests.md": "d59aeef80944e4c888ffc5c996f50a4906709103c1d717c8299ad3f2e7c10e89",
    "strategy_tests.json": "028eb3ea2050cbc8e0b0596c6951914f03e1aec1090ace56aef02730cbefc883",
    "chance_express_history.json": "d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711",
}


def split_day(days):
    """Original runner's floor(60% of unique days) first held-out day."""
    return days[int(len(days) * TRAIN_SHARE)]


def pick_training(candidates, train):
    """First maximum in original E5 enumeration order, with zero-stake return -1."""
    returns = [paid[train].sum() / stake[train].sum() if stake[train].sum() else -1
               for _, stake, paid in candidates]
    index = int(np.argmax(returns))
    return index, float(returns[index])


def evaluate_one(template, seed, cut):
    d = sha256_drbg(template, seed=seed)
    pay = payout_matrix(d.nums, "all")
    _, candidates, _ = ex.e5_streak_entry(d, pay)
    if len(candidates) != 12:
        raise ValueError("E5 policy grid must contain exactly 12 candidates")
    train = d.day < cut
    index, train_ret = pick_training(candidates, train)
    label, stake, paid = candidates[index]
    held = ~train
    # The original runner seeds its bootstrap RNG with 7 and money defaults to 2,000
    # day-block resamples. A fresh RNG for each independent calibration stream.
    metric = ex.money(d.day[held], stake[held], paid[held], np.random.default_rng(BOOTSTRAP_SEED))
    if metric is None:
        raise ValueError(f"No held-out E5 stakes for {seed}")
    return {"seed": seed, "policy": label, "train_ret": train_ret,
            "ret": metric["ret"], "lo": metric["lo"], "hi": metric["hi"],
            "covered": bool(metric["lo"] <= RANDOM_RETURN <= metric["hi"])}


def make_report(rows, original, meta, elapsed):
    covered = sum(row["covered"] for row in rows)
    prior = original["held_out"]
    return {"meta": {"days": meta.get("days"), "test_from": meta.get("test_from"),
                     "train_share": TRAIN_SHARE, "bootstrap_reps": ex.BOOTSTRAP_REPS,
                     "bootstrap_seed": BOOTSTRAP_SEED, "expected_return": RANDOM_RETURN},
            "original_e5": {"policy": original["pick"], "ret": prior.get("ret"),
                            "lo": prior["lo"], "hi": prior["hi"],
                            "criterion_met": bool(prior["lo"] <= RANDOM_RETURN <= prior["hi"])},
            "records": rows,
            "aggregate": {"covered": covered, "total": len(rows), "threshold": THRESHOLD,
                          "pass": covered >= THRESHOLD and len(rows) == len(SEEDS)},
            "elapsed_seconds": elapsed}


def markdown(report):
    agg, original = report["aggregate"], report["original_e5"]
    lines = ["# Calibración prospectiva de cobertura E5 en controles sanos", "",
             ("Piloto separado: 20 corrientes SHA-256 independientes sobre el calendario original; "
              "selección entre 12 políticas E5 solo en el 60% inicial, evaluación en el 40% final. "
              "IC bootstrap 95% por días con 2.000 remuestreos por corriente y semilla fija 7. "
              "La cobertura incluye ambos límites del intervalo."), "",
             (f"**Control sano E5 original: criterio INCUMPLIDO.** Política {original['policy']}; "
              f"IC 95% [{original['lo']:.6f}, {original['hi']:.6f}] excluye 0,85. "
              "Este piloto no reemplaza ese fallo ni demuestra rentabilidad de estrategia alguna."),
             "", ("| Semilla | Política elegida | Retorno entrenamiento | Retorno prueba | "
                  "IC 95% prueba | Contiene 0,85 |"), "|---|---|---:|---:|---:|---|"]
    for row in report["records"]:
        lines.append(f"| {row['seed']} | {row['policy']} | {row['train_ret']:.6f} | "
                     f"{row['ret']:.6f} | [{row['lo']:.6f}, {row['hi']:.6f}] | "
                     f"{'sí' if row['covered'] else 'no'} |")
    lines += ["", (f"**Criterio separado: {'PASA' if agg['pass'] else 'FALLA'}** — "
                   f"{agg['covered']}/{agg['total']} intervalos contienen 0,85 "
                   f"(umbral ≥{agg['threshold']}/20)."),
              ("Piloto de precisión limitada: no aprueba retroactivamente E5 original ni "
               "garantiza cobertura universal; retorno esperado 0,85 no es rentabilidad (>1)."),
              f"Tiempo de ejecución: {report['elapsed_seconds']:.2f} s."]
    return "\n".join(lines) + "\n"


def main():
    # Check all fixed inputs and output locations before generating any outcomes.
    for name, expected in EXPECTED_HASHES.items():
        path = ROOT / ("reports" if name.startswith("strategy_tests") else "") / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit(f"Frozen input changed: {path}")
    md = REPORT_DIR / "e5_healthy_calibration.md"
    js = REPORT_DIR / "e5_healthy_calibration.json"
    if md.exists() or js.exists():
        raise SystemExit("Calibration outputs already exist; never rerun changing outcomes")
    source = ROOT / "chance_express_history.json"
    original_report = json.loads((REPORT_DIR / "strategy_tests.json").read_text(encoding="utf-8"))
    original = original_report["results"]["sano (SHA-256)"]["money"]["E5"]
    if original["held_out"] is None or original["held_out"]["hi"] >= RANDOM_RETURN:
        raise SystemExit("Expected original E5 failure is not present")
    if expected_return("all") != RANDOM_RETURN or ex.BOOTSTRAP_REPS != 2000:
        raise SystemExit("Original return or bootstrap convention changed")
    template = load_draws(source)
    days = np.unique(template.day)
    cut = split_day(days)
    if len(days) != 566 or date.fromordinal(int(cut)).isoformat() != "2026-02-10":
        raise SystemExit("Historical timeline or fixed split changed")
    start = time.perf_counter()
    rows = [evaluate_one(template, seed, cut) for seed in SEEDS]
    report = make_report(rows, original, {"days": len(days), "test_from": "2026-02-10"},
                         time.perf_counter() - start)
    md.write_text(markdown(report), encoding="utf-8")
    js.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"E5 healthy coverage: {report['aggregate']['covered']}/20; "
          f"{'PASA' if report['aggregate']['pass'] else 'FALLA'}; "
          f"{report['elapsed_seconds']:.2f}s")


if __name__ == "__main__":
    main()
