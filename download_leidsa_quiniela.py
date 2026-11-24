#!/usr/bin/env python3
"""Descarga el histórico de la Quiniela Leidsa (premios.do + respaldo histórico).

Fuente principal (verdad desde 2023-01-04): cada página
https://premios.do/resultados-leidsa-AAAA-MM-DD trae los 15 sorteos más
recientes hasta esa fecha, así que se consulta de 15 en 15 días desde la fecha
inicial hasta hoy. Guarda los tres números de cada sorteo en
datos/leidsa_quiniela_history.json, con el mismo formato que datos/chance_express_history.json.

Respaldo histórico (opcional, --backfill): premios.do no publica nada antes de
2023-01-04, así que las fechas anteriores se toman de las páginas anuales de
https://www.miresultadoloteria.com/quiniela-pale/AAAA (Quiniela Palé de Leidsa;
solo trae día, mes y los tres números, no la hora). Para esas fechas la hora se
infiere del día de la semana (15:50 domingo, 20:50 el resto, igual que en
premios.do desde 2023). Antes de mezclar se comparan, en el mismo orden, los
números de las fechas que ambas fuentes comparten y se aborta si coinciden
menos del 99,5 %. Las fechas >= 2023-01-04 NUNCA se sobrescriben con el
respaldo: desde la fecha de corte manda premios.do.
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
CUTOVER_DATE = DEFAULT_START_DATE  # Desde aquí manda premios.do; antes, el respaldo.
BACKFILL_ENDPOINT = "https://www.miresultadoloteria.com/quiniela-pale/"
BACKFILL_MIN_YEAR = 2000  # Tope de seguridad al buscar hacia atrás.
BACKFILL_MATCH_THRESHOLD = 0.995  # Coincidencia mínima en las fechas compartidas.
SUNDAY_HORA = "15:50"  # Hora de cierre en domingo.
WEEKDAY_HORA = "20:50"  # Hora de cierre de lunes a sábado.
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
    ok, found = _retry(day.isoformat(), lambda: fetch_page(session, day, timeout), retries)
    return found if ok else None


def _retry(label: str, call: Any, retries: int) -> tuple[bool, Any]:
    """Ejecuta call() con reintentos y espera creciente. Devuelve (ok, resultado)."""
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            return True, call()
        except (requests.RequestException, DownloadError) as exc:
            if attempt == retries:
                print(
                    f"  {label}: {type(exc).__name__} tras {retries} "
                    f"intentos, se salta y se sigue.",
                    file=sys.stderr, flush=True,
                )
                return False, None
            print(
                f"  {label}: {type(exc).__name__}, reintento "
                f"{attempt}/{retries} en {delay:.0f}s",
                file=sys.stderr, flush=True,
            )
            time.sleep(delay)
            delay = min(delay * 2, 60.0)
    return False, None


def inferred_hora(day: date) -> str:
    """El respaldo no publica la hora: domingo 15:50, el resto 20:50."""
    return SUNDAY_HORA if day.weekday() == 6 else WEEKDAY_HORA


def parse_year_page(content: bytes | str, year: int) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    """Interpreta una página anual de miresultadoloteria.com.

    Devuelve ({fecha ISO: [n1, n2, n3]}, descartes). Las filas que no se pueden
    interpretar con seguridad (mes distinto del encabezado, fecha inexistente,
    cantidad de números distinta de 3, fecha repetida con números distintos) no
    se inventan: se descartan y quedan anotadas.
    """
    soup = BeautifulSoup(content, "html.parser")
    blocks = soup.select("div.rrm-month-results")
    if not blocks:
        raise DownloadError(f"Página anual {year} sin bloques de meses")

    draws: dict[str, list[str]] = {}
    discarded: list[dict[str, Any]] = []
    conflicting: set[str] = set()
    for block in blocks:
        title_el = block.select_one(".rrm-month-title h2")
        title_words = title_el.get_text(" ", strip=True).split() if title_el else []
        header_month = MONTHS.get(title_words[-1].lower()) if title_words else None
        if header_month is None:
            raise DownloadError(f"Encabezado de mes desconocido en la página anual {year}")
        for item in block.select("div.rrm-single-result-wrap"):
            date_el = item.select_one("p.rrm-year-results-date")
            text = date_el.get_text(" ", strip=True) if date_el else ""
            match = re.fullmatch(r"Resultado\s+(\d{1,2})\s+(\S+)", text, re.IGNORECASE)
            numbers = [n.get_text(strip=True) for n in item.select(".rrm-draw-numbers span")]
            if match is None:
                discarded.append({"fecha": f"{year} ({text or 'sin fecha'})", "motivo": "fecha ilegible", "numeros": numbers})
                continue
            month = MONTHS.get(match.group(2).lower())
            try:
                if month is None or month != header_month:
                    raise ValueError("mes distinto del encabezado")
                day = date(year, month, int(match.group(1)))
            except ValueError as exc:
                discarded.append({"fecha": f"{year} ({text})", "motivo": str(exc), "numeros": numbers})
                continue
            key = day.isoformat()
            if len(numbers) != 3 or any(not NUMBER_RE.fullmatch(n) for n in numbers):
                discarded.append({
                    "fecha": key,
                    "motivo": f"se esperaban 3 números y vinieron {len(numbers)}",
                    "numeros": numbers,
                })
                continue
            normalized = [f"{int(n):02d}" for n in numbers]
            if key in draws and draws[key] != normalized:
                conflicting.add(key)
                discarded.append({"fecha": key, "motivo": "fecha repetida con números distintos", "numeros": normalized})
            else:
                draws[key] = normalized
    for key in conflicting:
        draws.pop(key, None)
    return draws, discarded


def fetch_year(
    session: requests.Session, year: int, timeout: float
) -> tuple[dict[str, list[str]], list[dict[str, Any]]] | None:
    """Descarga la página anual del respaldo. None si el sitio responde 404 (año sin datos)."""
    response = session.get(f"{BACKFILL_ENDPOINT}{year}", timeout=timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return parse_year_page(response.content, year)


def compare_overlap(
    backfill: dict[str, list[str]],
    premios_rows: dict[str, list[dict[str, Any]]],
    first_year: int,
    last_year: int,
) -> dict[str, Any]:
    """Compara, en el mismo orden, las fechas >= corte que tienen ambas fuentes."""
    compared = matched = only_premios = only_backfill = 0
    mismatches: list[dict[str, Any]] = []
    for key in sorted(set(backfill) | {k for k, v in premios_rows.items() if v}):
        if key < CUTOVER_DATE.isoformat() or not first_year <= int(key[:4]) <= last_year:
            continue
        premios = [r["numeros"] for r in premios_rows.get(key) or []]
        mine = backfill.get(key)
        if premios and mine is not None:
            compared += 1
            if premios == [mine]:
                matched += 1
            else:
                mismatches.append({"fecha": key, "premios_do": premios, "respaldo": mine})
        elif premios:
            only_premios += 1
        else:
            only_backfill += 1
    return {
        "fechas_comparadas": compared,
        "coincidencias": matched,
        "tasa_coincidencia": round(matched / compared, 6) if compared else None,
        "umbral_minimo": BACKFILL_MATCH_THRESHOLD,
        "discrepancias": mismatches,
        "fechas_solo_en_premios_do": only_premios,
        "fechas_solo_en_respaldo": only_backfill,
    }


def run_backfill(
    session: requests.Session,
    premios_rows: dict[str, list[dict[str, Any]]],
    first_year: int | None,
    lower_date: date,
    upper_date: date,
    timeout: float,
    delay: float,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Baja las páginas anuales, valida contra premios.do y arma las fechas < corte.

    Con first_year=None busca hacia atrás hasta el primer año que da 404 o viene
    sin sorteos. Lanza DownloadError si la validación cruzada no alcanza el umbral.
    """
    last_year = CUTOVER_DATE.year + 1  # Un año más solo para ampliar la muestra de validación.
    min_year = first_year if first_year is not None else BACKFILL_MIN_YEAR
    parsed: dict[str, list[str]] = {}
    discarded: list[dict[str, Any]] = []
    per_year: dict[str, int] = {}
    failed_years: list[int] = []
    stopped_at: int | None = None
    for index, year in enumerate(range(last_year, min_year - 1, -1)):
        if index and delay:
            time.sleep(delay)
        ok, result = _retry(f"año {year}", lambda y=year: fetch_year(session, y, timeout), 3)
        if not ok:
            failed_years.append(year)
            continue
        if result is None or not result[0]:
            if first_year is None:
                stopped_at = year
                break
            continue
        draws, dropped = result
        parsed.update(draws)
        discarded.extend(dropped)
        per_year[str(year)] = len(draws)
        print(f"  año {year}: {len(draws)} sorteos" + (f", {len(dropped)} descartados" if dropped else ""))
    if not parsed:
        raise DownloadError("El respaldo no devolvió ningún sorteo")

    overlap = compare_overlap(parsed, premios_rows, CUTOVER_DATE.year, last_year)
    rate = overlap["tasa_coincidencia"]
    if rate is None:
        raise DownloadError(
            "No hay fechas compartidas con premios.do para validar el respaldo; "
            "descargá primero premios.do hasta una fecha posterior al corte."
        )
    if rate < BACKFILL_MATCH_THRESHOLD:
        raise DownloadError(
            f"El respaldo coincide solo {rate:.2%} con premios.do en {overlap['fechas_comparadas']} "
            f"fechas (mínimo {BACKFILL_MATCH_THRESHOLD:.1%}). No se mezcla. Primeras discrepancias: "
            f"{overlap['discrepancias'][:5]}"
        )

    cutover = CUTOVER_DATE.isoformat()
    old = {
        k: v for k, v in sorted(parsed.items())
        if k < cutover and lower_date.isoformat() <= k <= upper_date.isoformat()
    }
    if not old:
        raise DownloadError("El respaldo no trae fechas anteriores al corte dentro del rango pedido")
    first_day = date.fromisoformat(min(old))
    last_day = date.fromisoformat(max(old))
    history: dict[str, list[dict[str, Any]]] = {}
    for offset in range((last_day - first_day).days + 1):
        day = first_day + timedelta(days=offset)
        key = day.isoformat()
        history[key] = [{
            "hora": inferred_hora(day),
            "numeros": old[key],
            "source_url": f"{BACKFILL_ENDPOINT}{day.year}",
        }] if key in old else []
    # Señal de calidad: el respaldo parece repetir el resultado del día anterior en algunas
    # fechas (sobre todo feriados de diciembre); en premios.do desde 2023 eso nunca ocurre.
    repeated = [
        key for key in old
        if old.get((date.fromisoformat(key) - timedelta(days=1)).isoformat()) == old[key]
    ]
    years_before = [int(y) for y in per_year if int(y) < CUTOVER_DATE.year]
    info = {
        "fuente": BACKFILL_ENDPOINT + "AAAA",
        "estado": "incomplete" if failed_years else "complete",
        "anios_con_datos": dict(sorted(per_year.items())),
        "primer_anio_con_datos": min(years_before) if years_before else None,
        "primer_anio_sin_pagina_o_sin_datos": stopped_at,
        "anios_con_error": sorted(failed_years),
        "primera_fecha": first_day.isoformat(),
        "hasta": last_day.isoformat(),
        "hora": (
            "Inferida del día de la semana (15:50 domingo, 20:50 resto): "
            "miresultadoloteria.com no publica la hora de los sorteos."
        ),
        "fechas_descartadas": discarded,
        "fechas_con_numeros_iguales_al_dia_anterior": repeated,
        "validacion_cruzada": overlap,
        "generado_utc": datetime.now(UTC).isoformat(),
    }
    return history, info


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
    backfill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ordered = {k: rows[k] for k in sorted(rows)}
    populated = [k for k, v in ordered.items() if v]
    empty = [k for k, v in ordered.items() if not v]
    first = next(iter(ordered), scan_start.isoformat())
    last = next(reversed(ordered), scan_start.isoformat())
    fuentes: dict[str, Any] = {
        "fecha_corte": CUTOVER_DATE.isoformat(),
        "premios_do": {
            "url": f"{PREMIOS_ENDPOINT}AAAA-MM-DD",
            "desde": CUTOVER_DATE.isoformat(),
            "hasta": last,
            "nota": "Fuente de verdad desde la fecha de corte; nunca se sobrescribe con el respaldo.",
        },
    }
    descarga: dict[str, Any] = {
        "estado": status,
        "fase": "forward_scan",
        "scan_desde": scan_start.isoformat(),
        "proxima_fecha": cursor.isoformat() if cursor else None,
    }
    completitud = (
        "No verificada: los datos vienen del agregador premios.do; "
        "las fechas sin sorteo publicado se conservan como listas vacías. "
        "La hora es la de cierre de ventas (el sorteo es 10 minutos después)."
    )
    if backfill:
        fuentes["respaldo_historico"] = {
            "url": BACKFILL_ENDPOINT + "AAAA",
            "desde": backfill.get("primera_fecha"),
            "hasta": backfill.get("hasta"),
            "nota": (
                "Quiniela Palé de Leidsa. Solo para fechas anteriores al corte; no publica "
                "la hora, que se infiere del día de la semana."
            ),
        }
        descarga["respaldo_historico"] = backfill
        completitud = (
            f"No verificada. Desde {CUTOVER_DATE.isoformat()} los datos vienen de premios.do "
            "(fuente de verdad); antes, del respaldo miresultadoloteria.com, validado contra "
            "premios.do en las fechas compartidas. Las fechas sin sorteo publicado se conservan "
            "como listas vacías (feriados o huecos de la fuente). La hora desde el corte es la de "
            "cierre de ventas (el sorteo es 10 minutos después); antes del corte la hora está "
            "inferida del día de la semana (15:50 domingo, 20:50 resto) porque el respaldo no "
            "publica ninguna hora."
        )
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
            "fuentes": fuentes,
            "descarga": descarga,
            "completitud_historica": completitud,
        },
        "sorteos_por_fecha": ordered,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Descarga la Quiniela Leidsa por fecha al JSON raíz. Desde 04/01/2023 usa premios.do "
            "(fuente de verdad); con --backfill completa las fechas anteriores desde "
            "miresultadoloteria.com, sin sobrescribir nunca fechas >= 04/01/2023."
        )
    )
    parser.add_argument(
        "--start-date",
        help=(
            "Primera fecha (DD/MM/AAAA; por defecto 04/01/2023). Una fecha anterior a 04/01/2023 "
            "exige --backfill y limita el respaldo a fechas >= esa."
        ),
    )
    parser.add_argument("--end-date", help="Última fecha (DD/MM/AAAA; por defecto hoy).")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--delay", type=float, default=0.5, help="Segundos entre consultas.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout por consulta.")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help=(
            "Completa las fechas anteriores a 04/01/2023 con las páginas anuales de "
            "miresultadoloteria.com (valida contra premios.do y aborta si coincide < 99,5 %%). "
            "La hora se infiere del día de la semana (15:50 domingo, 20:50 resto). "
            "Sin esta opción, el respaldo ya guardado en el JSON se conserva intacto."
        ),
    )
    parser.add_argument(
        "--backfill-desde-anio",
        type=int,
        help=(
            "Primer año del respaldo a bajar. Por defecto se busca hacia atrás hasta el primer "
            "año que responde 404 o viene sin sorteos."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Borrar el JSON (incluido el respaldo histórico) y empezar de cero.",
    )
    args = parser.parse_args(argv)

    if args.delay < 0 or args.timeout <= 0:
        parser.error("--delay debe ser >= 0 y --timeout > 0")
    if args.backfill_desde_anio is not None and not args.backfill:
        parser.error("--backfill-desde-anio requiere --backfill")
    if args.backfill_desde_anio is not None and args.backfill_desde_anio >= CUTOVER_DATE.year:
        parser.error(f"--backfill-desde-anio debe ser anterior a {CUTOVER_DATE.year}")

    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    scan_start = parse_date(args.start_date, "--start-date") if args.start_date else DEFAULT_START_DATE
    end = parse_date(args.end_date, "--end-date") if args.end_date else today
    if end > today:
        parser.error("--end-date no puede ser posterior a hoy")
    if end < scan_start:
        parser.error("--end-date debe ser posterior a --start-date")
    if scan_start < CUTOVER_DATE and not args.backfill:
        parser.error(
            f"premios.do no publica nada antes de {CUTOVER_DATE.strftime('%d/%m/%Y')}; "
            "usá --backfill para pedir fechas anteriores."
        )
    # premios.do solo se consulta desde la fecha de corte; antes lo cubre el respaldo.
    premios_start = max(scan_start, CUTOVER_DATE)

    path = args.output.resolve()
    rows: dict[str, list[dict[str, Any]]] = {}
    history: dict[str, list[dict[str, Any]]] = {}
    backfill_info: dict[str, Any] | None = None
    saved: dict[str, Any] = {}
    duplicates = 0

    if path.exists() and not args.overwrite:
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"ERROR: el JSON está dañado ({exc}). Usá --overwrite para empezar de cero.", file=sys.stderr)
            return 1
        saved_rows = saved.get("sorteos_por_fecha") or {}
        rows = {
            k: list(v or [])
            for k, v in saved_rows.items()
            if k >= premios_start.isoformat()
        }
        # El respaldo histórico (fechas < corte) se conserva siempre que ya exista.
        history = {k: list(v or []) for k, v in saved_rows.items() if k < CUTOVER_DATE.isoformat()}
        backfill_info = ((saved.get("metadata") or {}).get("descarga") or {}).get("respaldo_historico")
        duplicates = (saved.get("metadata") or {}).get("filas_duplicadas_exactas_omitidas") or 0

    # ¿Desde dónde seguimos? Con progreso parcial se retoma; si estaba completo,
    # se vuelve a pedir el último día por si se publicó después de la descarga.
    state = (saved.get("metadata") or {}).get("descarga") or {}
    cursor_text = state.get("proxima_fecha")
    if not rows:
        cursor = premios_start
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
    if scan_start < CUTOVER_DATE or args.backfill:
        print(f"Respaldo histórico: {BACKFILL_ENDPOINT}AAAA (fechas anteriores a {CUTOVER_DATE.isoformat()})")
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
            save_json(path, build_payload(
                {**history, **rows}, premios_start, next_cursor, duplicates, status, backfill_info,
            ))
            got = sum(len(found.get((win_start + timedelta(days=o)).isoformat()) or [])
                      for o in range((win_end - win_start).days + 1))
            estado = "SALTADO" if skipped else f"{got} sorteos"
            print(f"[{index}/{len(windows)}] {win_start.isoformat()} a {win_end.isoformat()} | {estado}")
    except KeyboardInterrupt:
        print(f"\nDetenido. El progreso quedó guardado en {path}.", file=sys.stderr)
        return 130

    if args.backfill:
        print("\nRespaldo histórico:")
        try:
            new_history, backfill_info = run_backfill(
                session, rows, args.backfill_desde_anio,
                scan_start if scan_start < CUTOVER_DATE else date.min,
                min(end, CUTOVER_DATE - timedelta(days=1)), args.timeout, args.delay,
            )
        except DownloadError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            print("\nDetenido durante el respaldo; el JSON no se modificó con él.", file=sys.stderr)
            return 130
        history.update(new_history)
        # Estado final: la descarga de premios.do no cambia, solo se agrega el respaldo.
        save_json(path, build_payload(
            {**history, **rows}, premios_start, None, duplicates, "complete", backfill_info,
        ))
        validation = backfill_info["validacion_cruzada"]
        print(
            f"Validación: {validation['coincidencias']}/{validation['fechas_comparadas']} fechas coinciden "
            f"con premios.do ({validation['tasa_coincidencia']:.2%})."
        )

    total = sum(len(v) for v in {**history, **rows}.values())
    elapsed = int(time.monotonic() - started)
    print(f"\nListo: {total} sorteos en {len(history) + len(rows)} fechas ({len(windows)} páginas en {elapsed}s).")
    print(f"JSON guardado en: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
