"""Audit Chance Express draws with NIST SP 800-22 and lottery-specific tests.

Usage: py -m rng_audit.run_audit [path/to/chance_express_history.json]
Reads the history file only; writes reports/rng_audit.md and reports/rng_audit.json.
"""

import json
import math
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
from scipy.stats import chisquare

from rng_audit import lottery_tests, nist_sp800_22
from rng_audit.generators import CONTROLS
from rng_audit.lottery_tests import Draws

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "reports"
SHORT_SEQ, SHORT_COUNT = 100_000, 20
LONG_SEQ, LONG_COUNT = 1_000_000, 2
LONG_ONLY = ("universal", "random_excursions", "random_excursions_variant")
ALPHA = 0.01


def load_draws(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))["sorteos_por_fecha"]
    rows = []
    for key in sorted(data):
        day = date.fromisoformat(key)
        for rec in sorted(data[key], key=lambda r: r["hora"]):
            hour, minute = map(int, rec["hora"].split(":"))
            rows.append((day.toordinal(), hour * 60 + minute, day.weekday(), day.month,
                         [int(x) for x in rec["numeros"]]))
    cols = list(zip(*rows, strict=True))
    return Draws(np.array(cols[4], dtype=np.int64), np.array(cols[0]), np.array(cols[1]),
                 np.array(cols[2]), np.array(cols[3]))


def six_bit_stream(d):
    """Keep only values 0-63 so every kept value maps to exactly 6 unbiased bits."""
    values = d.nums.ravel()
    values = values[values < 64].astype(np.uint8)
    return np.unpackbits(values[:, None], axis=1)[:, 2:].ravel()


def nist_verdict(pvals):
    m = len(pvals)
    if m == 0:
        return {"m": 0, "passed": 0, "verdict": "N/A"}
    p = np.asarray(pvals)
    passed = int(np.count_nonzero(p >= ALPHA))
    bound = (1 - ALPHA) - 3 * math.sqrt(ALPHA * (1 - ALPHA) / m)
    uniform_p = None
    if m >= 55:
        uniform_p = float(chisquare(np.histogram(p, bins=10, range=(0, 1))[0])[1])
    ok = passed / m >= bound and (uniform_p is None or uniform_p >= 1e-4)
    return {"m": m, "passed": passed, "bound": bound, "uniform_p": uniform_p,
            "verdict": "PASA" if ok else "FALLA"}


def run_nist(bits, seq_len, count, only=None):
    collected = {}
    for i in range(min(count, len(bits) // seq_len)):
        chunk = bits[i * seq_len : (i + 1) * seq_len]
        tests = only or [name for name in nist_sp800_22.run_suite.__code__.co_names
                         if name in NIST_NAMES]
        for name in tests:
            collected.setdefault(name, []).extend(getattr(nist_sp800_22, name)(chunk))
    return collected


NIST_NAMES = ("frequency", "block_frequency", "runs", "longest_run", "binary_matrix_rank",
              "dft", "non_overlapping_template", "overlapping_template", "universal",
              "linear_complexity", "serial", "approximate_entropy", "cumulative_sums",
              "random_excursions", "random_excursions_variant")


def nist_for(d):
    bits6 = six_bit_stream(d)
    short = run_nist(bits6, SHORT_SEQ, SHORT_COUNT)
    long = run_nist(bits6, LONG_SEQ, LONG_COUNT, only=LONG_ONLY)
    six = {name: nist_verdict(long[name] if name in LONG_ONLY else short.get(name, []))
           for name in NIST_NAMES}
    parity = {}
    for pos in range(5):
        seq = (d.nums[:SHORT_SEQ, pos] % 2).astype(np.uint8)
        for name, pvals in nist_sp800_22.run_suite(seq).items():
            parity.setdefault(name, []).extend(pvals)
    return {"bits_6": six, "bits_6_count": int(len(bits6)),
            "parity": {name: nist_verdict(parity.get(name, [])) for name in NIST_NAMES}}


def holm(pvals):
    order = np.argsort(pvals)
    m, adjusted, running = len(pvals), np.empty(len(pvals)), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adjusted[i] = running
    return adjusted


def bh(pvals):
    order = np.argsort(pvals)[::-1]
    m, adjusted, running = len(pvals), np.empty(len(pvals)), 1.0
    for rank, i in enumerate(order):
        running = min(running, pvals[i] * m / (m - rank))
        adjusted[i] = running
    return adjusted


def lottery_for(d):
    results = lottery_tests.run_all(d)
    p = np.array([r["p"] for r in results])
    for r, h, f in zip(results, holm(p), bh(p), strict=True):
        r["p_holm"], r["p_bh"] = float(h), float(f)
        if h < ALPHA:
            r["verdict"] = "FALLA"
        elif r["p"] < ALPHA:
            r["verdict"] = "SOSPECHOSA"
        else:
            r["verdict"] = "PASA"
    return results


ICON = {"PASA": "✅", "FALLA": "❌", "SOSPECHOSA": "⚠️", "N/A": "—"}


def fmt_p(p):
    return "<1e-300" if p < 1e-300 else (f"{p:.2e}" if p < 1e-3 else f"{p:.4f}")


def write_report(audit, source, sha):
    names = list(audit)
    loteka = audit["Loteka"]
    lines = [
        "# Auditoría del generador de Chance Express", "",
        f"- Fuente: `{source.name}` (SHA-256 `{sha[:16]}…`, solo lectura)",
        f"- Sorteos: {loteka['draws']:,} · Días: {loteka['days']} · "
        f"Bits NIST (6 bits, valores 00-63): {loteka['nist']['bits_6_count']:,}",
        f"- Criterio: α = {ALPHA}; pruebas específicas con corrección de Holm; "
        "NIST con la regla de proporción de SP 800-22 (y uniformidad de p cuando m ≥ 55).",
        "", "## 1. Veredicto por dataset", "",
        "| Dataset | Pruebas específicas que fallan | NIST 6 bits que fallan | NIST paridad que fallan |",
        "|---|---:|---:|---:|",
    ]
    for name in names:
        a = audit[name]
        fails = [r["id"] for r in a["lottery"] if r["verdict"] == "FALLA"]
        n6 = [k for k, v in a["nist"]["bits_6"].items() if v["verdict"] == "FALLA"]
        npar = [k for k, v in a["nist"]["parity"].items() if v["verdict"] == "FALLA"]
        lines.append(f"| **{name}** | {len(fails)}/{len(a['lottery'])} "
                     f"{', '.join(fails[:8])}{'…' if len(fails) > 8 else ''} | "
                     f"{len(n6)}/15 {', '.join(n6)} | {len(npar)}/15 {', '.join(npar)} |")
    lines += ["", "## 2. Pruebas específicas 00-99 (todas las columnas)", "",
              "| ID | Prueba | " + " | ".join(names) + " |",
              "|---|---|" + "---|" * len(names)]
    for i, r in enumerate(loteka["lottery"]):
        cells = []
        for name in names:
            rr = audit[name]["lottery"][i]
            cells.append(f"{ICON[rr['verdict']]} {fmt_p(rr['p_holm'])}")
        lines.append(f"| {r['id']} | {r['name']} | " + " | ".join(cells) + " |")
    lines += ["", "Cada celda: veredicto y p corregido por Holm.", "",
              "## 3. NIST SP 800-22", ""]
    for stream, title in (("bits_6", "Flujo de 6 bits (20 × 100.000 bits; "
                                     "Maurer y excursiones: 2 × 1.000.000)"),
                          ("parity", "Paridad de cada globo (5 × 100.000 bits)")):
        lines += [f"### {title}", "", "| Prueba NIST | " + " | ".join(names) + " |",
                  "|---|" + "---|" * len(names)]
        for test in NIST_NAMES:
            cells = []
            for name in names:
                v = audit[name]["nist"][stream][test]
                cells.append("—" if v["m"] == 0 else
                             f"{ICON[v['verdict']]} {v['passed']}/{v['m']}")
            lines.append(f"| {test} | " + " | ".join(cells) + " |")
        lines += ["", "Cada celda: veredicto y p-values ≥ 0,01 sobre el total. "
                      "— = no aplicable al largo de la secuencia.", ""]
    lines += ["## 4. Detalle de Loteka", "",
              "| ID | Prueba | p | p Holm | Veredicto | Detalle |", "|---|---|---:|---:|---|---|"]
    for r in loteka["lottery"]:
        lines.append(f"| {r['id']} | {r['name']} | {fmt_p(r['p'])} | {fmt_p(r['p_holm'])} | "
                     f"{ICON[r['verdict']]} {r['verdict']} | {r['detail']} |")
    lines += ["", "## 5. Limitaciones", "",
              "- Dieharder no se corrió: necesita cientos de MB y aquí hay ~250 KB; "
              "reciclaría datos y daría falsos fallos.",
              "- TestU01 no se corrió: no hay compilador C y no se instalaron dependencias.",
              "- NIST se implementó en numpy/scipy y se validó con los ejemplos numéricos "
              "de SP 800-22 (`rng_audit/test_nist_examples.py`).",
              "- B1b (fuente de 16 bits) tiene poca potencia: el sesgo esperado (0,00035) "
              "es menor que el error estadístico con este volumen de datos.",
              "- Ninguna prueba identifica el algoritmo exacto: al reducir cada salida a 00-99 "
              "se pierde la información necesaria.", ""]
    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "rng_audit.md").write_text("\n".join(lines), encoding="utf-8")
    (REPORT_DIR / "rng_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    import hashlib

    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "chance_express_history.json"
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    loteka = load_draws(source)
    datasets = {"Loteka": loteka}
    datasets.update({name: make(loteka) for name, make in CONTROLS.items()})
    audit = {}
    for name, d in datasets.items():
        start = time.time()
        audit[name] = {"draws": int(len(d.nums)), "days": int(len(np.unique(d.day))),
                       "lottery": lottery_for(d), "nist": nist_for(d)}
        print(f"{name:22} listo en {time.time() - start:5.1f}s", flush=True)
    write_report(audit, source, sha)
    print(f"Reporte: {REPORT_DIR / 'rng_audit.md'}")


if __name__ == "__main__":
    main()
