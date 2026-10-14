"""Full bounded compatibility proof for the configured frozen history source."""

import hashlib
import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from laboratorio.domain.quiniela_profiles import create_profile
from laboratorio.engine.quiniela_import import preview_included_history, source_reference
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256, Settings


def included_profile():
    rules = {
        "schema_version": 2,
        "universe": list(range(100)),
        "display_width": 2,
        "positions": 5,
        "played_positions": list(range(5)),
        "order_matters": True,
        "allows_repeats": True,
        "multipliers": [{"numerator": value, "denominator": 1} for value in (80, 8, 4, 2, 1)],
        "payout_mode": "all",
        "currency": "DOP",
        "scale": 0,
        "minimum_stake": 1,
        "stake_increment": 1,
        "maximum_stake": 1_000,
        "max_coverage": 50,
        "max_exposure": 1_000_000,
    }
    return create_profile("Frozen included history", rules)


def test_included_history_retains_all_105426_draws_and_original_input_identity():
    raw = Settings.from_environment().history_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == HISTORY_SHA256
    preview = preview_included_history(raw, included_profile())
    assert preview.raw_sha256 == HISTORY_SHA256
    assert preview.draw_count == 105_426
    assert preview.input_rows == 105_426
    assert preview.duplicate_count == 0
    assert preview.canonical_sha256
    assert preview.timezone == "America/Santo_Domingo"
    assert preview.first_timestamp == "2025-03-05T09:05:00Z"
    assert preview.last_timestamp == "2026-09-25T22:20:00Z"
    source = json.loads(raw)
    zone = ZoneInfo("America/Santo_Domingo")
    expected = []
    repeated_result_count = 0
    for date, rows in source["sorteos_por_fecha"].items():
        for row in rows:
            assert set(row) == {"hora", "numeros", "source_url"}
            draw_id = f"{date} {row['hora']}"
            local = datetime.strptime(f"{date}T{row['hora']}:00", "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=zone
            )
            timestamp = local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            results = tuple(int(number) for number in row["numeros"])
            repeated_result_count += len(results) - len(set(results))
            expected.append((draw_id, timestamp, results))
    assert len(expected) == 105_426
    expected.sort(key=lambda item: (item[1], item[0]))
    actual = [(draw.draw_id, draw.timestamp, draw.results) for draw in preview.draws]
    assert actual == expected
    assert all(len(draw.results) == 5 for draw in preview.draws)
    assert all(all(0 <= value < 100 for value in draw.results) for draw in preview.draws)
    assert sum(len(draw.results) - len(set(draw.results)) for draw in preview.draws) == (
        repeated_result_count
    )
    assert b"source_url" not in preview.canonical_json.encode("utf-8")
    reference = source_reference(preview)
    assert reference.origin == "included"
    assert reference.raw_sha256 == HISTORY_SHA256
    assert reference.rankings_sha256 is None
    assert RANKINGS_SHA256 == "b405041fff1f45fe24fd9ab09fed2c6709e979576811c703e7d27e57f3ded94d"
