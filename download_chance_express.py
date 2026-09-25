#!/usr/bin/env python3
"""Descarga los resultados oficiales de Loteka Chance Express por fecha.

Consulta el endpoint oficial día por día desde la fecha inicial hasta hoy y
guarda los cinco números de cada sorteo en chance_express_history.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

OFFICIAL_PAGE = "https://loteka.com.do/chance-express/"
OFFICIAL_ENDPOINT = "https://loteka.com.do/wp-content/themes/loteka/getChanceExpress.php"
# Agregador con histórico desde 01/02/2025. Se usa sólo cuando la fuente oficial
# devuelve vacío; no publica el ID del sorteo, sólo hora y cinco números.
PREMIOS_ENDPOINT = "https://premios.do/resultados-chance-express-"
TIMEZONE = "America/Santo_Domingo"
DEFAULT_START_DATE = date(2025, 3, 5)  # Fecha inicial del historial.
NUMBER_RE = re.compile(r"^\d{1,2}$")


class DownloadError(RuntimeError):
    """El servidor devolvió algo que no se puede interpretar con seguridad."""


def parse_date(value: str, option: str) -> date:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"{option} debe usar el formato DD/MM/AAAA")


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ChanceExpressDownloader/2.0)",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": OFFICIAL_PAGE,
    })
    return session


def fetch_day(session: requests.Session, day: date, timeout: float) -> list[dict[str, Any]]:
    """Consulta un día y devuelve sus sorteos, con las cinco posiciones en orden."""
    response = session.get(
        OFFICIAL_ENDPOINT,
        params={"fechaSeleccionada": day.strftime("%d/%m/%Y")},
        timeout=timeout,
    )
    response.raise_for_status()
    if not response.content.strip():
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    wrapper = soup.select_one("#result-chanceexpress")
    items = wrapper.select("li") if wrapper is not None else soup.select("li")
    if not items:
        if wrapper is not None:
            return []
        raise DownloadError(f"Respuesta sin lista de sorteos para {day.strftime('%d/%m/%Y')}")

    records = []
    for item in items:
        time_el = item.select_one("span.orange")
        numbers = [n.get_text(strip=True) for n in item.select("span.numero")]
        if time_el is None or len(numbers) != 5:
            raise DownloadError(f"Sorteo incompleto en {day.strftime('%d/%m/%Y')}")
        if any(not NUMBER_RE.fullmatch(n) for n in numbers):
            raise DownloadError(f"Número inválido en {day.strftime('%d/%m/%Y')}")
        try:
            values = [f"{int(n):02d}" for n in numbers]
            hora = datetime.strptime(time_el.get_text(strip=True).upper(), "%I:%M %p").strftime("%H:%M")
        except ValueError as exc:
            raise DownloadError(f"Hora o número inválido en {day.strftime('%d/%m/%Y')}") from exc
        records.append({
            "hora": hora,
            "numeros": values,
            "source_url": response.url,
        })
    return records


def fetch_day_premios(session: requests.Session, day: date, timeout: float) -> list[dict[str, Any]]:
    """Histórico desde premios.do, para los días que la fuente oficial no tiene."""
    url = f"{PREMIOS_ENDPOINT}{day.isoformat()}"
    response = session.get(url, timeout=timeout)
    if response.status_code == 404:
        return []
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    records = []
    for card in soup.select("div.result-card"):
        time_el = card.select_one("span.lottery-closing-time")
        numbers = [b.get_text(strip=True) for b in card.select("div.result-ball")]
        # El sitio muestra "•••" cuando no tiene publicados los números.
        if time_el is None or len(numbers) != 5 or any(not NUMBER_RE.fullmatch(n) for n in numbers):
            continue
        try:
            raw_time = time_el.get_text(strip=True).upper().replace(" ", "")
            hora = datetime.strptime(raw_time, "%I:%M%p").strftime("%H:%M")
            values = [f"{int(n):02d}" for n in numbers]
        except ValueError:
            continue
        records.append({
            "hora": hora,
            "numeros": values,
            "source_url": url,
        })
    return records


def load_day(
    session: requests.Session, day: date, timeout: float, retries: int = 3
) -> tuple[list[dict[str, Any]], int] | None:
    """Obtiene un día. Devuelve None si falla tras los reintentos, para seguir adelante."""
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            raw = fetch_day(session, day, timeout)
            if not raw:
                raw = fetch_day_premios(session, day, timeout)
            unique: dict[str, dict[str, Any]] = {}
            for record in raw:
                # Sin ID de sorteo: sólo se descartan filas totalmente idénticas.
                unique[f"row:{record['hora']}:{','.join(record['numeros'])}"] = record
            return sorted(unique.values(), key=lambda r: r["hora"]), len(raw) - len(unique)
        except (requests.RequestException, DownloadError) as exc:
            if attempt == retries:
                print(
                    f"  {day.strftime('%d/%m/%Y')}: {type(exc).__name__} tras {retries} "
                    f"intentos, se salta esta fecha y se sigue.",
                    file=sys.stderr, flush=True,
                )
                return None
            print(
                f"  {day.strftime('%d/%m/%Y')}: {type(exc).__name__}, reintento "
                f"{attempt}/{retries} en {delay:.0f}s",
                file=sys.stderr, flush=True,
            )
            time.sleep(delay)
            delay = min(delay * 2, 60.0)
    return None


def save_json(path: Path, payload: dict[str, Any]) -> None:
    """Guarda el JSON. Tolerar el bloqueo momentáneo de OneDrive/antivirus."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for attempt in range(5):
            try:
                tmp.replace(path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.5)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def build_payload(
    rows: dict[str, list[dict[str, Any]]],
    scan_start: date,
    cursor: date | None,
    duplicates: int,
    status: str,
) -> dict[str, Any]:
    ordered = {k: rows[k] for k in sorted(rows)}
    populated = [k for k, v in ordered.items() if v]
    empty = [k for k, v in ordered.items() if not v]
    first = next(iter(ordered), scan_start.isoformat())
    last = next(reversed(ordered), scan_start.isoformat())
    return {
        "metadata": {
            "schema_version": 1,
            "juego": "Loteka Chance Express",
            "origen": OFFICIAL_PAGE,
            "endpoint": OFFICIAL_ENDPOINT,
            "zona_horaria": TIMEZONE,
            "generado_utc": datetime.now(timezone.utc).isoformat(),
            "rango_solicitado": {"desde": first, "hasta": last},
            "rango_seleccionado": {"desde": first, "hasta": last},
            "dias_solicitados": len(ordered),
            "dias_limite": None,
            "dias_completados": len(ordered),
            "dias_con_sorteos": len(populated),
            "dias_sin_resultados": empty,
            "cantidad_sorteos": sum(len(v) for v in ordered.values()),
            "filas_duplicadas_exactas_omitidas": duplicates,
            "cobertura_observada": {
                "primera_fecha_con_datos": populated[0] if populated else None,
                "ultima_fecha_con_datos": populated[-1] if populated else None,
            },
            "descarga": {
                "estado": status,
                "fase": "forward_scan",
                "scan_desde": scan_start.isoformat(),
                "proxima_fecha": cursor.isoformat() if cursor else None,
            },
            "completitud_historica": (
                "No verificada: las fechas sin resultados del endpoint oficial "
                "se conservan como listas vacías."
            ),
        },
        "sorteos_por_fecha": ordered,
    }


def print_day(day: date, records: list[dict[str, Any]], quiet: bool) -> None:
    if not records or quiet:
        return
    border = "+" + "=" * 59 + "+"
    print(f"\n{border}")
    title = f" LOTEKA | CHANCE EXPRESS | {day.isoformat()} | {len(records)} sorteos "
    print("|" + title[:59].ljust(59) + "|")
    print(border)
    for record in reversed(records):
        row = f"| {record['hora']} | " + " ".join(record["numeros"])
        print(row[:60].ljust(60) + "|")
    print(border)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Descarga Chance Express por fecha al JSON raíz.")
    parser.add_argument("--start-date", help="Primera fecha (DD/MM/AAAA; por defecto 05/03/2025).")
    parser.add_argument("--end-date", help="Última fecha (DD/MM/AAAA; por defecto hoy).")
    parser.add_argument("--output", type=Path, default=Path("chance_express_history.json"))
    parser.add_argument("--delay", type=float, default=0.25, help="Segundos entre consultas.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout por consulta.")
    parser.add_argument("--quiet-draws", action="store_true", help="No imprimir los números.")
    parser.add_argument("--rescan", action="store_true", help="Volver a consultar todo desde la fecha inicial.")
    parser.add_argument("--overwrite", action="store_true", help="Borrar el JSON y empezar de cero.")
    args = parser.parse_args(argv)

    if args.delay < 0 or args.timeout <= 0:
        parser.error("--delay debe ser >= 0 y --timeout > 0")

    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    scan_start = parse_date(args.start_date, "--start-date") if args.start_date else DEFAULT_START_DATE
    end = parse_date(args.end_date, "--end-date") if args.end_date else today
    if end > today:
        parser.error("--end-date no puede ser posterior a hoy")
    if end < scan_start:
        parser.error("--end-date debe ser posterior a --start-date")

    path = args.output.resolve()
    rows: dict[str, list[dict[str, Any]]] = {}
    saved: dict[str, Any] = {}
    duplicates = 0

    if path.exists() and not args.overwrite:
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"ERROR: el JSON está dañado ({exc}). Usá --overwrite para empezar de cero.", file=sys.stderr)
            return 1
        # Sólo se conserva desde la fecha inicial y sin el ID de sorteo.
        rows = {
            k: [{c: v for c, v in r.items() if c != "numero_sorteo"} for r in (v or [])]
            for k, v in (saved.get("sorteos_por_fecha") or {}).items()
            if k >= scan_start.isoformat()
        }
        meta = saved.get("metadata") or {}
        duplicates = meta.get("filas_duplicadas_exactas_omitidas") or 0

    # ¿Desde dónde seguimos? Si hay progreso parcial, nunca se vuelve a empezar de cero.
    state = (saved.get("metadata") or {}).get("descarga") or {}
    cursor_text = state.get("proxima_fecha")
    if not rows:
        cursor = scan_start
    elif cursor_text:
        cursor = date.fromisoformat(cursor_text)
    elif args.rescan:
        cursor = scan_start      # --rescan sobre un archivo ya completo: rehacer todo
    else:
        cursor = date.fromisoformat(max(rows))
        cursor = cursor + timedelta(days=1) if cursor < end else end

    days = [cursor + timedelta(days=i) for i in range((end - cursor).days + 1)]
    print(f"Consultando {len(days)} fechas: {cursor.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}")
    print(f"JSON: {path}")

    session = make_session()
    started = time.monotonic()
    last_day = cursor
    try:
        for index, day in enumerate(days, 1):
            last_day = day
            if index > 1 and args.delay:
                time.sleep(args.delay)
            result = load_day(session, day, args.timeout)
            if result is None:
                # Tras 3 intentos se salta el día y se sigue; no se borra lo guardado.
                found, dup = [], 0
                skipped = True
            else:
                found, dup = result
                skipped = False
            duplicates += dup
            # Una respuesta vacía nunca borra sorteos que ya teníamos guardados.
            if found:
                rows[day.isoformat()] = found
            else:
                rows.setdefault(day.isoformat(), [])
            next_cursor = day + timedelta(days=1) if day < end else None
            status = "complete" if next_cursor is None else "in_progress"
            save_json(path, build_payload(rows, scan_start, next_cursor, duplicates, status))
            estado = "SALTADO" if skipped else f"{len(found)} sorteos"
            print(f"[{index}/{len(days)}] {day.strftime('%d/%m/%Y')} | {estado}")
            print_day(day, found, args.quiet_draws)
            if index % 25 == 0 or index == len(days):
                elapsed = int(time.monotonic() - started)
                print(f"    progreso: {sum(len(v) for v in rows.values())} sorteos guardados | {elapsed}s")
    except KeyboardInterrupt:
        save_json(path, build_payload(rows, scan_start, last_day, duplicates, "in_progress"))
        print(f"\nDetenido. El progreso quedó guardado en {path}.", file=sys.stderr)
        return 130

    total = sum(len(v) for v in rows.values())
    print(f"\nListo: {total} sorteos en {len(rows)} fechas ({len(days)} consultadas ahora).")
    print(f"JSON guardado en: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
