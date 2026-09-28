"""Counterfactual Quiniela 80/8/4/2/1 on Chance Express, without modifying prior reports.

Usage: py -B -m strategy_tests.run_quiniela80
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
from strategy_tests.rules import (
    LADDER,
    QUINIELA80,
    expected_return,
    first_prize_ladder,
    ladder_table,
    payout_matrix,
)
from strategy_tests.run_experiments import (
    IDEAS,
    ROOT,
    TRAIN_SHARE,
    controls_section,
    detail_tests,
    idea_cell,
    load_sources,
    pct,
)

VIEWS = ("first", "all", "best")
REPORT_DIR = ROOT / "reports"
REPORT_STEM = "strategy_tests_quiniela80"
SEED = 7
FIRST_LADDER = first_prize_ladder(QUINIELA80)


def metadata(source, sha, draws, days, train_days, train_to, heldout_from, train_draws):
    return {
        "scenario": "hypothetical payout on Chance Express; not Rapidita observations",
        "source": source, "sha": sha, "draws": draws, "days": days,
        "prizes": list(QUINIELA80.prizes), "principal_mode": "all",
        "sensitivity_mode": "best", "first_position": "first prize only",
        "selector": "training first-position return only; total-return pick is sensitivity",
        "split": {"train_fraction": TRAIN_SHARE, "train_days": train_days,
                  "heldout_days": days - train_days, "train_draws": train_draws,
                  "heldout_draws": draws - train_draws, "train_to": train_to,
                  "heldout_from": heldout_from},
        "bootstrap": {"repetitions": ex.BOOTSTRAP_REPS, "seed": SEED, "unit": "day"},
        "reference": {"first": QUINIELA80.prizes[0] / 100,
                      "all": expected_return("all", QUINIELA80),
                      "best": expected_return("best", QUINIELA80)},
        "e6_mc_sessions": ex.MC_SESSIONS,
        "ladder": {"original70_unchanged": list(LADDER), "precomputed80": list(FIRST_LADDER),
                   "numbers_per_round": 50, "target_first_win_net": 10,
                   "original70_ten_misses": ladder_cost(LADDER),
                   "precomputed80_ten_misses": ladder_cost(FIRST_LADDER)},
    }


def ladder_cost(ladder):
    return 50 * sum(ladder)


def _money(day, stake, paid, rng, per_number=None, first_paid=None):
    result = ex.money(day, stake, paid, rng)
    if result is None:
        return None
    # Flat wagers are one peso per selected number. A ladder covers 50 numbers
    # with an equal per-number stake, so count raw first hits without weighting.
    units = stake if per_number is None else np.divide(
        stake, per_number, out=np.zeros_like(stake, dtype=float), where=per_number != 0)
    first_paid = paid if first_paid is None else first_paid
    first_hits = (first_paid / (QUINIELA80.prizes[0] if per_number is None else
                                QUINIELA80.prizes[0] * np.where(per_number != 0, per_number, 1))).sum()
    result.update({"paid": result["net"] + result["stake"],
                   "first_hits": round(first_hits),
                   "opportunities": int(np.count_nonzero(stake)),
                   "stake_units": float(units.sum()),
                   "expected_first_hits": float(units.sum() / 100)})
    return result


def evaluate_views(d, views, train, rng):
    """Select by training first return, never by the held-out outcomes or best mode."""
    if set(views) != set(VIEWS) or any(len(views[v]) != len(views["first"]) for v in VIEWS):
        raise ValueError("candidate labels/stakes must match across views")
    for rows in zip(*(views[v] for v in VIEWS), strict=True):
        if len({row[0] for row in rows}) != 1 or any(
                not np.array_equal(row[1], rows[0][1]) for row in rows[1:]):
            raise ValueError("candidate labels/stakes must match across views")
    train = np.asarray(train, dtype=bool)
    test = ~train
    grid, train_first, train_all = [], [], []
    for row in zip(*(views[v] for v in VIEWS), strict=True):
        by_view = dict(zip(VIEWS, row, strict=True))
        label = row[0][0]
        stake = row[0][1]
        first_ret = (float(by_view["first"][2][train].sum() / stake[train].sum())
                     if stake[train].sum() else None)
        all_ret = (float(by_view["all"][2][train].sum() / stake[train].sum())
                   if stake[train].sum() else None)
        train_first.append(first_ret)
        train_all.append(all_ret)
        grid.append({"label": label, "train_ret_first": first_ret, "train_ret_all": all_ret,
                     "full_data": {v: _money(d.day, by_view[v][1], by_view[v][2], rng,
                                              first_paid=by_view["first"][2]) for v in VIEWS},
                     "held_out": {v: _money(d.day[test], by_view[v][1][test],
                                            by_view[v][2][test], rng,
                                            first_paid=by_view["first"][2][test]) for v in VIEWS}})
    pick = int(np.argmax([x if x is not None else -np.inf for x in train_first])) if grid else None
    alt = int(np.argmax([x if x is not None else -np.inf for x in train_all])) if any(
        x is not None for x in train_all) else None
    if pick is not None and train_first[pick] is None:
        pick = None
    return {"grid": grid, "pick": grid[pick]["label"] if pick is not None else None,
            "train_ret_first": train_first[pick] if pick is not None else None,
            "held_out": grid[pick]["held_out"] if pick is not None else dict.fromkeys(VIEWS),
            "sensitivity_total_pick": grid[alt]["label"] if alt is not None else None,
            "sensitivity_total_train_ret": train_all[alt] if alt is not None else None,
            "sensitivity_total_held_out": grid[alt]["held_out"] if alt is not None else
            dict.fromkeys(VIEWS)}


def _ladder_losses(d, train, label, ladder):
    hname, threshold = label.split(" tras ≥")
    bet_t, target, rnd, series = ex._streak_bets(d, ex.HALVES[hname], int(threshold))
    missed = (rnd == len(ladder) - 1) & (series[bet_t] != target)
    return {"full_data": int(missed.sum()), "held_out": int(np.count_nonzero(missed & ~train[bet_t]))}


def evaluate_ladders(d, pay, train, pick, rng):
    """Keep the flat first-position choice for every ladder and payout mode."""
    result = {}
    for name, ladder in (("original70_unchanged", LADDER), ("precomputed80", FIRST_LADDER)):
        candidate_views = {}
        for view in VIEWS:
            _, _, ladders = ex.e5_streak_entry(d, pay[view], ladder=ladder, profile=QUINIELA80)
            candidate_views[view] = ladders
        rows = []
        for label in candidate_views["first"]:
            same_stake = candidate_views["first"][label][0]
            if any(not np.array_equal(candidate_views[v][label][0], same_stake) for v in VIEWS):
                raise ValueError("ladder labels/stakes differ across modes")
            # The active per-number stake varies by round; zeros are excluded.
            per_number = same_stake / 50
            losses = _ladder_losses(d, train, label, ladder)
            metrics = {}
            for scope, mask in (("full_data", np.ones(len(train), dtype=bool)),
                                ("held_out", ~train)):
                metrics[scope] = {
                    v: _money(d.day[mask], same_stake[mask], candidate_views[v][label][1][mask],
                              rng, per_number[mask], candidate_views["first"][label][1][mask])
                    for v in VIEWS}
                metrics[scope]["complete_losses"] = losses[scope]
            rows.append({"label": label, **metrics})
        chosen = next((r for r in rows if r["label"] == pick), None)
        result[name] = {"ladder": list(ladder), "ten_miss_cost": ladder_cost(ladder),
                        "first_win_table": ladder_table(ladder, profile=QUINIELA80),
                        "pick": pick, "grid": rows, "held_out": chosen["held_out"] if chosen else None,
                        "full_data": chosen["full_data"] if chosen else None}
    return result


def run_dataset(d, source, train):
    rng = np.random.default_rng(SEED)
    pay = {"first": ex.first_position_matrix(d.nums, QUINIELA80),
           "all": payout_matrix(d.nums, "all", QUINIELA80),
           "best": payout_matrix(d.nums, "best", QUINIELA80)}
    e1, _ = ex.e1_halves(d)
    candidates, tests = {}, list(e1)
    for key, experiment in (("E2", ex.e2_cold), ("E3", ex.e3_carry),
                            ("E4", ex.e4_doubles)):
        candidates[key] = {}
        for view in VIEWS:
            found, rows = experiment(d, pay[view])
            candidates[key][view] = rows
            if view == "first":
                tests.extend(found)
    candidates["E5"] = {}
    for view in VIEWS:
        found, rows, _ = ex.e5_streak_entry(d, pay[view], ladder=LADDER, profile=QUINIELA80)
        candidates["E5"][view] = rows
        if view == "first":
            tests.extend(found)
    money = {key: evaluate_views(d, candidates[key], train, rng) for key in candidates}
    money["E5_ladders"] = evaluate_ladders(d, pay, train, money["E5"]["pick"], rng)
    sessions = {}
    for mode in ("all", "best"):
        found, sessions[mode] = ex.e6_bold(d, pay[mode], profile=QUINIELA80, mode=mode)
        tests.extend(dict(t, id=f"{t['id']} {mode}", name=f"{t['name']} ({mode})") for t in found)
    e8, per_source = ex.e8_sources(d, source, profile=QUINIELA80)
    tests.extend(e8)
    tested = [t for t in tests if t["p"] is not None]
    for t, h in zip(tested, holm(np.array([t["p"] for t in tested])), strict=True):
        t["p_holm"] = float(h)
        t["verdict"] = "FALLA" if h < ALPHA else ("SOSPECHOSA" if t["p"] < ALPHA else "PASA")
    return {"tests": tests, "money": money, "sessions": sessions,
            "repeat_rule": ex.e7_repeat_rule(d, pay["all"], pay["best"], profile=QUINIELA80),
            "sources": {k: {**v, "first_day": date.fromordinal(v["first_day"]).isoformat(),
                            "last_day": date.fromordinal(v["last_day"]).isoformat()}
                        for k, v in per_source.items()}}


def _fmt(m):
    if m is None:
        return "N/A (sin apuestas)"
    return (f"{m['ret']:.4f} [{m['lo']:.3f}–{m['hi']:.3f}]; "
            f"RD${m['stake']:,.0f} / {m['paid']:,.0f} / {m['net']:+,.0f}; "
            f"{m['first_hits']:,} aciertos 1.º; {m['opportunities']:,} sorteos; "
            f"{m['stake_units']:,.0f} unidades; capital {m['min_bankroll']:,.0f}; "
            f"caída {m['max_drawdown']:,.0f}")


def _row(label, m):
    return f"| {label} | " + " | ".join(_fmt(m.get(v)) for v in VIEWS) + " |"


def _money_section(lines, result):
    money = result["money"]
    lines += ["## Retornos y apuestas — Chance Express", "",
              ("Cada celda: retorno [IC 95%]; RD$ apostado / cobrado / neto; aciertos crudos al "
              "1.º; sorteos con apuesta; unidades-número apostadas; capital mínimo; caída máxima. "
              "Los aciertos crudos NO son tasas ponderadas por stake. Una apuesta a 50 números "
              "tiene cobertura 50%, no 1%; referencia de 1% es por número-unidad. "
              "El retorno de primera posición tiene referencia 0,80; total all 0,95; best "
              "0,9474159401. Rentabilidad neta requiere retorno >1."), "",
              "| Selección por retorno 1.º en entrenamiento | Solo 1.º | Total all | Total best |",
              "|---|---|---|---|"]
    for key in ("E2", "E3", "E4", "E5"):
        item = money[key]
        lines.append(_row(f"{key} {item['pick']} (entrenamiento 1.º "
                          f"{item['train_ret_first'] if item['train_ret_first'] is not None else 'N/A'})",
                          item["held_out"]))
    lines += ["", "### Grilla monetaria completa (sin escoger por prueba ciega)", "",
              "| Idea y candidato | Solo 1.º: prueba ciega | All: prueba ciega | Best: prueba ciega |",
              "|---|---|---|---|"]
    for key in ("E2", "E3", "E4", "E5"):
        for row in money[key]["grid"]:
            lines.append(_row(f"{key} {row['label']} (train 1.º {row['train_ret_first']}, "
                              f"train total {row['train_ret_all']})", row["held_out"]))
    lines += ["", ("La selección alternativa por retorno total all en entrenamiento es "
              "solo sensibilidad, no segunda prueba confirmatoria:"), "",
              "| Idea | Elección alternativa | Solo 1.º: prueba ciega | Total all: prueba ciega | Total best: prueba ciega |",
              "|---|---|---|---|---|"]
    for key in ("E2", "E3", "E4", "E5"):
        item = money[key]
        lines.append(_row(f"{key}: {item['sensitivity_total_pick']} "
                          f"(train all {item['sensitivity_total_train_ret']})",
                          item["sensitivity_total_held_out"]))
    lines += ["", "### E5: ambas escaleras, mismo N seleccionado por apuesta plana al 1.º", "",
              ("La escalera original de premio 70 NO fue optimizada para 80. La nueva se "
              "calculó antes de ver resultados: mínimo entero por número para recuperar lo "
              "invertido más RD$10 con un único acierto 1.º. Los 50 números cuestan "
              "50 × apuesta por ronda. Pérdida completa = fallo al 1.º en la décima apuesta; "
              "puede haber pagos menores sin evitar ese evento. El costo de diez rondas "
              "perdidas es determinista. Ausencia de pérdidas raras en prueba ciega NO permite "
              "al bootstrap inventar colas no observadas."), ""]
    for name, ladder in money["E5_ladders"].items():
        lines += [(f"**{name}**: secuencia {ladder['ladder']}; diez fallos: "
                  f"RD${ladder['ten_miss_cost']:,}; inversión acumulada y neto al "
                  f"acertar 1.º por ronda: {ladder['first_win_table']}."), "",
                  "| N y variante | Pérdidas completas (todos / prueba) | Solo 1.º prueba | All prueba | Best prueba |",
                  "|---|---:|---|---|---|"]
        for row in ladder["grid"]:
            lines.append(f"| {row['label']} | {row['full_data']['complete_losses']} / "
                         f"{row['held_out']['complete_losses']} | "
                         + " | ".join(_fmt(row["held_out"][v]) for v in VIEWS) + " |")
        selected = next((r for r in ladder["grid"] if r["label"] == ladder["pick"]), None)
        if selected is not None:
            lines += ["", ("Candidato seleccionado: métricas de **todos los datos** "
                       "(NO de prueba ciega):"), "",
                      "| Variante | Solo 1.º: todos | All: todos | Best: todos |",
                      "|---|---|---|---|"]
            lines.append(_row(selected["label"], selected["full_data"]))
        lines.append("")


def _report(results, meta):
    real = results["Chance Express"]
    lines = ["# Quiniela Extraordinaria 80 sobre Chance Express: simulación contrafactual", "",
             ("**No son sorteos observados de Rapidita ni validación de sus reglas.** "
             "Pagos hipotéticos RD$80/8/4/2/1 por peso y número en posiciones 1.ª–5.ª. "
             "All suma coincidencias repetidas (principal); best paga solo la mejor "
             "(sensibilidad no confirmada por reglas oficiales). No palé ni tripleta."), "",
             (f"Fuente `{meta['source']}` SHA-256 `{meta['sha']}`; "
             f"{meta['draws']:,} sorteos, {meta['days']} días. "
             f"Corte 60/40: hasta {meta['split']['train_to']} entrenamiento "
             f"({meta['split']['train_days']} días, {meta['split']['train_draws']:,} sorteos), "
             f"desde {meta['split']['heldout_from']} prueba ciega "
             f"({meta['split']['heldout_days']} días, {meta['split']['heldout_draws']:,} sorteos). "
             "Bootstrap por día 2.000 repeticiones, semilla 7. E6: 20.000 sesiones MC "
             "por combinación, sesiones reales consecutivas no solapadas."), "",
             "## Conclusiones y supuestos", "",
             ("- Prioridad: retorno de solo primera posición vs **0,80**; total quiniela "
             "all vs **0,95** y best vs **0,9474159401**. Son referencias de azar "
             "uniforme independiente; beneficio exige **retorno >1** con incertidumbre, "
             "no solo superar azar. Un retorno histórico >1 no garantiza ventaja futura."),
             ("- E2–E5: se elige candidato por retorno al 1.º solo en entrenamiento; el "
             "mismo candidato y las mismas apuestas se evalúan en las tres vistas de "
             "prueba ciega. La elección alternativa por total all es sensibilidad."),
             ("- p crudos de E1–E5 y E8 no dependen del premio; E6 sí cambia por "
             "pagos/objetivo y modo. Holm se recalcula sobre la familia completa, "
             "incluidas E6 all/best; sus p ajustados pueden variar aunque el p crudo "
             "de otras pruebas sea idéntico. α=0,01; N/A se conserva."), "",
             "## Ocho ideas: pruebas de probabilidad", "",
             "| Idea | Pregunta | Chance Express | Sano | Trampa |",
             "|---|---|---|---|---|"]
    for key in ("E1", "E2", "E3", "E4", "E5", "E6", "E8"):
        num, title, question = IDEAS[key]
        if key == "E6":
            question = "¿Cómo se comparan sesiones reales no solapadas con MC uniforme del mismo pago/modo?"
        lines.append(f"| {num} {title} | {question} | " + " | ".join(
            idea_cell(results[n], key) for n in results) + " |")
    rr = real["repeat_rule"]
    lines.append("| #27 E7 Repetidos | retornos all / best; teórico "
                 f"{rr['theory_all']:.4f} / {rr['theory_best']:.4f} | "
                 + " | ".join(f"{results[n]['repeat_rule']['real_all']:.4f} / "
                              f"{results[n]['repeat_rule']['real_best']:.4f}"
                              for n in results) + " |")
    chosen = real["money"]
    observed = [(key, chosen[key]["held_out"]) for key in ("E2", "E3", "E4", "E5")]
    summary = "; ".join(
        f"{key}: 1.º {views['first']['ret']:.4f}, all {views['all']['ret']:.4f}, "
        f"neto all RD${views['all']['net']:+,.0f}" if views["first"] and views["all"]
        else f"{key}: sin apuestas" for key, views in observed)
    losses = sum(views["all"] is not None and views["all"]["net"] < 0
                 for _, views in observed)
    lines += ["", (f"**Resultado económico principal en prueba ciega:** {summary}. "
               f"{losses}/4 selecciones planas pierden dinero en all; el IC de una "
               "muestra escasa puede ser especialmente inestable."), "",
        "### Grilla E1 y E5: todos los N y variantes", "",
              "| Prueba | Casos | Observado | Esperado | p | p Holm |",
              "|---|---:|---:|---:|---:|---:|"]
    for t in real["tests"]:
        if t["id"].startswith(("E1 ", "E5 ")):
            lines.append(f"| {t['id']} | {t['n']:,} | {pct(t['observed'])} | "
                         f"{pct(t['expected'])} | {fmt_p(t['p']) if t['p'] is not None else 'N/A'} | "
                         f"{fmt_p(t['p_holm']) if t['p'] is not None else 'N/A'} |")
    lines += [""]
    _money_section(lines, real)
    lines += ["## E6: alcanzar meta (NO pronóstico)", "",
              ("El límite banco/meta solo corresponde al caso hipotético de juego justo; "
              "con pagos 80/8/4/2/1 hay margen. MC uniforme usa el mismo perfil y "
              "modo all/best que la serie real. IC Wilson 95%."), "",
              "| Modo | Capital → meta | Estilo | Real [IC], sesiones | MC [IC], mediana sorteos | Cota justa |",
              "|---|---|---|---|---|---:|"]
    for mode, rows in real["sessions"].items():
        for s in rows:
            lines.append(f"| {mode} | {s['bank']:,} → {s['goal']:,} | {s['style']} | "
                         f"{pct(s['real_rate'])} [{pct(s['real_ci'][0])}–{pct(s['real_ci'][1])}], "
                         f"n={s['real_n']} | {pct(s['mc_rate'])} "
                         f"[{pct(s['mc_ci'][0])}–{pct(s['mc_ci'][1])}], "
                         f"mediana {s['mc_steps']:.0f} | {pct(s['fair'])} |")
    lines += ["", "## E7 y E8", "", "| Repetidos | Teórico | Observado |",
              "|---|---:|---:|",
              f"| All | {rr['theory_all']:.10f} | {rr['real_all']:.4f} |",
              f"| Best | {rr['theory_best']:.10f} | {rr['real_best']:.4f} |",
              (f"| Sorteos con repetidos | {pct(rr['theory_draws_with_repeat'])} | "
              f"{pct(rr['draws_with_repeat'])} |"), ""]
    for src, info in real["sources"].items():
        lines.append(f"- E8 `{src}`: {info['draws']:,} sorteos, "
                     f"{info['first_day']} a {info['last_day']} (períodos disjuntos).")
    e8 = [t for t in real["tests"] if t["id"].startswith("E8 ")]
    na = [t for t in e8 if t["p"] is None]
    lines += [(f"E8: {len(e8)} filas, {len(na)} N/A (celdas dispersas o sin casos); "
              "no detectar diferencia NO prueba equivalencia. Comparación directa de "
              "globos y repetidos:"), ""]
    lines += detail_tests(real, ("E8 globo", "E8 repetidos"))
    lines += ["", *[f"- {t['id']}: N/A — {t.get('detail') or 'sin casos'}" for t in na], "",
              "## Controles y límites", ""]
    for name in ("sano (SHA-256)", "trampa (4 patrones sembrados)"):
        result = results[name]
        lines.append(f"**{name}**: " + "; ".join(idea_cell(result, key)
                     for key in ("E1", "E2", "E3", "E4", "E5", "E6", "E8")))
        for key in ("E2", "E3", "E4", "E5"):
            held = result["money"][key]["held_out"]
            for view, ref in meta["reference"].items():
                m = held[view]
                if m is not None:
                    covers = m["lo"] <= ref <= m["hi"]
                    lines.append(f"- {key} {view} {result['money'][key]['pick']}: "
                                 f"IC [{m['lo']:.6f}, {m['hi']:.6f}] "
                                 f"{'cubre' if covers else 'NO cubre'} {ref:.10f}; "
                                 f"{m['opportunities']} sorteos, {m['stake_units']:,.0f} "
                                 f"unidades, {m['first_hits']} aciertos 1.º.")
        lines.append("")
    lines += controls_section(results)
    lines += [("Los cuatro defectos sembrados (racha, arrastre, doble, frío) sirven para "
              "sensibilidad, no certifican ausencia de otros defectos. El criterio sano E5 "
              "original quedó **NO APROBADO**; el piloto 19/20 sobre 0,85 y STR-13 "
              "siguen históricos, NO se trasladan al premio 80. No se ajustaron semillas "
              "para hacer cubrir IC."), "",
              ("E4 usa ventanas solapadas e inferencia agrupada por día; Holm no elimina "
              "dependencia intradía. E8 compara fuentes de épocas distintas, con tablas "
              "100×100 dispersas N/A. IC bootstrap por día asume días independientes, "
              "no ajusta simultáneamente grillas y puede ser poco informativo para "
              "apuestas escasas. La selección post hoc de cualquier fila no confirma "
              "predicción; cambios futuros y pérdidas raras no observadas quedan fuera "
              "del bootstrap."), "",
              "## E9: transición descriptiva tras X (00–99)", "",
              ("Solo pares consecutivos del mismo día en Chance Express; matriz "
              "100×100 íntegra en JSON. No hay elección ni p por X, ni predicción."), "",
              "| X | Casos | Repeticiones | Tasa |", "|---|---:|---:|---:|"]
    for row in real["e9"]["rows"]:
        lines.append(f"| {row['x']} | {row['count']:,} | {row['repeats']:,} | "
                     f"{pct(row['rate'])} |")
    return "\n".join(lines) + "\n"


def write_outputs(results, meta, directory=REPORT_DIR):
    directory.mkdir(exist_ok=True)
    (directory / f"{REPORT_STEM}.md").write_text(_report(results, meta), encoding="utf-8")
    (directory / f"{REPORT_STEM}.json").write_text(
        json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=1,
                   default=lambda o: o.item() if hasattr(o, "item") else str(o)),
        encoding="utf-8")


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
    datasets = {"Chance Express": d, **{name: make(d) for name, make in CONTROLS.items()}}
    results = {}
    for name, data in datasets.items():
        start = time.time()
        results[name] = run_dataset(data, source, train)
        print(f"{name:32} listo en {time.time() - start:6.1f}s", flush=True)
    results["Chance Express"]["e9"] = ex.e9_next_first(d)
    meta = metadata(path.name, sha, len(d.nums), len(days), int(np.count_nonzero(days < cut)),
                    date.fromordinal(int(days[days < cut][-1])).isoformat(),
                    date.fromordinal(int(cut)).isoformat(), int(np.count_nonzero(train)))
    write_outputs(results, meta)
    print(f"Reportes: {REPORT_DIR / (REPORT_STEM + '.md')} / {REPORT_STEM}.json")


if __name__ == "__main__":
    main()
