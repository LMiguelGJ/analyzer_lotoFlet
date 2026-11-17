import unittest


class DataNormalizationTests(unittest.TestCase):
    def test_normalization_keeps_valid_order_and_reports_boundaries(self):
        from predictor_v2.data_loader import normalize_values

        result = normalize_values([1, "02", 99, -1, 100, True, None, 1.5])

        self.assertEqual(result.numbers, [1, 2, 99])
        self.assertEqual(result.summary.valid_records, 3)
        self.assertEqual(result.summary.invalid_records, 5)
        self.assertGreaterEqual(result.summary.type_boundary_warnings, 2)
        self.assertGreaterEqual(result.summary.out_of_range_warnings, 2)

    def test_repeated_numbers_are_not_rejected_as_duplicates(self):
        from predictor_v2.data_validator import validate_numbers

        result = validate_numbers([7, 7, 8])

        self.assertTrue(result.ok)
        self.assertEqual(result.summary.repeated_draws, 1)


class BayesianAndPrequentialTests(unittest.TestCase):
    def test_bayesian_smoothing_stays_strictly_inside_probability_bounds(self):
        from predictor_v2.bayesian_predictor import ParityMarkovPredictor

        model = ParityMarkovPredictor(max_order=2)
        prediction = model.predict()

        self.assertGreater(prediction.probability_par, 0.0)
        self.assertLess(prediction.probability_par, 1.0)
        self.assertEqual(model.history_length, 0)

    def test_prediction_is_made_before_target_update(self):
        from predictor_v2.bayesian_predictor import ParityMarkovPredictor

        model = ParityMarkovPredictor(max_order=2)
        before = model.predict()
        self.assertEqual(before.metadata["history_length"], 0)

        model.update(2)
        after = model.predict()

        self.assertEqual(after.metadata["history_length"], 1)
        self.assertNotEqual(
            before.metadata["history_length"], after.metadata["history_length"]
        )


class EconomicsAndPolicyTests(unittest.TestCase):
    def test_payout_and_break_even_are_exact(self):
        from predictor_v2.betting_economics import economics_for_probability

        economics = economics_for_probability(0.5)

        self.assertEqual(economics.gross_payout, 70.0)
        self.assertEqual(economics.net_win, 20.0)
        self.assertEqual(economics.net_loss, -50.0)
        self.assertAlmostEqual(economics.break_even_probability, 5 / 7)
        self.assertEqual(economics.expected_value, -15.0)

    def test_point_probability_trigger_is_strictly_greater_than_fifty_percent(self):
        from predictor_v2.decision_policy import qualifies_by_point_probability

        self.assertFalse(qualifies_by_point_probability(0.5))
        self.assertTrue(qualifies_by_point_probability(0.5000001))

    def test_risk_limits_stop_after_a_loss(self):
        from predictor_v2.risk_manager import RiskLimits, RiskManager

        limits = RiskLimits(
            max_stake=50.0,
            max_daily_loss=50.0,
            max_drawdown=50.0,
            reserve=60.0,
        )
        manager = RiskManager(initial_capital=100.0, limits=limits)
        self.assertTrue(manager.check_stake(40.0).allowed)

        manager.record_settlement(-50.0, 40.0)

        check = manager.check_stake(40.0)
        self.assertFalse(check.allowed)
        self.assertIn(
            check.reason,
            {
                "MAX_DAILY_LOSS_EXCEEDED",
                "RESERVE_VIOLATION",
                "RESERVE_REACHED",
                "MAX_DRAWDOWN_EXCEEDED",
            },
        )


if __name__ == "__main__":
    unittest.main()
