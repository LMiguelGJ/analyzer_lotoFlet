#!/usr/bin/env python3
"""Descarga el histórico de la Quiniela Leidsa desde premios.do.

Cada página https://premios.do/resultados-leidsa-AAAA-MM-DD trae los 15
sorteos más recientes hasta esa fecha, así que se consulta de 15 en 15 días
desde la fecha inicial hasta hoy. Guarda los tres números de cada sorteo en
datos/leidsa_quiniela_history.json, con el mismo formato que datos/chance_express_history.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

OFFICIAL_PAGE = "https://www.leidsa.com/results"
PREMIOS_ENDPOINT = "https://premios.do/resultados-leidsa-"
TIMEZONE = "America/Santo_Domingo"
DEFAULT_START_DATE = date(2023, 1, 4)  # Primer sorteo publicado en premios.do.
WINDOW_DAYS = 15  # Sorteos que muestra cada página.
NUMBER_RE = re.compile(r"^\d{1,2}$")
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "datos" / "leidsa_quiniela_history.json"
# Fecha de la tarjeta, p. ej. "Lunes 16 de noviembre, 2026". Los enlaces de los
# sorteos recientes dicen "hoy"/"ayer", así que se usa el texto y no el href.
DATE_TEXT_RE = re.compile(r"(\d{1,2})\s+de\s+([a-záéíóú]+),?\s+(\d{4})", re.IGNORECASE)
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def parse_card_date(text: str) -> date | None:
    match = DATE_TEXT_RE.search(text)
    if match is None:
        return None
    month = MONTHS.get(match.group(2).lower())
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(1)))
    except ValueError:
        return None


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
        "User-Agent": "Mozilla/5.0 (compatible; LeidsaQuinielaDownloader/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    return session


def fetch_page(session: requests.Session, day: date, timeout: float) -> dict[str, list[dict[str, Any]]]:
    """Consulta la página de un día y devuelve sus sorteos agrupados por fecha."""
    url = f"{PREMIOS_ENDPOINT}{day.isoformat()}"
    response = session.get(url, timeout=timeout)
    if response.status_code == 404:
        return {}
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    cards = soup.select("div.result-card")
    if not cards:
        raise DownloadError(f"Respuesta sin tarjetas de sorteos para {day.isoformat()}")

    found: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        date_el = card.select_one("span.result-date")
        time_el = card.select_one("span.lottery-closing-time")
        numbers = [b.get_text(strip=True) for b in card.select("div.result-ball")]
        card_date = parse_card_date(date_el.get_text(" ", strip=True)) if date_el else None
        if card_date is None or time_el is None:
            raise DownloadError(f"Sorteo sin fecha u hora en {url}")
        # El sitio muestra "•••" cuando todavía no publicó los números.
        if len(numbers) != 3 or any(not NUMBER_RE.fullmatch(n) for n in numbers):
            continue
        try:
            raw_time = time_el.get_text(strip=True).upper().replace(" ", "")
            hora = datetime.strptime(raw_time, "%I:%M%p").strftime("%H:%M")
        except ValueError as exc:
            raise DownloadError(f"Hora inválida en {url}") from exc
        found.setdefault(card_date.isoformat(), []).append({
            "hora": hora,
            "numeros": [f"{int(n):02d}" for n in numbers],
            "source_url": url,
        })
    return found


def load_page(
    session: requests.Session, day: date, timeout: float, retries: int = 3
) -> dict[str, list[dict[str, Any]]] | None:
    """Obtiene una página. Devuelve None si falla tras los reintentos, para seguir adelante."""
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            return fetch_page(session, day, timeout)
        except (requests.RequestException, DownloadError) as exc:
            if attempt == retries:
                print(
                    f"  {day.isoformat()}: {type(exc).__name__} tras {retries} "
                    f"intentos, se salta esta ventana y se sigue.",
                    file=sys.stderr, flush=True,
                )
                return None
            print(
                f"  {day.isoformat()}: {type(exc).__name__}, reintento "
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
            "juego": "Leidsa Quiniela",
            "origen": OFFICIAL_PAGE,
            "endpoint": f"{PREMIOS_ENDPOINT}AAAA-MM-DD",
            "zona_horaria": TIMEZONE,
            "generado_utc": datetime.now(UTC).isoformat(),
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
                "No verificada: los datos vienen del agregador premios.do; "
                "las fechas sin sorteo publicado se conservan como listas vacías. "
                "La hora es la de cierre de ventas (el sorteo es 10 minutos después)."
            ),
        },
        "sorteos_por_fecha": ordered,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Descarga la Quiniela Leidsa por fecha al JSON raíz.")
    parser.add_argument("--start-date", help="Primera fecha (DD/MM/AAAA; por defecto 04/01/2023).")
    parser.add_argument("--end-date", help="Última fecha (DD/MM/AAAA; por defecto hoy).")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--delay", type=float, default=0.5, help="Segundos entre consultas.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout por consulta.")
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
        rows = {
            k: list(v or [])
            for k, v in (saved.get("sorteos_por_fecha") or {}).items()
            if k >= scan_start.isoformat()
        }
        duplicates = (saved.get("metadata") or {}).get("filas_duplicadas_exactas_omitidas") or 0

    # ¿Desde dónde seguimos? Con progreso parcial se retoma; si estaba completo,
    # se vuelve a pedir el último día por si se publicó después de la descarga.
    state = (saved.get("metadata") or {}).get("descarga") or {}
    cursor_text = state.get("proxima_fecha")
    if not rows:
        cursor = scan_start
    elif cursor_text:
        cursor = date.fromisoformat(cursor_text)
    else:
        cursor = min(date.fromisoformat(max(rows)), end)

    # Ventanas de 15 días: la página del día E trae los sorteos de E-14 a E.
    windows: list[tuple[date, date]] = []
    start = cursor
    while start <= end:
        stop = min(start + timedelta(days=WINDOW_DAYS - 1), end)
        windows.append((start, stop))
        start = stop + timedelta(days=1)

    print(f"Consultando {len(windows)} páginas: {cursor.isoformat()} a {end.isoformat()}")
    print(f"JSON: {path}")

    session = make_session()
    started = time.monotonic()
    try:
        for index, (win_start, win_end) in enumerate(windows, 1):
            if index > 1 and args.delay:
                time.sleep(args.delay)
            found = load_page(session, win_end, args.timeout)
            skipped = found is None
            found = found or {}
            for offset in range((win_end - win_start).days + 1):
                key = (win_start + timedelta(days=offset)).isoformat()
                records = found.get(key) or []
                unique: dict[str, dict[str, Any]] = {}
                for record in records:
                    unique[f"row:{record['hora']}:{','.join(record['numeros'])}"] = record
                duplicates += len(records) - len(unique)
                # Una respuesta vacía nunca borra sorteos que ya teníamos guardados.
                if unique:
                    rows[key] = sorted(unique.values(), key=lambda r: r["hora"])
                else:
                    rows.setdefault(key, [])
            next_cursor = win_end + timedelta(days=1) if win_end < end else None
            status = "complete" if next_cursor is None else "in_progress"
            save_json(path, build_payload(rows, scan_start, next_cursor, duplicates, status))
            got = sum(len(found.get((win_start + timedelta(days=o)).isoformat()) or [])
                      for o in range((win_end - win_start).days + 1))
            estado = "SALTADO" if skipped else f"{got} sorteos"
            print(f"[{index}/{len(windows)}] {win_start.isoformat()} a {win_end.isoformat()} | {estado}")
    except KeyboardInterrupt:
        print(f"\nDetenido. El progreso quedó guardado en {path}.", file=sys.stderr)
        return 130

    total = sum(len(v) for v in rows.values())
    elapsed = int(time.monotonic() - started)
    print(f"\nListo: {total} sorteos en {len(rows)} fechas ({len(windows)} páginas en {elapsed}s).")
    print(f"JSON guardado en: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
