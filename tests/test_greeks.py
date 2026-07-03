from __future__ import annotations

import unittest

from hype_options.greeks import build_portfolio_curve, sum_position_greeks


class GreeksTest(unittest.TestCase):
    def test_sum_position_greeks_ignores_wallet_position_amount(self) -> None:
        totals = sum_position_greeks(
            [
                {"amount": 100, "delta": 1.5, "gamma": 0.2, "vega": 3.0, "theta": -0.5},
                {"amount": 50, "delta": -0.25, "gamma": 0.1, "vega": -1.0, "theta": 0.2},
            ]
        )

        self.assertEqual(
            totals,
            {"delta": 1.25, "gamma": 0.3, "vega": 2.0, "theta": -0.3},
        )

    def test_portfolio_curve_has_default_points_and_anchors_current_wallet_greek(self) -> None:
        instrument = "HYPE-20260731-100-C"
        curve = build_portfolio_curve(
            [
                {
                    "instrumentName": instrument,
                    "amount": 100,
                    "delta": 2.5,
                    "gamma": 0.4,
                    "vega": 7.0,
                    "theta": -1.1,
                }
            ],
            {
                instrument: {
                    "instrumentName": instrument,
                    "optionType": "C",
                    "strike": 100,
                    "forwardPrice": 100,
                    "markIv": 0.8,
                    "dteDays": 30,
                }
            },
            "delta",
        )

        self.assertEqual(curve["metric"], "delta")
        self.assertEqual(len(curve["points"]), 61)
        current = [point for point in curve["points"] if point["shock"] == 0.0][0]
        self.assertAlmostEqual(current["value"], 2.5, places=9)
        self.assertEqual(
            [row["shock"] for row in curve["scenarioTable"]],
            [-0.2, -0.1, 0.0, 0.1, 0.2],
        )
        self.assertEqual(curve["unavailableInstruments"], [])

    def test_portfolio_curve_includes_expiry_payoff_curve(self) -> None:
        instrument = "HYPE-20260731-100-C"
        curve = build_portfolio_curve(
            [
                {
                    "instrumentName": instrument,
                    "amount": 2,
                    "side": "long",
                    "delta": 1.0,
                    "gamma": 0.2,
                    "vega": 1.0,
                    "theta": -0.1,
                }
            ],
            {
                instrument: {
                    "instrumentName": instrument,
                    "optionType": "C",
                    "strike": 100,
                    "forwardPrice": 100,
                    "markIv": 0.8,
                    "dteDays": 30,
                    "markPrice": 5,
                }
            },
            "delta",
        )

        self.assertEqual(len(curve["payoffPoints"]), 61)
        down = [point for point in curve["payoffPoints"] if point["shock"] == -0.1][0]
        current = [point for point in curve["payoffPoints"] if point["shock"] == 0.0][0]
        up = [point for point in curve["payoffPoints"] if point["shock"] == 0.1][0]
        self.assertEqual(down["value"], -10.0)
        self.assertEqual(current["value"], -10.0)
        self.assertEqual(up["value"], 10.0)
        self.assertEqual(
            [row["shock"] for row in curve["payoffScenarioTable"]],
            [-0.2, -0.1, 0.0, 0.1, 0.2],
        )

    def test_portfolio_curve_returns_empty_points_without_model_inputs(self) -> None:
        instrument = "HYPE-20260731-100-C"
        curve = build_portfolio_curve(
            [{"instrumentName": instrument, "delta": 2.5}],
            {},
            "delta",
        )

        self.assertEqual(curve["current"], 2.5)
        self.assertEqual(curve["points"], [])
        self.assertEqual(curve["scenarioTable"], [])
        self.assertEqual(curve["unavailableInstruments"], [instrument])

    def test_portfolio_curve_ignores_non_option_positions(self) -> None:
        instrument = "HYPE-20260731-100-C"
        curve = build_portfolio_curve(
            [
                {"instrumentName": instrument, "instrumentType": "option", "delta": 2.5, "gamma": 0.1, "vega": 1.0, "theta": -0.1},
                {"instrumentName": "HYPE-FUTURE", "instrumentType": "future", "delta": 999.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0},
            ],
            {
                instrument: {
                    "instrumentName": instrument,
                    "optionType": "C",
                    "strike": 100,
                    "forwardPrice": 100,
                    "markIv": 0.8,
                    "dteDays": 30,
                }
            },
            "delta",
        )

        self.assertEqual(curve["current"], 2.5)
        self.assertEqual(curve["totals"]["delta"], 2.5)
        self.assertEqual(curve["unavailableInstruments"], [])
        self.assertEqual(len(curve["points"]), 61)

    def test_portfolio_curve_includes_same_asset_perp_delta_and_payoff(self) -> None:
        instrument = "HYPE-20260731-100-C"
        curve = build_portfolio_curve(
            [
                {
                    "instrumentName": instrument,
                    "instrumentType": "option",
                    "amount": 2,
                    "side": "long",
                    "delta": 2.5,
                    "gamma": 0.1,
                    "vega": 1.0,
                    "theta": -0.1,
                },
                {
                    "instrumentName": "HYPE-PERP",
                    "instrumentType": "perp",
                    "amount": 3,
                    "side": "long",
                    "delta": 3.0,
                    "markPrice": 100,
                },
            ],
            {
                instrument: {
                    "instrumentName": instrument,
                    "optionType": "C",
                    "strike": 100,
                    "forwardPrice": 100,
                    "markIv": 0.8,
                    "dteDays": 30,
                    "markPrice": 5,
                }
            },
            "delta",
        )

        self.assertEqual(curve["current"], 5.5)
        self.assertEqual(curve["totals"]["delta"], 5.5)
        current_delta = [point for point in curve["points"] if point["shock"] == 0.0][0]
        self.assertAlmostEqual(current_delta["value"], 5.5, places=9)
        down = [point for point in curve["payoffPoints"] if point["shock"] == -0.1][0]
        current = [point for point in curve["payoffPoints"] if point["shock"] == 0.0][0]
        up = [point for point in curve["payoffPoints"] if point["shock"] == 0.1][0]
        self.assertEqual(down["value"], -40.0)
        self.assertEqual(current["value"], -10.0)
        self.assertEqual(up["value"], 40.0)

    def test_portfolio_curve_accepts_underscore_decimal_strike_instrument(self) -> None:
        instrument = "HYPE-20260731-100_5-C"
        curve = build_portfolio_curve(
            [
                {
                    "instrumentName": instrument,
                    "amount": 1,
                    "side": "long",
                    "delta": 0.5,
                    "gamma": 0.1,
                    "vega": 1.0,
                    "theta": -0.1,
                }
            ],
            {
                instrument: {
                    "instrumentName": instrument,
                    "optionType": "C",
                    "strike": 100.5,
                    "forwardPrice": 100,
                    "markIv": 0.8,
                    "dteDays": 30,
                    "markPrice": 4,
                }
            },
            "delta",
        )

        self.assertEqual(curve["current"], 0.5)
        self.assertEqual(len(curve["points"]), 61)


if __name__ == "__main__":
    unittest.main()
