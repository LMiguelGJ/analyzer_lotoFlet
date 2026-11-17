import unittest
from contextlib import redirect_stdout
from io import StringIO


class _AuditModel:
    model_name = "audit_model"

    def __init__(self):
        self.seen = []
        self.snapshots = []

    def predict(self):
        from predictor_v2.bayesian_predictor import Prediction

        self.snapshots.append(tuple(self.seen))
        return Prediction(
            side="PAR",
            probability_par=0.6,
            probability_impar=0.4,
            point_probability=0.6,
            support=len(self.seen),
            context="audit",
            model_name=self.model_name,
            metadata={"history_length": len(self.seen), "past_only": True},
        )

    def update(self, number):
        self.seen.append(number)


class WalkForwardSafetyTests(unittest.TestCase):
    def test_walk_forward_calls_predict_before_updating_target(self):
        from predictor_v2.walk_forward import WalkForwardConfig, WalkForwardEngine

        audit = _AuditModel()
        values = list(range(20))
        result = WalkForwardEngine(
            WalkForwardConfig(warmup=4),
            candidate_factory=lambda: {"audit_model": audit},
        ).run(values)

        self.assertEqual(audit.snapshots[0], tuple(values[:4]))
        self.assertEqual(audit.snapshots[1], tuple(values[:5]))
        self.assertEqual(result.test_metrics.count, 4)

    def test_calibrated_test_and_forecast_probabilities_preserve_raw_metadata(self):
        from predictor_v2.report_generator import render_forecast
        from predictor_v2.walk_forward import WalkForwardConfig, WalkForwardEngine

        result = WalkForwardEngine(
            WalkForwardConfig(warmup=4, retain_test_predictions=True),
            candidate_factory=lambda: {"audit_model": _AuditModel()},
        ).run(list(range(1, 22)))

        self.assertEqual(result.calibration_fit.block_count, 1)
        self.assertAlmostEqual(result.forecast.point_probability, 0.5)
        self.assertEqual(result.forecast.metadata["raw_point_probability"], 0.6)
        self.assertEqual(result.forecast.metadata["calibrated_point_probability"], 0.5)
        self.assertTrue(
            all(prediction[3] == 0.5 for prediction in result.test_predictions)
        )
        self.assertIn("raw_point_probability=60.000%", render_forecast(result.forecast))

    def test_calibrated_side_and_point_probability_follow_calibrated_probability(self):
        from predictor_v2.bayesian_predictor import Prediction
        from predictor_v2.calibration import IsotonicCalibrator
        from predictor_v2.walk_forward import _calibrated_prediction

        raw_prediction = Prediction(
            side="PAR",
            probability_par=0.6,
            probability_impar=0.4,
            point_probability=0.6,
            support=1,
            context="regression",
            model_name="regression_model",
        )
        calibrator = IsotonicCalibrator().fit([0.6, 0.6], [0, 0])

        calibrated = _calibrated_prediction(raw_prediction, calibrator)

        self.assertEqual(calibrated.side, "IMPAR")
        self.assertEqual(calibrated.point_probability, 1.0)
        self.assertEqual(calibrated.metadata["raw_side"], "PAR")
        self.assertEqual(calibrated.metadata["raw_point_probability"], 0.6)

    def test_point_rule_can_bet_but_labels_negative_ev(self):
        from predictor_v2.decision_policy import (
            PaperPolicyConfig,
            build_risk_manager,
            decide_paper,
        )

        config = PaperPolicyConfig(
            bankroll=100.0,
            fixed_stake=10.0,
            max_stake=10.0,
            max_daily_loss=100.0,
            max_drawdown=100.0,
            reserve=0.0,
        )
        manager = build_risk_manager(config)
        decision = decide_paper("PAR", 0.60, config, manager)

        self.assertEqual(decision.action, "BET")
        self.assertIn("NEGATIVE_EXPECTED_VALUE", decision.warnings)
        self.assertIsNotNone(decision.economics)
        assert decision.economics is not None
        self.assertLess(decision.economics.expected_value, 0.0)

    def test_paper_bet_has_no_outcome_until_explicit_settlement(self):
        from predictor_v2.decision_policy import PaperPolicyConfig
        from predictor_v2.paper_trading import PaperTrader

        config = PaperPolicyConfig(
            bankroll=100.0,
            fixed_stake=10.0,
            max_stake=10.0,
            max_daily_loss=100.0,
            max_drawdown=100.0,
            reserve=0.0,
        )
        trader = PaperTrader(config)
        bet = trader.place(7, "PAR", 0.60)

        self.assertIsNotNone(bet)
        assert bet is not None
        self.assertIsNone(bet.outcome)
        self.assertFalse(bet.settled)
        trader.settle(bet, "IMPAR")
        self.assertEqual(bet.outcome, "IMPAR")
        self.assertEqual(bet.net_result, -10.0)


class CalibrationAndSimulationTests(unittest.TestCase):
    def test_equal_probability_observations_share_one_isotonic_block(self):
        from predictor_v2.calibration import IsotonicCalibrator

        calibrator = IsotonicCalibrator().fit([0.5, 0.5], [0, 1])

        self.assertEqual(calibrator.fit_info.block_count, 1)
        self.assertEqual(calibrator.transform([0.5, 0.5]), [0.5, 0.5])

    def test_final_test_data_cannot_fit_calibrator(self):
        from predictor_v2.calibration import IsotonicCalibrator

        with self.assertRaises(ValueError):
            IsotonicCalibrator().fit([0.5], [True], source="final_test")

    def test_monte_carlo_requires_explicit_manual_risk_limits(self):
        from predictor_v2.monte_carlo import run_monte_carlo
        from predictor_v2.risk_manager import RiskLimits

        for limits in (None, RiskLimits()):
            with self.subTest(limits=limits):
                with self.assertRaisesRegex(ValueError, "explicit manual risk limit"):
                    run_monte_carlo(
                        100.0, 0.6, stake=5.0, paths=1, horizon=1, limits=limits
                    )

    def test_monte_carlo_max_drawdown_refuses_peak_stake_before_capital_changes(self):
        from predictor_v2.monte_carlo import run_monte_carlo
        from predictor_v2.risk_manager import RiskLimits

        report = run_monte_carlo(
            100.0,
            0.6,
            stake=10.0,
            paths=1,
            horizon=1,
            limits=RiskLimits(max_drawdown=5.0),
        )

        scenario = report.configured_under_estimated
        self.assertEqual(scenario.mean_final_capital, 100.0)
        self.assertEqual(scenario.mean_max_drawdown, 0.0)
        self.assertEqual(scenario.ruin_or_stop_rate, 1.0)

    def test_monte_carlo_cli_without_risk_limit_explains_no_bet(self):
        from predictor_v2.main import main

        output = StringIO()
        with redirect_stdout(output):
            status = main(
                [
                    "monte_carlo",
                    "--bankroll",
                    "100",
                    "--estimated-probability",
                    "0.6",
                    "--stake",
                    "10",
                    "--paths",
                    "1",
                    "--horizon",
                    "1",
                ]
            )

        self.assertEqual(status, 0)
        self.assertIn("MONTE CARLO NO_BET", output.getvalue())

    def test_monte_carlo_seed_is_deterministic(self):
        from predictor_v2.monte_carlo import run_monte_carlo
        from predictor_v2.risk_manager import RiskLimits

        limits = RiskLimits(max_stake=5.0)
        first = run_monte_carlo(
            100.0,
            0.6,
            stake=5.5,
            paths=20,
            horizon=10,
            seed=7,
            limits=limits,
        )
        second = run_monte_carlo(
            100.0,
            0.6,
            stake=5.5,
            paths=20,
            horizon=10,
            seed=7,
            limits=limits,
        )

        self.assertEqual(
            first.configured_under_null.mean_final_capital,
            second.configured_under_null.mean_final_capital,
        )
        self.assertEqual(first.no_bet.mean_final_capital, 100.0)

    def test_calibration_flip_makes_calibrated_side_coherent(self):
        from predictor_v2.walk_forward import WalkForwardConfig, WalkForwardEngine

        values = [2, 4, 6, 8] + [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25]
        result = WalkForwardEngine(
            WalkForwardConfig(warmup=4, retain_test_predictions=True),
            candidate_factory=lambda: {"audit_model": _AuditModel()},
        ).run(values)

        self.assertEqual(result.forecast.metadata["raw_side"], "PAR")
        self.assertEqual(result.forecast.metadata["calibrated_side"], "IMPAR")
        self.assertEqual(result.forecast.side, "IMPAR")
        self.assertEqual(result.forecast.point_probability, 1.0)
        self.assertTrue(all(p[2] == "IMPAR" for p in result.test_predictions))


if __name__ == "__main__":
    unittest.main()
