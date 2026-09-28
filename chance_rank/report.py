"""Spanish retrospective report built solely from persisted JSON evidence."""
import json
from pathlib import Path

from chance_rank import protocol


def _load(root, name):
    path = root / name
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Artefacto JSON ilegible: {name}") from exc


def _fmt(value):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _table(rows):
    return "\n".join("| " + " | ".join(_fmt(x).replace("|", "\\|") for x in row) + " |" for row in rows)


def build_report(run_dir):
    """Write resumen.md without reading history, store, or prediction/result artifacts."""
    root = Path(run_dir)
    metrics = _load(root, "metrics.json")
    frozen = _load(root, "protocol.json")
    status = _load(root, "status.json")
    primary = metrics.get("primary") or {}
    secondary = metrics.get("secondary") or {}
    targets = secondary.get("targets") or {}
    systems = primary.get("systems") or {}
    state = status.get("state", "incompleto" if not metrics else "N/A")
    pending = "supervisada pendiente" if any(not systems.get(s, {}).get("available") for s in protocol.SUPERVISED_FAMILIES) else "N/A"
    lines = ["# Chance Express — resumen retrospectivo/exploratorio", "",
             ("Este estudio retrospectivo y exploratorio no constituye confirmación prospectiva. "
              "N/A significa evidencia ausente, no éxito ni ausencia de efecto."), ""]

    def section(n, title, content):
        lines.extend([f"## {n}. {title}", "", content or "N/A", ""])

    section(1, "Pregunta principal y criterio", "Primer puesto, Top-25, H1 actualizado, predecesor observado a cinco minutos. "
            "Mejora ≥1 punto porcentual frente a uniforme y reciente500, Holm <0,01 en ambos, "
            "positiva en ≥70% de folds con ≥500 oportunidades. No se infiere equivalencia del no rechazo.")
    section(2, "Estado e integridad", f"Ejecución: {_fmt(state)}; motivo: {_fmt(status.get('reason'))}; "
            f"métricas: {_fmt(metrics.get('status'))}; {pending}. Protocolo: {_fmt((frozen.get('protocol') or {}).get('protocol_id'))}; "
            f"hash: {_fmt(frozen.get('protocol_hash'))}; SHA de datos: {_fmt(metrics.get('data_sha'))}.")
    rows: list[tuple[object, ...]] = [("Sistema", "Disponible", "Δ uniforme", "p Holm", "Δ reciente500", "p Holm", "Clasificación")]
    rows.append(("---",) * 7)
    for system in (*protocol.INTERPRETABLE_FAMILIES, *protocol.SUPERVISED_FAMILIES, *protocol.SELECTORS):
        entry = systems.get(system) or {}
        uniform, recent = entry.get("uniform") or {}, entry.get("recent500") or {}
        rows.append((system, "sí" if entry.get("available") else "N/A", uniform.get("delta"),
                     uniform.get("p_adj"), recent.get("delta"), recent.get("p_adj"),
                     (entry.get("classification") or {}).get("label")))
    section(3, "Contrastes predeclarados (16 sistemas × 2 referencias)", _table(rows) +
            "\n\nCasillas indisponibles permanecen en la familia Holm conservadora, no se aprueban.")
    section(4, "Cobertura y K", f"Objetivos primarios: {_fmt(primary.get('n_primary_targets'))}. "
            f"K={_fmt((frozen.get('protocol') or {}).get('k_values'))}. Tasas por objetivo/sistema: "
            f"{_fmt({k: v.get('topk') for k, v in targets.items()})}.")
    section(5, "Horizontes y listas", _fmt({k: v.get("horizon") for k, v in targets.items()}) +
            "\n\nPoblaciones de bloques completos y descartes se informan por separado; no se equiparan coberturas.")
    section(6, "Puestos y cualquier puesto", "Las cinco posiciones y 'any' no comparten denominador implícito: "
            + _fmt({k: v.get("topk") for k, v in targets.items()}))
    section(7, "Referencias", _fmt({k: v.get("baselines") for k, v in targets.items()}) +
            "\n\nUniforme K/100 es analítica; más cobertura no implica mejor selección.")
    section(8, "Esperas y supervivencia", _fmt({k: v.get("waits") for k, v in targets.items()}) +
            "\n\nLas esperas inconclusas se censuran al fin del segmento.")
    section(9, "Probabilidades y calibración", _fmt({k: v.get("prob_summary") for k, v in targets.items()}) +
            "\n\nUn score de ranking no es probabilidad calibrada.")
    section(10, "Folds, fuentes y meses", "Folds: " + _fmt(metrics.get("fold_manifest")) +
            "; desgloses: " + _fmt({k: v.get("breakdown") for k, v in targets.items()}))
    section(11, "Ablaciones y ensambles", _fmt({k: v.get("ablations") for k, v in targets.items()}))
    section(12, "Dependencia entre sistemas (phi)", _fmt(secondary.get("cross_system_pos1")) +
            "\n\nJaccard omitido por presupuesto de memoria cuando así consta; no asumir independencia.")
    section(13, "Reinicio de fuente y controles", "Reinicio: " + _fmt(metrics.get("source_restart")) +
            "; controles sanos/señales/orden: " + _fmt(metrics.get("controls_summary")) +
            "; streams: " + _fmt(len(metrics["controls"]) if "controls" in metrics else None) +
            ". Nulo de orden condicionado a intercambiabilidad.")
    section(14, "Fallos, presupuesto y límites", f"Próximo paso: {_fmt(status.get('next_step'))}; "
            f"inventario: {_fmt(metrics.get('inventory'))}; detectabilidad: {_fmt(metrics.get('mde'))}. "
            "Datos históricos ya conocidos: ninguna señal retrospectiva prueba confirmación prospectiva. "
            "Fase supervisada incompleta cuando figura pendiente; no ocultar controles ni fallos.")
    text = "\n".join(lines).rstrip() + "\n"
    root.mkdir(parents=True, exist_ok=True)
    (root / "resumen.md").write_text(text, encoding="utf-8")
    return text
