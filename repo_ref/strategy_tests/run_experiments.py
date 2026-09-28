"""Run betting-strategy experiments E1-E8 plus descriptive Loteka E9 and write a Spanish report.

Usage: py -m strategy_tests.run_experiments [path/to/chance_express_history.json]
Reads the history file only; writes reports/strategy_tests.md and reports/strategy_tests.json.
"""

import hashlib
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

from rng_audit.run_audit import ALPHA, fmt_p, holm, load_draws
from strategy_tests import experiments as ex
from strategy_tests.controls import CONTROLS
from strategy_tests.rules import expected_return, payout_matrix

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "reports"
TRAIN_SHARE = 0.6
RANDOM_RETURN = expected_return("all")
IDEAS = {
    "E1": ("#1", "Mitades tras racha", "¿Después de N iguales (par/impar, bajo/alto) sale más la otra mitad?"),
    "E2": ("#2", "Números fríos", "¿Un número que lleva X sorteos sin salir 1º sale más?"),
    "E3": ("#6", "Arrastre", "¿Un número del sorteo anterior sube al 1º?"),
    "E4": ("#12", "Dobles", "¿Un número que salió doble vuelve pronto?"),
    "E5": ("#21", "Entrar tras N fallos", "¿Esperar N iguales y cubrir la otra mitad paga más?"),
    "E6": ("#26", "Audaz vs tímida", "¿Los datos reales se comportan como un juego justo al buscar una meta?"),
    "E7": ("#27", "Regla de repetidos", "¿Cuánto cambia el margen según cómo paguen un número repetido?"),
    "E8": ("#29", "Cambio de fuente", "¿premios.do y loteka.com.do se comportan igual?"),
}
ICON = {"PASA": "✅", "FALLA": "❌", "SOSPECHOSA": "⚠️"}


def load_sources(path):
    """Source host per draw, in the same order as rng_audit.run_audit.load_draws."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))["sorteos_por_fecha"]
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(f"Cannot read draw history from {path}: {exc}") from exc
    return np.array([rec["source_url"].split("/")[2]
                     for key in sorted(data)
                     for rec in sorted(data[key], key=lambda r: r["hora"])])


def money_verdict(m):
    if m is None:
        return "sin apuestas"
    if m["lo"] > RANDOM_RETURN:
        return "SUPERA RETORNO ALEATORIO"
    if m["hi"] < RANDOM_RETURN:
        return "BAJO RETORNO ALEATORIO"
    return "INCONCLUSO VS AZAR"


def evaluate_money(d, candidates, train, rng):
    """Money for every candidate on all data, then the training pick on held-out days only."""
    grid = [{"label": label, **(ex.money(d.day, stake, paid, rng) or {})}
            for label, stake, paid in candidates]
    train_ret = [paid[train].sum() / stake[train].sum() if stake[train].sum() else -1
                 for _, stake, paid in candidates]
    best = int(np.argmax(train_ret))
    label, stake, paid = candidates[best]
    test = ~train
    held = ex.money(d.day[test], stake[test], paid[test], rng)
    return {"grid": grid, "pick": label, "train_ret": float(train_ret[best]), "held_out": held,
            "verdict": money_verdict(held)}


def run_dataset(d, source, train):
    rng = np.random.default_rng(7)
    pay, pay_best = payout_matrix(d.nums, "all"), payout_matrix(d.nums, "best")
    e1, _ = ex.e1_halves(d)
    e2, c2 = ex.e2_cold(d, pay)
    e3, c3 = ex.e3_carry(d, pay)
    e4, c4 = ex.e4_doubles(d, pay)
    e5, c5, ladders = ex.e5_streak_entry(d, pay)
    e6, sessions = ex.e6_bold(d, pay)
    e8, per_source = ex.e8_sources(d, source)
    tests = e1 + e2 + e3 + e4 + e5 + e6 + e8
    tested = [t for t in tests if t["p"] is not None]
    for t, h in zip(tested, holm(np.array([t["p"] for t in tested])), strict=True):
        t["p_holm"] = float(h)
        t["verdict"] = "FALLA" if h < ALPHA else ("SOSPECHOSA" if t["p"] < ALPHA else "PASA")
    money = {"E2": evaluate_money(d, c2, train, rng), "E3": evaluate_money(d, c3, train, rng),
             "E4": evaluate_money(d, c4, train, rng), "E5": evaluate_money(d, c5, train, rng)}
    pick_stake, pick_paid, _ = ladders[money["E5"]["pick"]]
    ladder_rows = [{"label": label, "lost_ladders": lost,
                    **(ex.money(d.day, stake, paid, rng) or {})}
                   for label, (stake, paid, lost) in ladders.items()]
    money["E5 escalera"] = {
        "grid": ladder_rows, "pick": money["E5"]["pick"],
        "held_out": ex.money(d.day[~train], pick_stake[~train], pick_paid[~train], rng)}
    money["E5 escalera"]["verdict"] = money_verdict(money["E5 escalera"]["held_out"])
    return {"tests": tests, "money": money, "sessions": sessions,
            "repeat_rule": ex.e7_repeat_rule(d, pay, pay_best),
            "sources": {k: {**v, "first_day": date.fromordinal(v["first_day"]).isoformat(),
                            "last_day": date.fromordinal(v["last_day"]).isoformat()}
                        for k, v in per_source.items()}}


def idea_cell(result, prefix):
    all_rows = [t for t in result["tests"] if t["id"].startswith(prefix + " ")]
    tests = [t for t in all_rows if t["p"] is not None]
    missing = len(all_rows) - len(tests)
    fails = sum(t["verdict"] == "FALLA" for t in tests)
    suspects = sum(t["verdict"] == "SOSPECHOSA" for t in tests)
    icon = "❌" if fails else ("⚠️" if suspects or missing else "✅")
    extra = f", {suspects} sospechosas" if suspects else ""
    extra += f", {missing} N/A" if missing else ""
    return f"{icon} {fails}/{len(tests)} pruebas válidas fallan{extra}"


def fmt_money(m):
    if not m or "ret" not in m:
        return "—"
    return f"{m['ret']:.4f} [{m['lo']:.3f}–{m['hi']:.3f}]"


def pct(x):
    return "—" if x is None else f"{100 * x:.2f}%"


def n_summary(result):
    """Compact view of all prespecified E1/E5 thresholds, without choosing a winner."""
    lines = ["## Resumen de todos los N (Loteka)", "",
             ("E1 cuenta el cambio tras exactamente N iguales; E5 cuenta la entrada tras ≥N. "
              "Todas las variantes y N; el detalle estadístico completo sigue más abajo."), ""]
    for prefix, title in (("E1", "E1: N=1–10, cambio de mitad"),
                          ("E5", "E5: N≥3–8, cambio a la otra mitad")):
        lines += [f"### {title}", "", "| Variante y N | Casos | Tasa observada |",
                  "|---|---:|---:|"]
        for row in result["tests"]:
            if row["id"].startswith(prefix + " "):
                lines.append(f"| {row['id']} | {row['n']:,} | {pct(row['observed'])} |")
        lines.append("")
    return lines


def e9_section(result):
    """One row for every previous first-position value, including values without cases."""
    lines = ["## E9. Tras X exacto (00–99): siguiente primer globo, solo Loteka", "",
             ("Exploratorio y descriptivo, añadido después de E1–E8. Solo pares de sorteos "
              "consecutivos del mismo día; el siguiente primer globo es el destino. "
              "Referencia bajo azar: 1% de repetición de X (no un umbral de decisión). "
              "Las transiciones adyacentes se solapan y esta búsqueda es post hoc: "
              "no hay p por X, ni nueva familia Holm, ni un X elegido como predicción. "
              "La matriz completa 100×100 de conteos por origen y destino está en el JSON."), "",
             "| X anterior | Casos | Repite X | Tasa de repetición | Nota |",
             "|---|---:|---:|---:|---|"]
    for row in result["rows"]:
        note = "sin casos" if row["count"] == 0 else "descriptivo; no predice"
        lines.append(f"| {row['x']} | {row['count']:,} | {row['repeats']:,} | "
                     f"{pct(row['rate'])} | {note} |")
    return lines


def write_report(results, meta):
    names = list(results)
    lot = results["Loteka"]
    lines = [
        "# Pruebas de estrategias de apuesta en Chance Express",
        "",
        f"- Fuente: `{meta['source']}` (SHA-256 `{meta['sha'][:16]}…`, solo lectura)",
        (f"- Sorteos: {meta['draws']:,} · Días: {meta['days']} · "
        f"Entrenamiento: {meta['train_from']} → {meta['train_to']} · "
        f"Prueba ciega: {meta['test_from']} → {meta['test_to']}"),
        ("- Reglas: por cada peso, 70 si sale 1º, 8 si sale 2º, 4 si 3º, 2 si 4º, 1 si 5º. "
        "Bajo sorteos aleatorios con estos pagos desfavorables, el retorno esperado es 0,85 "
        "por peso (pérdida esperada del 15%); no es un juego justo."),
        (f"- Criterio: α = {ALPHA}, con corrección de Holm sobre todas las pruebas de cada dataset. "
        "❌ FALLA = rechazo estadístico de la hipótesis nula, no prueba de un patrón real; "
        "⚠️ SOSPECHOSA = p < 0,01 sin corregir, sin evidencia tras Holm."),
        ("- Controles: **sano** simula sorteos aleatorios (puede tener falsos positivos). **trampa** tiene "
        "4 patrones sembrados a propósito (permite comprobar sensibilidad a los patrones buscados)."),
        "",
        "## 1. Veredicto por idea",
        "",
        "| Idea | Pregunta | " + " | ".join(names) + " |",
        "|---|---|" + "---|" * len(names),
    ]
    for key in ("E1", "E2", "E3", "E4", "E5", "E6", "E8"):
        num, title, question = IDEAS[key]
        cells = " | ".join(idea_cell(results[n], key) for n in names)
        lines.append(f"| {num} {title} | {question} | {cells} |")
    rr = lot["repeat_rule"]
    lines.append(f"| #27 Regla de repetidos | {IDEAS['E7'][2]} | margen "
                 f"{100 * (1 - rr['real_all']):.2f}% si pagan todas las posiciones, "
                 f"{100 * (1 - rr['real_best']):.2f}% si solo la mejor | — | — |")
    lines += ["", *n_summary(lot)]
    lines += [
        "## 2. La plata: comparación con el retorno aleatorio esperado",
        "",
        ("El parámetro se eligió mirando solo el entrenamiento (el que más devolvió), y se mide en la "
        "prueba ciega, que la estrategia nunca vio. Retorno = pesos cobrados por peso apostado, con "
        "intervalo bootstrap de 95%. Referencia aleatoria bajo estos pagos = 0,85; superar "
        "esa referencia no implica rentabilidad (que exige retorno > 1)."),
        ("Los IC 95% de la grilla completa son descriptivos, sin ajuste simultáneo por comparar "
         "variantes; no son confirmación de estrategias seleccionadas después de ver los datos."),
        "",
        ("| Idea | Dataset | Parámetro elegido | Retorno entrenamiento | Retorno prueba ciega [IC 95%] "
        "| Apostado prueba ciega | Ganancia neta prueba ciega | Capital mínimo prueba ciega "
        "(escalera) | Comparación con 0,85 |"),
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    labels = {"E2": "#2 Fríos", "E3": "#6 Arrastre", "E4": "#12 Dobles",
              "E5": "#21 Tras N fallos (plana)", "E5 escalera": "#21 Tras N fallos (escalera)"}
    for key, label in labels.items():
        for n in names:
            m = results[n]["money"][key]
            held = m["held_out"] or {}
            train_ret = f"{m['train_ret']:.4f}" if "train_ret" in m else "igual que plana"
            bank = f"{held['min_bankroll']:,.0f}" if key == "E5 escalera" and held else "—"
            lines.append(f"| {label} | {n} | {m['pick']} | {train_ret} | {fmt_money(held)} | "
                         f"{held.get('stake', 0):,.0f} | {held.get('net', 0):+,.0f} | "
                         f"{bank} | {m['verdict']} |")
    healthy = results["sano (SHA-256)"]["money"]["E5"]["held_out"]
    lines += [
        "", ("**Control sano, E5 plana: criterio previsto INCUMPLIDO.** En prueba ciega, "
        f"su IC 95% [{healthy['lo']:.3f}–{healthy['hi']:.3f}] excluye 0,85 por debajo. "
        "No se ajustaron semilla, umbrales ni pruebas para ocultarlo."),
        "", ("**E2 frío en cualquier posición ≥200:** las apuestas en prueba ciega son escasas; "
        "un bootstrap por días con pocos eventos puede dar intervalos inestables o poco "
        "informativos. La ganancia observada no demuestra rentabilidad."),
        "", ("**Escalera:** capital mínimo = máximo de (apuesta del sorteo − saldo neto "
        "acumulado antes de apostar), para poder financiar cada apuesta; no es la peor caída "
        "del saldo ya liquidado. Las escaleras perdidas se cuentan tras fallar la décima apuesta, "
        "aunque cierre el día sin undécima apuesta. Si no se observan pérdidas raras de "
        "escalera, un retorno histórico aparente >1 no es una estimación fiable del futuro."),
        "", "## 3. Detalle de Loteka", "",
    ]
    lines += detail_tests(lot, ("E1", "E2", "E3", "E4", "E5"))
    lines += ["", "### Todas las variantes con plata (todos los datos)", "",
              ("| Idea | Variante | Apostado | Retorno [IC 95%] | Ganancia neta | Peor caída | "
              "Capital mínimo | Escaleras perdidas |"), "|---|---|---:|---:|---:|---:|---:|---:|"]
    for key, label in labels.items():
        for row in lot["money"][key]["grid"]:
            lost = row.get("lost_ladders", "")
            lines.append(f"| {label} | {row['label']} | {row.get('stake', 0):,.0f} | "
                         f"{fmt_money(row)} | {row.get('net', 0):+,.0f} | "
                         f"{row.get('max_drawdown', 0):,.0f} | "
                         f"{row.get('min_bankroll', 0):,.0f} | {lost} |")
    lines += ["", "### #26 Apuesta audaz vs tímida (llegar a la meta)", "",
              ("Audaz = apostar a un número lo justo para llegar a la meta si sale 1º. Tímida = 10 "
              "pesos por sorteo. Sesiones reales una detrás de otra, sin compartir sorteos."), "",
              ("| Meta | Estilo | Datos reales [IC 95%] | Sesiones | "
               "Sorteos aleatorios con estos pagos [IC 95%] | Sorteos por sesión (mediana) | "
               "Si los pagos fueran justos |"),
              "|---|---|---:|---:|---:|---:|---:|"]
    for s in lot["sessions"]:
        lo, hi = s["real_ci"]
        mlo, mhi = s["mc_ci"]
        lines.append(f"| {s['bank']:,} → {s['goal']:,} | {s['style']} | {pct(s['real_rate'])} "
                     f"[{pct(lo)}–{pct(hi)}] | {s['real_n']:,} | {pct(s['mc_rate'])} "
                     f"[{pct(mlo)}–{pct(mhi)}] | {s['mc_steps']:.0f} | {pct(s['fair'])} |")
    lines += detail_tests(lot, ("E6",), header=False)
    lines += ["", "### #27 Regla de números repetidos", "",
              "| | Teórico | Real (tus datos) |", "|---|---:|---:|",
              f"| Retorno si pagan todas las posiciones | {rr['theory_all']:.4f} | {rr['real_all']:.4f} |",
              f"| Retorno si pagan solo la mejor | {rr['theory_best']:.4f} | {rr['real_best']:.4f} |",
              (f"| Sorteos con algún número repetido | {pct(rr['theory_draws_with_repeat'])} | "
              f"{pct(rr['draws_with_repeat'])} |"),
              "", "### #29 Cambio de fuente", ""]
    for src, info in lot["sources"].items():
        lines.append(f"- `{src}`: {info['draws']:,} sorteos, {info['first_day']} → {info['last_day']}")
    e8 = [t for t in lot["tests"] if t["id"].startswith("E8 ")]
    valid_e8 = [t for t in e8 if t["p"] is not None]
    na_e8 = [t for t in e8 if t["p"] is None]
    sparse_e8 = [t for t in na_e8 if t.get("n") == 0]
    lines += ["", (f"Se intentaron {len(e8)} filas: distribución por globo, tasa de repetidos, las "
              "52 pruebas de la auditoría RNG y E1–E4, cada una por separado en cada fuente."), ""]
    lines += detail_tests(lot, ("E8 globo", "E8 repetidos"), header=False)
    lines += ["", (f"E8: {len(e8)} filas intentadas, {len(valid_e8)} con p válido; "
               f"{len(na_e8)} N/A ({len(na_e8) - len(sparse_e8)} tablas 100×100 "
               f"con conteos esperados <5/celda, {len(sparse_e8)} sin casos):")]
    lines += [f"- {t['id']}: N/A — {t['detail'] or 'sin casos'}" for t in na_e8]
    odd = [t for t in valid_e8 if t["p"] < ALPHA]
    lines += ["", (f"Pruebas válidas de E8 con p < 0,01 sin corregir: {len(odd)} de {len(valid_e8)} "
              f"(por azar se esperan ~{len(valid_e8) * ALPHA:.1f}). "
              f"Rechazos después de Holm: {sum(t['verdict'] == 'FALLA' for t in valid_e8)}.")]
    lines += [f"- {t['id']}: "
              + (f"observado {t['observed']:.4f}, " if t.get('observed') is not None else "")
              + f"p {fmt_p(t['p'])}, p Holm {fmt_p(t['p_holm'])}" for t in odd]
    lines += controls_section(results)
    lines += ["", *e9_section(lot["e9"])]
    lines += [
        "", "## 5. Limitaciones", "",
        ("- Las reglas no dicen cómo se paga un número que sale en 2 posiciones. La plata se calculó "
        "pagando todas las posiciones; #27 muestra cuánto cambia con la otra lectura. Solo Loteka "
        "puede confirmarlo."),
        ("- #26: las sesiones se juegan una detrás de otra (no una por día, como decía el plan) para "
        "que no compartan sorteos y la prueba sea válida. Con 5.000 → 10.000 en modo tímido hay "
        "pocas sesiones, así que esa fila tiene poca precisión."),
        ("- El corte entrenamiento/prueba ciega cae antes del cambio de fuente (2026-04-25), así que la "
        "prueba ciega mezcla las dos fuentes. E8 compara directamente las distribuciones 2×100 y la "
        "tasa de repetidos; las pruebas dentro de cada fuente no prueban equivalencia entre fuentes. "
        "Los períodos son disjuntos: no detectar diferencias no implica mismo RNG ni equivalencia."),
        ("- En el control trampa, los patrones sembrados también mueven un poco otras pruebas (por "
        "ejemplo, meter números fríos en el 1º toca el arrastre). Es esperable: esos datos no son "
        "aleatorios."),
        ("- E4 usa inferencia bilateral robusta por día sobre aciertos menos aciertos esperados "
        "(1% para 1º; 1−0,99⁵ para cualquier posición), no binomial de ventanas solapadas. "
        "Supone independencia entre días; Holm no corrige dependencia dentro del día."),
        ("- Los intervalos de plata usan bootstrap por días (2.000 remuestreos), que agrupa "
        "sorteos del mismo día pero supone independencia entre días; con eventos escasos, "
        "como E2 ≥200 en cualquier posición, pueden ser poco fiables."),
    ]
    (REPORT_DIR / "strategy_tests.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def detail_tests(result, prefixes, header=True):
    rows = [t for t in result["tests"]
            if any(t["id"].startswith(p + " ") or t["id"] == p for p in prefixes)
            ]
    lines = ["| ID | Pregunta | Observado | Esperado | Casos | p | p Holm | Veredicto |",
             "|---|---|---:|---:|---:|---:|---:|---|"] if header or rows else []
    if not header:
        lines = ["", *lines]
    for t in rows:
        obs = "—" if t["observed"] is None or t["expected"] is None else f"{t['observed']:.4f}"
        exp = "—" if t["expected"] is None else f"{t['expected']:.4f}"
        p = fmt_p(t["p"]) if t["p"] is not None else "N/A"
        adjusted = fmt_p(t["p_holm"]) if t["p"] is not None else "N/A"
        verdict = f"{ICON[t['verdict']]} {t['verdict']}" if t["p"] is not None else "N/A (sin casos)"
        lines.append(f"| {t['id']} | {t['name']} | {obs} | {exp} | {t['n']:,} | {p} | "
                     f"{adjusted} | {verdict} |")
    return lines


def controls_section(results):
    planted = (("Tras ≥5 impares en el 1º, par 65%", "E1 par-g1 N=5"),
               ("Tras ≥5 impares en el 1º, par 65%", "E5 par/impar N≥5"),
               ("El 2º pasa al 1º del siguiente (5%)", "E3 2º→1º"),
               ("Un doble sale 1º en el siguiente (5%)", "E4 1º w=1"),
               ("Frío ≥300 sorteos sale 1º con 3%", "E2 1º X=300"))
    names = list(results)
    lines = ["", "## 4. Controles: sensibilidad a patrones sembrados (no validación universal)", "",
             "| Patrón sembrado en *trampa* | Prueba | " + " | ".join(names) + " |",
             "|---|---|" + "---|" * len(names)]
    for label, test_id in planted:
        cells = []
        for n in names:
            t = next(x for x in results[n]["tests"] if x["id"] == test_id)
            cells.append(f"{ICON[t['verdict']]} obs {t['observed']:.4f} (esp {t['expected']:.4f}), "
                         f"Holm {fmt_p(t['p_holm'])}")
        lines.append(f"| {label} | {test_id} | " + " | ".join(cells) + " |")
    return lines


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "chance_express_history.json"
    try:
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc
    d, source = load_draws(path), load_sources(path)
    days = np.unique(d.day)
    cut = days[int(len(days) * TRAIN_SHARE)]
    train = d.day < cut
    datasets = {"Loteka": d, **{name: make(d) for name, make in CONTROLS.items()}}
    results = {}
    for name, data in datasets.items():
        start = time.time()
        results[name] = run_dataset(data, source, train)
        print(f"{name:32} listo en {time.time() - start:6.1f}s")
    results["Loteka"]["e9"] = ex.e9_next_first(d)
    meta = {"source": path.name, "sha": sha, "draws": len(d.nums), "days": len(days),
            "train_from": date.fromordinal(int(days[0])).isoformat(),
            "train_to": date.fromordinal(int(days[days < cut][-1])).isoformat(),
            "test_from": date.fromordinal(int(cut)).isoformat(),
            "test_to": date.fromordinal(int(days[-1])).isoformat()}
    REPORT_DIR.mkdir(exist_ok=True)
    write_report(results, meta)
    (REPORT_DIR / "strategy_tests.json").write_text(
        json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=1,
                   default=lambda o: o.item() if hasattr(o, "item") else str(o)),
        encoding="utf-8")
    print(f"Reporte: {REPORT_DIR / 'strategy_tests.md'}")


if __name__ == "__main__":
    main()
