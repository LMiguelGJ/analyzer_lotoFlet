import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from laboratorio.api.strategies import router
from laboratorio.domain.profile_strategy import StrategyDefinition
from laboratorio.domain.strategy_library import (
    definition_snapshot,
    seed_presets,
    strategy_payload,
)
from laboratorio.storage.database import initialize_database
from laboratorio.storage.quota import LOGICAL_MARGIN_BYTES, QuotaExceeded
from laboratorio.storage.repository import Repository


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "library.db"
    initialize_database(path)
    return Repository(path)


def disk(_):
    return SimpleNamespace(free=2 * 1024**3)


def definition(name="mi estrategia"):
    return StrategyDefinition.static_numbers(name, (7, 13))


def test_closed_definition_codec_and_canonical_hash():
    definition_json, digest = definition_snapshot(definition("áurea"))
    assert json.loads(definition_json)["name"] == "áurea"
    assert digest == hashlib.sha256(definition_json.encode("utf-8")).hexdigest()
    with pytest.raises(ValueError):
        strategy_payload({"definition_version": 1, "unrecognized": True})


def test_create_page_reopen_preserves_exact_snapshot_hash_and_execution_state(repo):
    created = repo.create_strategy(definition(), disk_usage=disk)
    assert created["revision"] == 1
    assert (
        created["definition_sha256"]
        == hashlib.sha256(created["definition_json"].encode("utf-8")).hexdigest()
    )
    assert repo.page_strategies(0, 100)[0] == 1
    reopened = Repository(repo.path).get_strategy(created["id"])
    assert reopened is not None
    assert reopened == created
    assert reopened["execution_available"] is False
    assert "ProfileBatchRequestV5" in reopened["execution_unavailable_reason"]


def test_append_is_cas_and_old_revision_is_immutable(repo):
    first = repo.create_strategy(definition(), disk_usage=disk)
    second = repo.append_strategy_revision(first["id"], 1, definition("variante"), disk_usage=disk)
    assert second["revision"] == 2
    assert repo.get_strategy_revision(first["id"], 1)["definition_json"] == first["definition_json"]
    with pytest.raises(ValueError, match="revision conflict"):
        repo.append_strategy_revision(first["id"], 1, definition("lost update"), disk_usage=disk)
    assert repo.get_strategy(first["id"])["latest_revision"] == 2


def test_preset_seed_is_idempotent_and_protected_originals_are_copy_only(repo):
    first = seed_presets(repo, disk_usage=disk)
    again = seed_presets(repo, disk_usage=disk)
    assert [item["id"] for item in first] == [item["id"] for item in again]
    assert len(first) == 3
    with sqlite3.connect(repo.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE strategies SET latest_revision = 2 WHERE id = ?", (first[0]["id"],))
    with pytest.raises(ValueError, match="protected"):
        repo.append_strategy_revision(first[0]["id"], 1, definition("overwrite"), disk_usage=disk)
    copied = repo.create_strategy(definition("mi copia"), disk_usage=disk)
    assert copied["id"] not in {item["id"] for item in first}


def test_invalid_definitions_and_tampered_rows_are_rejected(repo):
    with pytest.raises(ValueError):
        strategy_payload({"definition_version": 1, "name": "x", "unknown": 9})
    saved = repo.create_strategy(definition(), disk_usage=disk)
    assert saved is not None
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER strategy_revisions_no_update")
        db.execute(
            "UPDATE strategy_revisions SET definition_json = '{}' WHERE strategy_id = ?",
            (saved["id"],),
        )
    with pytest.raises(ValueError, match="corrupt"):
        repo.get_strategy(saved["id"])


def test_exact_utf8_quota_and_failed_transaction_rollback(repo):
    saved = repo.create_strategy(definition("estrategia ñ"), disk_usage=disk)
    expected = (
        len(saved["id"].encode("utf-8"))
        + len(saved["name"].encode("utf-8"))
        + len(saved["created_at"].encode("utf-8"))
        + 9
        + len(saved["id"].encode("utf-8"))
        + 16
        + len(saved["definition_sha256"].encode("utf-8"))
        + len(saved["definition_json"].encode("utf-8"))
        + len(saved["revision_created_at"].encode("utf-8"))
    )
    assert repo.strategy_artifact_bytes() == expected
    other_path = repo.path.parent / "rollback.db"
    initialize_database(other_path)
    other = Repository(other_path)
    limit = next(
        candidate
        for candidate in range(expected + 1, 2 * expected + 100)
        if candidate - min(LOGICAL_MARGIN_BYTES, max(1, candidate // 20)) == expected
    )
    with pytest.raises(QuotaExceeded):
        other.create_strategy(definition("estrategia ñ"), quota_bytes=limit, disk_usage=disk)
    assert other.strategy_artifact_bytes() == 0
    with sqlite3.connect(other.path) as db:
        db.execute(
            "CREATE TRIGGER reject_strategy BEFORE INSERT ON strategies "
            "BEGIN SELECT RAISE(ABORT, 'reject'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="reject"):
        other.create_strategy(definition(), disk_usage=disk)
    assert other.strategy_artifact_bytes() == 0


def test_profile_compatibility_is_contextual_and_presets_require_exact_reference():
    from test_import_records import profile

    from laboratorio.domain.strategy_library import compatibility_projection

    saved_profile = profile()
    report = compatibility_projection(definition(), saved_profile)
    assert report["profile_compatible"] is True
    preset = StrategyDefinition.reference_parity_50()
    assert (
        compatibility_projection(
            preset, saved_profile, reference_preset_id="preset-paridad-50-plana"
        )["profile_compatible"]
        is False
    )


def test_startup_seeds_presets_and_mounts_strategy_api(tmp_path):
    from fastapi.testclient import TestClient

    from laboratorio.app import create_app
    from laboratorio.settings import Settings

    class Queue:
        is_stopped = False

        def start(self):
            pass

        def shutdown(self):
            self.is_stopped = True

    settings = Settings(
        data_dir=tmp_path,
        history_path=tmp_path / "unused-history",
        rankings_path=tmp_path / "unused-rankings",
        frontend_dist=tmp_path / "frontend",
        port=8765,
    )
    app = create_app(
        settings,
        catalog_loader=lambda _: None,
        queue_factory=lambda _path, _settings: Queue(),
    )
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        result = client.get("/api/v1/strategies?offset=0&limit=3")
        assert result.status_code == 200
        assert result.json()["total"] == 3
        assert all(item["execution_available"] is False for item in result.json()["items"])


def test_route_uses_closed_body_pagination_and_id_retrieval(repo):
    from fastapi import FastAPI
    from test_import_records import profile

    from laboratorio.domain.profile_request import profile_sha256

    app = FastAPI()
    app.state.repo = repo
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    body = {"definition": json.loads(definition_snapshot(definition())[0])}
    response = client.post("/api/v1/strategies", json={**body, "arbitrary_path": "x"})
    assert response.status_code == 422
    assert (
        client.post(
            "/api/v1/strategies", content="{", headers={"Content-Type": "application/json"}
        ).status_code
        == 422
    )
    response = client.post("/api/v1/strategies", json=body)
    assert response.status_code == 201
    identifier = response.json()["id"]
    assert client.get("/api/v1/strategies/" + identifier).json()["id"] == identifier
    registered = profile()
    repo.create_game_profile(registered, disk_usage=disk)
    context = {
        "profile_id": registered.profile_id,
        "profile_revision": registered.revision,
        "profile_sha256": profile_sha256(registered),
    }
    contextual = client.get("/api/v1/strategies/" + identifier, params=context)
    assert contextual.json()["profile_compatible"] is True
    context["profile_sha256"] = "0" * 64
    assert client.get("/api/v1/strategies/" + identifier, params=context).status_code == 409
    revised = client.post(
        "/api/v1/strategies/" + identifier + "/revisions",
        json={
            "expected_latest_revision": 1,
            "definition": json.loads(definition_snapshot(definition("nueva"))[0]),
        },
    )
    assert revised.status_code == 201 and revised.json()["revision"] == 2
    stale = client.post(
        "/api/v1/strategies/" + identifier + "/revisions",
        json={"expected_latest_revision": 1, "definition": body["definition"]},
    )
    assert stale.status_code == 409
    assert client.get("/api/v1/strategies/" + identifier + "/revisions").json()["total"] == 2
    assert client.get("/api/v1/strategies/missing").status_code == 404
    assert client.get("/api/v1/strategies/missing/revisions").status_code == 404
    assert client.get("/api/v1/strategies?offset=0&limit=100").json()["total"] == 1
    assert client.get("/api/v1/strategies?offset=0&limit=101").status_code == 422


def generic_profile(
    *,
    first_numerator=10,
    first_denominator=2,
    minimum_stake=10,
    maximum_stake=1000,
    max_coverage=1000,
    max_exposure=None,
):
    from laboratorio.domain.contracts import GameProfile, PayoutMultiplier

    return GameProfile(
        schema_version=1,
        profile_id="generic-game",
        revision=1,
        universe_size=1000,
        positions=3,
        allows_repeats=True,
        multipliers=(
            PayoutMultiplier(numerator=first_numerator, denominator=first_denominator),
            PayoutMultiplier(numerator=4, denominator=1),
            PayoutMultiplier(numerator=2, denominator=1),
        ),
        currency="USD",
        scale=2,
        stake_increment=10,
        minimum_stake=minimum_stake,
        maximum_stake=maximum_stake,
        max_coverage=max_coverage,
        max_exposure=(maximum_stake * max_coverage if max_exposure is None else max_exposure),
        best_rule="maximum-payout/v1",
    )


def test_generic_profile_staking_math_is_not_q80_or_fake_capital_admission():
    from laboratorio.domain.strategy_library import compatibility_projection

    profile_value = generic_profile()
    audaz = StrategyDefinition(
        1,
        "audaz genérica",
        "static-numbers/v1",
        2,
        "profile-audaz/v1",
        (("numbers", (4, 8)),),
        (),
        (),
    )
    report = compatibility_projection(audaz, profile_value)
    assert report["profile_compatible"] is True
    assert report["execution_available"] is False
    no_gain_profile = generic_profile(first_numerator=4, first_denominator=2)
    assert compatibility_projection(audaz, no_gain_profile)["profile_compatible"] is False
    assert "first-position" in " ".join(
        compatibility_projection(audaz, no_gain_profile)["incompatibilities"]
    )
    # 1000 is a generic profile-owned coverage limit, not a Q80 ceiling.
    wide = StrategyDefinition.static_numbers("wide", tuple(range(1000)), stake=10)
    assert compatibility_projection(wide, profile_value)["profile_compatible"] is True


def test_generic_recovery_ladder_checks_full_rung_exposure_and_stake_caps():
    from laboratorio.domain.profile_staking import profile_recovery_ladder
    from laboratorio.domain.strategy_library import compatibility_projection

    definition_value = StrategyDefinition(
        1,
        "recovery",
        "static-numbers/v1",
        2,
        "profile-recovery-ladder/v1",
        (("numbers", (4, 8)),),
        (("end_mode", "stop"), ("rounds", 7), ("target_margin", 100)),
        (),
    )
    assert (
        compatibility_projection(definition_value, generic_profile())["profile_compatible"] is True
    )
    report = compatibility_projection(definition_value, generic_profile(maximum_stake=20))
    assert report["profile_compatible"] is False
    assert any("maximum stake" in reason for reason in report["incompatibilities"])
    no_gain = compatibility_projection(
        definition_value, generic_profile(first_numerator=4, first_denominator=2)
    )
    assert no_gain["profile_compatible"] is False
    assert any("first-position" in reason for reason in no_gain["incompatibilities"])
    minimum_stake_definition = StrategyDefinition(
        1,
        "minimum recovery",
        "static-numbers/v1",
        2,
        "profile-recovery-ladder/v1",
        (("numbers", (4, 8)),),
        (("end_mode", "stop"), ("rounds", 1), ("target_margin", 1)),
        (),
    )
    minimum_profile = generic_profile(minimum_stake=20, maximum_stake=20, max_coverage=2)
    assert (
        compatibility_projection(minimum_stake_definition, minimum_profile)["profile_compatible"]
        is True
    )
    assert profile_recovery_ladder(minimum_profile, 2, 1, 1) == (20,)
    late_exposure = compatibility_projection(
        definition_value,
        generic_profile(maximum_stake=500, max_coverage=2, max_exposure=500),
    )
    assert late_exposure["profile_compatible"] is False
    assert any("profile exposure" in reason for reason in late_exposure["incompatibilities"])


def test_reference_identity_is_stable_when_definition_name_changes():
    from dataclasses import replace

    from laboratorio.domain.contracts import legacy_quiniela_80_profile
    from laboratorio.domain.strategy_library import compatibility_projection

    renamed = replace(StrategyDefinition.reference_parity_50(), name="renamed display")
    assert (
        compatibility_projection(
            renamed, generic_profile(), reference_preset_id="preset-paridad-50-plana"
        )["profile_compatible"]
        is False
    )
    with pytest.raises(ValueError, match="reference preset"):
        compatibility_projection(renamed, generic_profile(), reference_preset_id="forged-id")
    changed = replace(renamed, staking_parameters=(("per_number_stake", 2),))
    with pytest.raises(ValueError, match="reference preset"):
        compatibility_projection(
            changed, generic_profile(), reference_preset_id="preset-paridad-50-plana"
        )
    # Copies and variants retain generic profile-math evaluation, not benchmark identity.
    copy = StrategyDefinition.static_numbers("copy", (1, 2), stake=10)
    assert compatibility_projection(copy, generic_profile())["profile_compatible"] is True
    renamed_copy = replace(renamed, name="parity copy")
    from test_import_records import profile

    assert compatibility_projection(renamed_copy, profile())["profile_compatible"] is True
    assert (
        compatibility_projection(
            renamed, legacy_quiniela_80_profile(), reference_preset_id="preset-paridad-50-plana"
        )["profile_compatible"]
        is True
    )


def test_replace_cannot_mutate_any_existing_strategy_head(repo):
    preset = seed_presets(repo, disk_usage=disk)[0]
    custom = repo.create_strategy(definition(), disk_usage=disk)
    with sqlite3.connect(repo.path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA recursive_triggers=OFF")
        for strategy in (preset, custom):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                db.execute(
                    "INSERT OR REPLACE INTO strategies VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        strategy["id"],
                        strategy["name"],
                        strategy["created_at"],
                        int(strategy["protected"]),
                        strategy["preset_explanation"],
                        strategy["latest_revision"],
                    ),
                )
    assert repo.get_strategy(preset["id"])["protected"] is True
    assert (
        repo.get_strategy_revision(preset["id"], 1)["definition_json"] == preset["definition_json"]
    )


def test_strategy_read_endpoints_map_stored_corruption_to_409(repo):
    from fastapi import FastAPI
    from test_import_records import profile

    from laboratorio.domain.profile_request import profile_sha256

    app = FastAPI()
    app.state.repo = repo
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    saved = repo.create_strategy(definition(), disk_usage=disk)
    identifier = saved["id"]
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER strategy_revisions_no_update")
        db.execute(
            "UPDATE strategy_revisions SET definition_json = '{}' WHERE strategy_id = ?",
            (identifier,),
        )
    assert client.get("/api/v1/strategies").status_code == 409
    assert client.get(f"/api/v1/strategies/{identifier}").status_code == 409
    assert client.get(f"/api/v1/strategies/{identifier}/revisions").status_code == 409

    registered = profile()
    repo.create_game_profile(registered, disk_usage=disk)
    profile_identifier = repo.create_strategy(definition("profile corruption"), disk_usage=disk)[
        "id"
    ]
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER game_profiles_no_update")
        db.execute(
            "UPDATE game_profiles SET profile_json = '{}' WHERE profile_id = ? AND revision = ?",
            (registered.profile_id, registered.revision),
        )
    params = {
        "profile_id": registered.profile_id,
        "profile_revision": registered.revision,
        "profile_sha256": profile_sha256(registered),
    }
    response = client.get(f"/api/v1/strategies/{profile_identifier}", params=params)
    assert response.status_code == 409
    assert "{}" not in response.text


def test_unknown_protected_identity_is_rejected_on_get_and_list(repo):
    saved = repo.create_strategy(definition(), disk_usage=disk)
    with sqlite3.connect(repo.path) as db:
        db.execute(
            "UPDATE strategies SET protected = 1, preset_explanation = 'forged' WHERE id = ?",
            (saved["id"],),
        )
    with pytest.raises(ValueError, match="protected preset"):
        repo.get_strategy(saved["id"])
    with pytest.raises(ValueError, match="protected preset"):
        repo.page_strategies(0, 100)


def test_known_preset_reads_reject_forged_definition_with_recomputed_hash(repo):
    from dataclasses import replace

    preset = seed_presets(repo, disk_usage=disk)[0]
    forged = replace(preset["definition"], staking_parameters=(("per_number_stake", 2),))
    serialized, digest = definition_snapshot(forged)
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER strategy_revisions_no_update")
        db.execute(
            "UPDATE strategy_revisions SET definition_json = ?, definition_sha256 = ? "
            "WHERE strategy_id = ? AND revision = 1",
            (serialized, digest, preset["id"]),
        )
    with pytest.raises(ValueError, match="protected preset"):
        repo.get_strategy(preset["id"])
    with pytest.raises(ValueError, match="protected preset"):
        repo.get_strategy_revision(preset["id"], 1)
    with pytest.raises(ValueError, match="protected preset"):
        repo.page_strategies(0, 100)
