"""Frozen-oracle reference export for the rebuild acceptance harness.

The expected values were produced once by the legacy flat engine and are stored with their
provenance in reference-golden.json; this script no longer executes any legacy engine.

Run from webapp/backend with py -3.14 and an isolated LABORATORIO_DATA_DIR.
Writes only into the caller-provided temporary output directory.
"""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys

from laboratorio.engine.adapter import open_lab_data
from laboratorio.settings import Settings

GOLDEN_PATH = Path(__file__).resolve().with_name("reference-golden.json")


def load_golden() -> dict:
    try:
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        provenance, report = golden["provenance"], golden["reference"]
    except (OSError, ValueError, KeyError) as exc:
        raise RuntimeError(f"cannot read frozen golden at {GOLDEN_PATH}: {exc}") from exc
    for field in ("frozen_on", "base_commit", "frozen_history_sha256", "rankings_sha256"):
        if not provenance.get(field):
            raise RuntimeError(f"golden provenance lacks {field}")
    for field in ("frozen_history_sha256", "rankings_sha256"):
        if report.get(field) != provenance[field]:
            raise RuntimeError(f"golden {field} disagrees with its provenance")
    return golden


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: reference.py TEMP_OUTPUT_DIRECTORY")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_environment()
    data = open_lab_data(settings)

    golden = load_golden()
    provenance, report = golden["provenance"], golden["reference"]
    actual = {
        "frozen_history_sha256": data.history.sha256,
        "rankings_sha256": hashlib.sha256(settings.rankings_path.read_bytes()).hexdigest(),
        "draws": len(data.history.labels),
        "ranked_draws": len(data.rankings.row_ids),
    }
    for field, value in actual.items():
        expected = provenance.get(field, report[field])
        if value != expected:
            raise RuntimeError(f"data in use differs from the frozen golden: {field}")
    try:
        base = json.loads(settings.history_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"cannot parse bundled history at {settings.history_path}: {exc}") from exc
    labels = sorted(
        f"{day} {record['hora']}"
        for day, draws in base["sorteos_por_fecha"].items()
        for record in draws
    )
    last_label = labels[-1]
    last_day = last_label[:10]
    existing_record = next(
        record for record in base["sorteos_por_fecha"][last_day]
        if f"{last_day} {record['hora']}" == last_label
    )
    new_day = (date.fromisoformat(last_day) + timedelta(days=1)).isoformat()
    synthetic = {
        "metadata": {"schema_version": 1, "juego": "Quiniela 80", "origen": "acceptance"},
        "sorteos_por_fecha": {new_day: [{
            "hora": "10:00", "numeros": ["01", "02", "03", "04", "05"]
        }]},
    }
    conflicting = {
        "metadata": {"schema_version": 1, "juego": "Quiniela 80", "origen": "acceptance"},
        "sorteos_por_fecha": {last_day: [{
            "hora": existing_record["hora"],
            "numeros": [f"{(int(value) + 1) % 100:02d}" for value in existing_record["numeros"]],
        }]},
    }
    (output / "synthetic-history.json").write_text(
        json.dumps(synthetic, ensure_ascii=False), encoding="utf-8"
    )
    (output / "conflicting-history.json").write_text(
        json.dumps(conflicting, ensure_ascii=False), encoding="utf-8"
    )

    if report["last_label"] != last_label or report["new_label"] != f"{new_day} 10:00":
        raise RuntimeError("history labels differ from the frozen golden")
    (output / "reference.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"output": str(output), "reference": report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
