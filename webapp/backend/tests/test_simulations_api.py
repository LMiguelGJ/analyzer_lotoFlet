"""Unified simulation-list API contract tests using isolated temporary databases."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_batch_admission import _saved_inputs

from laboratorio.domain.batch_admission import admit_profile_batch
from laboratorio.settings import Settings


class CatalogStub:
    def __init__(self):
        self.history = SimpleNamespace(
            labels=("2025-01-01 05:10", "2025-01-01 05:15"), sha256="a" * 64
        )
        self.rankings = SimpleNamespace(row_ids=(0,), path="rankings.npz")


def test_unified_simulation_listing_exists_with_bounded_page_contract(tmp_path):
    from laboratorio.app import create_app

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    app = create_app(settings, catalog_loader=lambda _: CatalogStub())
    with TestClient(app, base_url=f"http://localhost:{settings.port}") as client:
        response = client.get("/api/v1/simulations?offset=0&limit=10")
        denied_host = client.get("/api/v1/simulations", headers={"Host": "evil.example"})
        denied_origin = client.get(
            "/api/v1/simulations", headers={"Origin": "https://evil.example"}
        )

    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "offset": 0,
        "limit": 10,
        "items": [],
    }
    assert denied_host.status_code == denied_origin.status_code == 403


def _client(tmp_path):
    from laboratorio.app import create_app

    settings = Settings(
        tmp_path / "data", tmp_path / "history.json", tmp_path / "rankings.npz", tmp_path
    )
    app = create_app(settings, catalog_loader=lambda _: CatalogStub())
    return app, TestClient(app, base_url=f"http://localhost:{settings.port}")


def _add_classic(app, name, created_at=None):
    from laboratorio.domain.contracts import (
        Conditions,
        ExperimentRequest,
        SelectorKind,
        StakingStyle,
        Strategy,
    )

    request = ExperimentRequest(
        name=name,
        conditions=Conditions(start_draw="2025-01-01 05:10", capital=100, goal=200, seed=42),
        strategies=(
            Strategy(
                name=name,
                selector=SelectorKind.SYSTEM,
                system="cold",
                coverage=1,
                staking=StakingStyle.FLAT,
            ),
        ),
    )
    identifier = app.state.repo.create_experiment(
        request,
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="test",
    )
    if created_at is not None:
        from laboratorio.storage.database import connection

        with connection(app.state.repo.path) as db:
            db.execute(
                "UPDATE experiments SET created_at = ? WHERE id = ?",
                (created_at, identifier),
            )
            db.commit()
    return identifier


def test_populated_pagination_beyond_last_page_keeps_true_total(tmp_path):
    app, client = _client(tmp_path)
    with client:
        _add_classic(app, "Classic")
        response = client.get("/api/v1/simulations?offset=999&limit=1")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"] == []


def _add_backtest(app, name, identifier, created_at):
    import json

    from laboratorio.storage.database import connection

    config = {
        "strategy": {
            "name": name,
            "selector": "system",
            "system": "transition",
            "coverage": 1,
            "staking": "flat",
        },
        "game": {"numbers": 10, "positions": 5, "prizes": [80, 8, 4, 2, 1], "min_stake": 1},
        "conditions": {"capital": 10, "goal": 20},
        "inputs": {"history_sha256": "a" * 64, "rankings_sha256": "b" * 64},
        "name": name,
    }
    result = {
        "reached_goal": 1,
        "completed": 1,
        "goal_rate": 100.0,
        "quiebres": 0,
        "neto_medio": 1.0,
        "incomplete": 0,
        "window": {"bets": 1, "wagered": 1, "paid": 2, "sessions": 1, "incomplete": 0},
    }
    with connection(app.state.repo.path) as db:
        db.execute(
            "INSERT INTO backtests VALUES (?, ?, ?, ?, ?)",
            (
                identifier,
                name,
                json.dumps(config),
                json.dumps(result),
                created_at,
            ),
        )
        db.commit()


def test_name_filter_treats_percent_and_underscore_as_literals(tmp_path):
    app, client = _client(tmp_path)
    with client:
        _add_classic(app, "A_B")
        _add_classic(app, "AB")
        _add_classic(app, "100%")
        underscore = client.get("/api/v1/simulations?name_contains=%5F").json()
        percent = client.get("/api/v1/simulations?name_contains=%25").json()

    assert {item["name"] for item in underscore["items"]} == {"A_B"}
    assert underscore["total"] == 1
    assert {item["name"] for item in percent["items"]} == {"100%"}
    assert percent["total"] == 1


def test_global_name_filter_sort_and_ties_merge_classics_and_backtests(tmp_path):
    app, client = _client(tmp_path)
    with client:
        first = _add_classic(app, "Alpha", "2025-01-01T00:00:00Z")
        second = _add_classic(app, "Beta", "2025-01-01T00:00:00Z")
        _add_backtest(app, "Alpha historical", first, "2025-01-01T00:00:00Z")
        page = client.get("/api/v1/simulations?sort=created_at&order=asc&limit=2").json()
        filtered = client.get("/api/v1/simulations?name_contains=alpha&sort=name&order=asc").json()
        literal = client.get("/api/v1/simulations?name_contains=%25").json()

    assert page["total"] == 3
    assert [(item["source_kind"], item["id"]) for item in page["items"]] == [
        ("backtest", first),
        ("experiment", min(first, second)),
    ]
    assert filtered["total"] == 2
    assert {item["name"] for item in filtered["items"]} == {"Alpha", "Alpha historical"}
    assert literal["total"] == 0


def test_v5_batch_uses_display_name_and_same_snapshot_dataset_loader(tmp_path, monkeypatch):
    from dataclasses import replace

    import laboratorio.storage.repository as repository

    app, client = _client(tmp_path)
    with client:
        _, _, _, _, submission = _saved_inputs(app.state.repo, row_count=4)
        identifier = admit_profile_batch(app.state.repo, submission)
        second = admit_profile_batch(
            app.state.repo, replace(submission, client_request_id="second-batch")
        )
        calls = 0
        check_dataset = repository.checked_dataset

        def count_dataset_checks(row):
            nonlocal calls
            calls += 1
            return check_dataset(row)

        monkeypatch.setattr(repository, "checked_dataset", count_dataset_checks)
        monkeypatch.setattr(
            app.state.repo,
            "get_dataset",
            lambda _: pytest.fail("simulation listing opened a second dataset connection"),
        )
        response = client.get("/api/v1/simulations?scope=profile&name_contains=static%20low%20risk")

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    assert {item["id"] for item in response.json()["items"]} == {identifier, second}
    assert {item["name"] for item in response.json()["items"]} == {"Static low risk"}
    assert calls == 1


def test_off_page_structural_experiment_corruption_fails_complete_listing(tmp_path):
    from laboratorio.storage.database import connection

    app, client = _client(tmp_path)
    with client:
        _add_classic(app, "Visible")
        damaged_id = _add_classic(app, "Off page damaged")
        with connection(app.state.repo.path) as db:
            db.execute("UPDATE experiments SET request_json = '{' WHERE id = ?", (damaged_id,))
            db.commit()
        response = client.get("/api/v1/simulations?limit=1")

    assert response.status_code == 409
    assert response.json()["detail"] == "A stored simulation is damaged and cannot be shown."


def test_off_page_structural_backtest_corruption_fails_complete_listing(tmp_path):
    from laboratorio.storage.database import connection

    app, client = _client(tmp_path)
    with client:
        _add_classic(app, "Visible")
        _add_backtest(app, "Corrupt later", "corrupt-backtest", "2025-01-01T00:00:00Z")
        with connection(app.state.repo.path) as db:
            db.execute("UPDATE backtests SET config_json = '[]'")
            db.commit()
        response = client.get("/api/v1/simulations?limit=1")

    assert response.status_code == 409
    assert response.json()["detail"] == "A stored simulation is damaged and cannot be shown."


def test_filtered_out_eligible_classic_domain_corruption_fails_listing(tmp_path):
    from laboratorio.storage.database import connection

    app, client = _client(tmp_path)
    with client:
        _add_classic(app, "Visible")
        damaged_id = _add_classic(app, "Hidden damaged request")
        with connection(app.state.repo.path) as db:
            db.execute(
                "UPDATE experiments SET request_json = "
                "json_set(request_json, '$.conditions.start_draw', 'not-a-draw') WHERE id = ?",
                (damaged_id,),
            )
            db.commit()
        response = client.get("/api/v1/simulations?name_contains=Visible")

    assert response.status_code == 409
    assert response.json()["detail"] == "A stored simulation is damaged and cannot be shown."


def test_filtered_out_backtest_contract_corruption_fails_listing(tmp_path):
    import json

    from laboratorio.storage.database import connection

    app, client = _client(tmp_path)
    with client:
        _add_classic(app, "Visible")
        _add_backtest(app, "Hidden damaged backtest", "bad-backtest", "2025-01-01T00:00:00Z")
        with connection(app.state.repo.path) as db:
            config = json.loads(
                db.execute(
                    "SELECT config_json FROM backtests WHERE id = 'bad-backtest'"
                ).fetchone()[0]
            )
            config["strategy"]["selector"] = "unknown"
            db.execute(
                "UPDATE backtests SET config_json = ? WHERE id = 'bad-backtest'",
                (json.dumps(config),),
            )
            db.commit()
        response = client.get("/api/v1/simulations?name_contains=Visible")

    assert response.status_code == 409
    assert response.json()["detail"] == "A stored simulation is damaged and cannot be shown."


@pytest.mark.parametrize(
    ("corrupt_config", "case"),
    [
        (lambda config: config["conditions"].update(goal=config["conditions"]["capital"]), "goal"),
        (lambda config: config["game"].update(prizes=[80]), "prize_count"),
    ],
)
def test_filtered_out_backtest_domain_config_corruption_fails_listing(
    tmp_path, corrupt_config, case
):
    import json

    from laboratorio.storage.database import connection

    app, client = _client(tmp_path)
    with client:
        _add_classic(app, "Visible")
        _add_backtest(app, f"Hidden {case}", "bad-backtest", "2025-01-01T00:00:00Z")
        with connection(app.state.repo.path) as db:
            stored = db.execute(
                "SELECT config_json FROM backtests WHERE id = 'bad-backtest'"
            ).fetchone()[0]
            config = json.loads(stored)
            corrupt_config(config)
            db.execute(
                "UPDATE backtests SET config_json = ? WHERE id = 'bad-backtest'",
                (json.dumps(config),),
            )
            db.commit()
        response = client.get("/api/v1/simulations?name_contains=Visible")

    assert response.status_code == 409
    assert response.json()["detail"] == "A stored simulation is damaged and cannot be shown."


def test_zero_bet_backtest_with_zero_window_totals_is_accepted(tmp_path):
    import json

    from laboratorio.storage.database import connection

    app, client = _client(tmp_path)
    with client:
        _add_backtest(app, "No ranked draws", "empty-backtest", "2025-01-01T00:00:00Z")
        with connection(app.state.repo.path) as db:
            result = {
                "reached_goal": 0,
                "completed": 0,
                "goal_rate": 0.0,
                "quiebres": 0,
                "neto_medio": 0.0,
                "incomplete": 0,
                "window": {
                    "bets": 0,
                    "wagered": 0,
                    "paid": 0,
                    "sessions": 0,
                    "incomplete": 0,
                },
            }
            db.execute(
                "UPDATE backtests SET result_json = ? WHERE id = 'empty-backtest'",
                (json.dumps(result),),
            )
            db.commit()
        response = client.get("/api/v1/simulations?scope=historical")

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["report"]["window"]["bets"] == 0


def test_filtered_out_backtest_window_totals_corruption_fails_listing(tmp_path):
    import json

    from laboratorio.storage.database import connection

    app, client = _client(tmp_path)
    with client:
        _add_classic(app, "Visible")
        _add_backtest(app, "Hidden bad window", "bad-backtest", "2025-01-01T00:00:00Z")
        with connection(app.state.repo.path) as db:
            result = json.loads(
                db.execute(
                    "SELECT result_json FROM backtests WHERE id = 'bad-backtest'"
                ).fetchone()[0]
            )
            result["window"].update(bets=0, wagered=999999, paid=888888)
            db.execute(
                "UPDATE backtests SET result_json = ? WHERE id = 'bad-backtest'",
                (json.dumps(result),),
            )
            db.commit()
        response = client.get("/api/v1/simulations?name_contains=Visible")

    assert response.status_code == 409
    assert response.json()["detail"] == "A stored simulation is damaged and cannot be shown."


def test_filtered_out_profile_v1_result_replay_corruption_fails_listing(tmp_path):
    import json
    from dataclasses import replace

    from test_import_records import options, row
    from test_import_records import profile as imported_profile
    from test_profile_storage import profile_request, replay

    from laboratorio.domain.contracts import SettlementMode
    from laboratorio.domain.profile_session import ProfileConditions, ProfileSelector
    from laboratorio.storage.database import connection

    app, client = _client(tmp_path)
    with client:
        profile = imported_profile(positions=5)
        dataset = app.state.repo.promote_dataset(
            json.dumps(
                [row(day=f"2025-09-0{day}", numbers=tuple(range(5))) for day in (1, 2, 3)]
            ).encode(),
            **options(positions=5),
        ).dataset
        app.state.repo.create_game_profile(profile)
        request = replace(
            profile_request(profile),
            dataset_sha256=dataset.dataset_sha256,
            conditions=ProfileConditions(
                1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL, max_elapsed_draws=2
            ),
            selector=ProfileSelector(1, "static-numbers/v1", 2, numbers=(0, 1)),
        )
        identifier = app.state.repo.create_profile_experiment(request)
        app.state.repo.start_run(identifier, 0)
        app.state.repo.complete_profile_run(identifier, 0, replay(request, profile, dataset))
        app.state.repo.complete_experiment(identifier)
        assert client.get("/api/v1/simulations?scope=profile").status_code == 200
        with connection(app.state.repo.path) as db:
            stored = db.execute(
                "SELECT result_json FROM runs WHERE experiment_id = ?", (identifier,)
            ).fetchone()[0]
            result = json.loads(stored)
            result["final_balance"] += 1
            db.execute(
                "UPDATE runs SET result_json = ? WHERE experiment_id = ?",
                (json.dumps(result), identifier),
            )
            db.commit()
        response = client.get("/api/v1/simulations?name_contains=No%20match")

    assert response.status_code == 409
    assert response.json()["detail"] == "A stored simulation is damaged and cannot be shown."


def test_filtered_out_classic_result_corruption_fails_listing(tmp_path):
    from laboratorio.storage.database import connection

    app, client = _client(tmp_path)
    with client:
        _add_classic(app, "Visible")
        damaged_id = _add_classic(app, "Hidden damaged result")
        with connection(app.state.repo.path) as db:
            db.execute("UPDATE experiments SET status = 'completed' WHERE id = ?", (damaged_id,))
            db.execute(
                "UPDATE runs SET status = 'completed', result_json = '{}', "
                "result_schema_version = 1 WHERE experiment_id = ?",
                (damaged_id,),
            )
            db.commit()
        response = client.get("/api/v1/simulations?name_contains=Visible")

    assert response.status_code == 409
    assert response.json()["detail"] == "A stored simulation is damaged and cannot be shown."


def test_missing_historical_source_returns_unavailable(tmp_path):
    from laboratorio.storage.database import connection

    app, client = _client(tmp_path)
    with client:
        with connection(app.state.repo.path) as db:
            db.execute("DROP TABLE backtests")
            db.commit()
        response = client.get("/api/v1/simulations")

    assert response.status_code == 503
    assert response.json()["detail"] == "A simulation source is unavailable."
