"""Private v5 composition, batch codec, and authenticated session tests."""

import hashlib
import json
from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from laboratorio.domain.contracts import SettlementMode, legacy_quiniela_80_profile
from laboratorio.domain.profile_archive import bind_archived_dataset
from laboratorio.domain.profile_request import (
    ProfileExperimentRequest,
    load_profile_request,
    profile_sha256,
    serialize_profile_request,
)
from laboratorio.domain.profile_request_v5 import (
    ProfileBatchRequestV5,
    load_profile_batch_v5,
    serialize_profile_batch_v5,
)
from laboratorio.domain.profile_result_v5 import (
    load_profile_batch_result_v5,
    serialize_profile_batch_result_v5,
    validate_profile_batch_result_v5,
)
from laboratorio.domain.profile_session import ProfileConditions, ProfileSelector, ProfileStaking
from laboratorio.domain.profile_session_v5 import run_profile_batch_v5
from laboratorio.domain.profile_strategy import StrategyDefinition
from laboratorio.importing.datasets import SavedDataset
from laboratorio.importing.records import ImportedRecord, ImportPreview
from laboratorio.settings import Settings


def _archive_fixture(tmp_path, monkeypatch):
    rows = [("2025-01-01", f"00:{i:02d}", (i, 1, 2, 3, 4)) for i in range(4)]
    raw = json.dumps(
        {
            "sorteos_por_fecha": {
                "2025-01-01": [
                    {"hora": time, "numeros": [f"{number:02d}" for number in numbers]}
                    for _, time, numbers in rows
                ]
            }
        }
    ).encode()
    source_sha = hashlib.sha256(raw).hexdigest()
    ranking_path = tmp_path / "rankings.npz"
    row_ids = np.asarray([0, 2, 3], dtype=np.int64)
    timestamps = np.asarray([f"{rows[i][0]} {rows[i][1]}" for i in row_ids])
    cold = np.tile(np.arange(100, dtype=np.uint8), (3, 1))
    transition = np.tile(np.arange(99, -1, -1, dtype=np.uint8), (3, 1))
    transition[1] = np.roll(transition[1], 1)
    with ranking_path.open("wb") as stream:
        np.savez(
            stream,
            row_ids=row_ids,
            timestamps=timestamps,
            ranking100__cold=cold,
            ranking100__transition=transition,
            ranking100__freq_hist=np.roll(cold, 2, axis=1),
            ranking100__topk=np.roll(cold, 1, axis=1),
        )
    rankings_sha = hashlib.sha256(ranking_path.read_bytes()).hexdigest()
    monkeypatch.setattr("laboratorio.engine.adapter.HISTORY_SHA256", source_sha)
    monkeypatch.setattr("laboratorio.engine.adapter.RANKINGS_SHA256", rankings_sha)
    settings = Settings(tmp_path, tmp_path / "history.json", ranking_path, tmp_path / "dist")
    settings.history_path.write_bytes(raw)
    records = tuple(ImportedRecord(day, time, numbers) for day, time, numbers in rows)
    canonical = json.dumps(
        {"profile": legacy_quiniela_80_profile().model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    dataset_sha = hashlib.sha256(canonical).hexdigest()
    preview = ImportPreview(records, source_sha, dataset_sha, len(rows), 0, (), 0, False, True)
    dataset = SavedDataset(dataset_sha, source_sha, canonical, raw, "fixture", preview)
    return bind_archived_dataset(dataset, settings), dataset


def _request(profile, dataset_sha, definition, start="2025-01-01 00:00", max_draws=10):
    return ProfileBatchRequestV5(
        5,
        "profile_batch",
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        dataset_sha,
        ProfileConditions(1, start, 2_000, 2_800, SettlementMode.ALL),
        (definition,),
        max_draws,
    )


def test_closed_definition_and_canonical_batch_codec_reject_legacy_versions():
    profile = legacy_quiniela_80_profile()
    definition = StrategyDefinition.reference_transition_audaz()
    request = _request(profile, "a" * 64, definition)
    wire = serialize_profile_batch_v5(request)
    assert load_profile_batch_v5(wire) == request
    assert serialize_profile_batch_v5(load_profile_batch_v5(wire)) == wire
    with pytest.raises(FrozenInstanceError):
        definition.__setattr__("coverage", 50)
    raw = json.loads(wire)
    raw["extra"] = True
    with pytest.raises(ValueError, match="exactly"):
        load_profile_batch_v5(json.dumps(raw))
    with pytest.raises(ValueError, match="duplicate"):
        load_profile_batch_v5(wire[:-1] + ',"kind":"profile"}')

    legacy = ProfileExperimentRequest(
        "profile",
        1,
        "legacy",
        "a" * 64,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        ProfileConditions(1, "2025-01-01 00:00", 2_000, 2_800, SettlementMode.ALL),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(7,)),
        ProfileStaking(1, "flat-per-number/v1", 1),
        "all_rows/v1",
    )
    old_wire = serialize_profile_request(legacy)
    assert load_profile_request(old_wire) == legacy
    with pytest.raises(ValueError, match="version"):
        load_profile_batch_v5(old_wire)


def test_archive_session_requires_ranked_start_and_skips_gap_rows(tmp_path, monkeypatch):
    binding, dataset = _archive_fixture(tmp_path, monkeypatch)
    profile = legacy_quiniela_80_profile()
    definition = StrategyDefinition.reference_cold_25()
    request = _request(profile, dataset.dataset_sha256, definition, "2025-01-01 00:01")
    with pytest.raises(ValueError, match="ranked start"):
        run_profile_batch_v5(request, profile, dataset, binding, operation_budget=10)

    request = replace(
        request, conditions=replace(request.conditions, start_draw="2025-01-01 00:00")
    )
    batch = run_profile_batch_v5(request, profile, dataset, binding, operation_budget=10)
    result = batch.results[0]
    assert result.ordinal == 0
    assert result.session.elapsed_draws == 4
    assert [bet.label for bet in result.session.bets] == [
        "2025-01-01 00:00",
        "2025-01-01 00:02",
        "2025-01-01 00:03",
    ]
    assert result.prior_cutoff is None
    validated = validate_profile_batch_result_v5(
        result=batch,
        request=request,
        profile=profile,
        dataset=dataset,
        binding=binding,
        operation_budget=10,
    )
    wire = serialize_profile_batch_result_v5(validated)
    assert load_profile_batch_result_v5(wire) == batch
    tampered_session = replace(result.session, final_balance=result.session.final_balance + 1)
    tampered_item = replace(result, session=tampered_session)
    tampered_batch = replace(batch, results=(tampered_item,))
    with pytest.raises(ValueError, match="replay"):
        validate_profile_batch_result_v5(
            tampered_batch, request, profile, dataset, binding, operation_budget=10
        )


def test_reference_parity_uses_full_causal_history_and_settlement(tmp_path, monkeypatch):
    binding, dataset = _archive_fixture(tmp_path, monkeypatch)
    profile = legacy_quiniela_80_profile()
    definition = StrategyDefinition.reference_parity_50()
    request = _request(profile, dataset.dataset_sha256, definition, "2025-01-01 00:02")
    batch = run_profile_batch_v5(request, profile, dataset, binding, operation_budget=10)
    result = batch.results[0]
    expected = binding.select("parity", 2, 50)
    assert result.session.bets[0].stakes == tuple((number, 1) for number in expected)
    assert result.prior_cutoff == "2025-01-01 00:01"
    assert result.session.bets[0].wagered == 50


def test_v5_operation_budget_does_not_apply_legacy_source_row_ceiling(tmp_path, monkeypatch):
    binding, dataset = _archive_fixture(tmp_path, monkeypatch)
    profile = legacy_quiniela_80_profile()
    request = _request(
        profile,
        dataset.dataset_sha256,
        StrategyDefinition.reference_transition_audaz(),
        max_draws=2,
    )
    with pytest.raises(ValueError, match="operation budget"):
        run_profile_batch_v5(request, profile, dataset, binding, operation_budget=1)


def test_batch_rejects_duplicate_names_invalid_limits_and_close_override():
    profile = legacy_quiniela_80_profile()
    definition = StrategyDefinition.reference_cold_25()
    request = _request(profile, "a" * 64, definition)
    with pytest.raises(ValueError, match="unique"):
        replace(request, strategies=(definition, replace(definition, name=" FRIOS_25_ESCALERA ")))
    with pytest.raises(ValueError, match="max_draws"):
        replace(request, max_draws=True)
    different_close = replace(
        definition, closing_defaults=(("max_bet_draws", 2), ("settlement", "all"))
    )
    assert replace(request, strategies=(different_close,)).strategies == (different_close,)
    incompatible_settlement = replace(definition, closing_defaults=(("settlement", "best"),))
    with pytest.raises(ValueError, match="settlement recommendation"):
        replace(request, strategies=(incompatible_settlement,))


def test_v5_codecs_reject_unknown_nested_fields_and_result_version(tmp_path, monkeypatch):
    binding, dataset = _archive_fixture(tmp_path, monkeypatch)
    profile = legacy_quiniela_80_profile()
    request = _request(
        profile,
        dataset.dataset_sha256,
        StrategyDefinition.reference_parity_50(),
        "2025-01-01 00:02",
    )
    wire = serialize_profile_batch_v5(request)
    raw = json.loads(wire)
    raw["strategies"][0]["selector_parameters"]["eval"] = "not supported"
    with pytest.raises(ValueError, match="unknown selector"):
        load_profile_batch_v5(json.dumps(raw))
    result = run_profile_batch_v5(request, profile, dataset, binding, operation_budget=10)
    raw_result = json.loads(serialize_profile_batch_result_v5(result))
    raw_result["schema_version"] = 4
    with pytest.raises(ValueError, match="version"):
        load_profile_batch_result_v5(json.dumps(raw_result))


def test_transition_reference_definition_rejects_invalid_coverage():
    transition = StrategyDefinition.reference_transition_audaz()
    assert transition.selector == "archived-transition/v1"
    assert transition.staking == "q80-reference-audaz/v1"
    with pytest.raises(ValueError, match="coverage one"):
        StrategyDefinition(
            1,
            "bad reference",
            "archived-transition/v1",
            2,
            "q80-reference-audaz/v1",
            (("system", "transition"),),
            (),
            (("settlement", "all"),),
        )


def test_generic_audaz_coverage_uses_profile_domain_not_q80_reference_limit():
    for coverage in (79, 80, 100, 101, 1_000):
        definition = StrategyDefinition(
            1,
            f"audaz {coverage}",
            "static-numbers/v1",
            coverage,
            "profile-audaz/v1",
            (("numbers", tuple(range(coverage))),),
        )
        assert definition.coverage == coverage
    with pytest.raises(ValueError, match="coverage"):
        StrategyDefinition(
            1,
            "audaz 1001",
            "static-numbers/v1",
            1_001,
            "profile-audaz/v1",
            (("numbers", tuple(range(1_001))),),
        )
    for coverage in (1, 79):
        StrategyDefinition(
            1,
            f"q80 {coverage}",
            "static-numbers/v1",
            coverage,
            "q80-first-prize-cycling/v1",
            (("numbers", tuple(range(coverage))),),
        )
    with pytest.raises(ValueError, match="Q80 cycling"):
        StrategyDefinition(
            1,
            "q80 80",
            "static-numbers/v1",
            80,
            "q80-first-prize-cycling/v1",
            (("numbers", tuple(range(80))),),
        )
    archived_100 = StrategyDefinition(
        1,
        "archived 100",
        "archived-transition/v1",
        100,
        "flat-per-number/v1",
        (("system", "transition"),),
        (("per_number_stake", 1),),
    )
    assert archived_100.coverage == 100
    with pytest.raises(ValueError, match="archived selector coverage"):
        replace(archived_100, coverage=101)


def test_custom_1000_universe_flat_and_profile_audaz_run_one_draw():
    from laboratorio.domain.contracts import GameProfile

    values = legacy_quiniela_80_profile().model_dump(mode="python")
    values.update(
        profile_id="wide-profile",
        best_rule="maximum-payout/v1",
        universe_size=1_000,
        positions=1,
        allows_repeats=False,
        multipliers=[{"numerator": 1_001, "denominator": 1}],
        minimum_stake=1,
        stake_increment=1,
        maximum_stake=100,
        max_coverage=1_000,
        max_exposure=100_000,
    )
    profile = GameProfile.model_validate(values)
    raw = b"one checked draw"
    source_sha = hashlib.sha256(raw).hexdigest()
    records = (ImportedRecord("2025-01-01", "00:00", (999,)),)
    canonical = json.dumps(
        {"profile": profile.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    dataset_sha = hashlib.sha256(canonical).hexdigest()
    preview = ImportPreview(records, source_sha, dataset_sha, 1, 0, (), 0, False, True)
    dataset = SavedDataset(dataset_sha, source_sha, canonical, raw, "fixture", preview)
    numbers = tuple(range(1_000))
    definitions = (
        StrategyDefinition.static_numbers("wide flat", numbers, stake=1),
        StrategyDefinition(
            1,
            "wide audaz",
            "static-numbers/v1",
            1_000,
            "profile-audaz/v1",
            (("numbers", numbers),),
        ),
    )
    request = _request(profile, dataset_sha, definitions[0], max_draws=1)
    request = replace(request, strategies=definitions)
    batch = run_profile_batch_v5(request, profile, dataset, None, operation_budget=1)
    assert [result.session.bet_draws for result in batch.results] == [1, 1]
    assert [result.session.bets[0].wagered for result in batch.results] == [1_000, 2_000]
    assert all(len(result.session.bets[0].stakes) == 1_000 for result in batch.results)


def test_v5_recovery_round_limit_result_round_trips_and_replays(tmp_path):
    from laboratorio.domain.contracts import GameProfile

    values = legacy_quiniela_80_profile().model_dump(mode="python")
    values.update(
        profile_id="single-prize",
        best_rule="maximum-payout/v1",
        universe_size=10,
        positions=1,
        allows_repeats=False,
        multipliers=[{"numerator": 4, "denominator": 1}],
        max_coverage=3,
        max_exposure=100_000,
        maximum_stake=100,
    )
    profile = GameProfile.model_validate(values)
    raw = b"checked custom history"
    source_sha = hashlib.sha256(raw).hexdigest()
    records = tuple(ImportedRecord("2025-01-01", f"00:0{i}", (7,)) for i in range(2))
    canonical = json.dumps(
        {"profile": profile.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    dataset_sha = hashlib.sha256(canonical).hexdigest()
    preview = ImportPreview(records, source_sha, dataset_sha, 2, 0, (), 0, False, True)
    dataset = SavedDataset(dataset_sha, source_sha, canonical, raw, "fixture", preview)
    definition = StrategyDefinition(
        1,
        "recovery stop",
        "static-numbers/v1",
        3,
        "profile-recovery-ladder/v1",
        (("numbers", (0, 1, 2)),),
        (("end_mode", "stop"), ("rounds", 2), ("target_margin", 10)),
    )
    request = _request(profile, dataset_sha, definition, max_draws=2)
    request = replace(
        request,
        conditions=replace(request.conditions, capital=5_000, goal=6_000, max_bet_draws=2),
    )
    batch = run_profile_batch_v5(request, profile, dataset, None, operation_budget=2)
    assert [bet.stakes[0][1] for bet in batch.results[0].session.bets] == [10, 40]
    assert batch.results[0].session.collisions == ("recovery_round_limit", "max_bet_draws")
    wire = serialize_profile_batch_result_v5(batch)
    assert load_profile_batch_result_v5(wire) == batch
    assert (
        validate_profile_batch_result_v5(batch, request, profile, dataset, None, operation_budget=2)
        == batch
    )
    raw_result = json.loads(wire)
    raw_result["results"][0]["session"]["collisions"].append("unknown-limit")
    with pytest.raises(ValueError, match="invalid collisions"):
        load_profile_batch_result_v5(json.dumps(raw_result))
    tampered_collision = replace(
        batch,
        results=(
            replace(
                batch.results[0],
                session=replace(batch.results[0].session, collisions=("max_bet_draws",)),
            ),
        ),
    )
    with pytest.raises(ValueError, match="replay"):
        validate_profile_batch_result_v5(
            tampered_collision, request, profile, dataset, None, operation_budget=2
        )
    bets = batch.results[0].session.bets
    tampered_round = replace(
        batch,
        results=(
            replace(
                batch.results[0],
                session=replace(
                    batch.results[0].session,
                    bets=(bets[0], replace(bets[1], stakes=((0, 30), (1, 30), (2, 30)))),
                ),
            ),
        ),
    )
    with pytest.raises(ValueError):
        validate_profile_batch_result_v5(
            tampered_round, request, profile, dataset, None, operation_budget=2
        )
    tampered_conditions = replace(request, conditions=replace(request.conditions, max_bet_draws=1))
    with pytest.raises(ValueError, match="replay"):
        validate_profile_batch_result_v5(
            batch, tampered_conditions, profile, dataset, None, operation_budget=2
        )


def test_v5_closing_defaults_do_not_override_shared_conditions_on_replay(tmp_path, monkeypatch):
    binding, dataset = _archive_fixture(tmp_path, monkeypatch)
    profile = legacy_quiniela_80_profile()
    first = replace(
        StrategyDefinition.static_numbers("static one", (0,), stake=1),
        closing_defaults=(("max_bet_draws", 2),),
    )
    second = replace(
        StrategyDefinition.static_numbers("static two", (0,), stake=1),
        closing_defaults=(("max_bet_draws", 3),),
    )
    base = StrategyDefinition.static_numbers("base", (0,), stake=1)
    request = _request(profile, dataset.dataset_sha256, base)
    request = replace(
        request,
        conditions=replace(request.conditions, max_bet_draws=1, settlement=SettlementMode.BEST),
        strategies=(first, second),
    )
    request_wire = serialize_profile_batch_v5(request)
    loaded_request = load_profile_batch_v5(request_wire)
    assert loaded_request == request
    preset = StrategyDefinition.reference_cold_25()
    with pytest.raises(ValueError, match="settlement recommendation"):
        replace(request, strategies=(preset,))
    with pytest.raises(ValueError, match="settlement recommendation"):
        replace(
            request,
            strategies=(replace(first, closing_defaults=(("settlement", "all"),)), second),
        )
    batch = run_profile_batch_v5(request, profile, dataset, binding, operation_budget=10)
    assert [len(item.session.bets) for item in batch.results] == [1, 1]
    assert batch.results[0].session == batch.results[1].session
    assert [item.session.collisions for item in batch.results] == [
        ("max_bet_draws",),
        ("max_bet_draws",),
    ]
    assert [item.definition.closing_defaults for item in batch.results] == [
        (("max_bet_draws", 2),),
        (("max_bet_draws", 3),),
    ]
    assert (
        validate_profile_batch_result_v5(
            batch, request, profile, dataset, binding, operation_budget=10
        )
        == batch
    )
