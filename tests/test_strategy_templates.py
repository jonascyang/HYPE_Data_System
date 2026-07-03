from __future__ import annotations

import unittest

from hype_options.strategy_templates import (
    SUPPORTED_STRATEGIES,
    generate_strategy_legs,
    simulate_strategy,
)


class StrategyTemplatesTest(unittest.TestCase):
    def test_supported_strategy_names_are_declared(self) -> None:
        self.assertEqual(
            set(SUPPORTED_STRATEGIES),
            {
                "long_call",
                "long_put",
                "vertical_call_spread",
                "vertical_put_spread",
                "straddle",
                "strangle",
                "risk_reversal",
                "butterfly",
                "iron_condor",
                "calendar_spread",
                "custom",
            },
        )


    def test_calendar_spread_accepts_custom_legs_with_separate_expiries(self) -> None:
        legs = generate_strategy_legs(
            "calendar_spread",
            expiry="2026-07-31",
            strikes=[],
            custom_legs=[
                {
                    "expiry": "20260731",
                    "strike": 100,
                    "optionType": "call",
                    "side": "sell",
                    "quantity": 2,
                },
                {
                    "expiry": "20260828",
                    "strike": 100,
                    "optionType": "call",
                    "side": "buy",
                    "quantity": 2,
                },
            ],
        )

        self.assertEqual(
            [leg["instrumentName"] for leg in legs],
            ["HYPE-20260731-100-C", "HYPE-20260828-100-C"],
        )
        self.assertEqual([leg["side"] for leg in legs], ["sell", "buy"])

    def test_vertical_call_spread_generates_buy_low_sell_high_calls(self) -> None:
        legs = generate_strategy_legs(
            "vertical_call_spread",
            expiry="2026-07-31",
            strikes=[110, 90],
            quantity=2,
            side="buy",
        )

        self.assertEqual(
            legs,
            [
                {
                    "instrumentName": "HYPE-20260731-90-C",
                    "expiry": "20260731",
                    "strike": 90.0,
                    "optionType": "C",
                    "side": "buy",
                    "quantity": 2.0,
                },
                {
                    "instrumentName": "HYPE-20260731-110-C",
                    "expiry": "20260731",
                    "strike": 110.0,
                    "optionType": "C",
                    "side": "sell",
                    "quantity": 2.0,
                },
            ],
        )

    def test_simulation_uses_cashflow_premium_and_exposure_greeks(self) -> None:
        legs = [
            {
                "instrumentName": "HYPE-20260731-90-C",
                "side": "buy",
                "quantity": 2,
            },
            {
                "instrumentName": "HYPE-20260731-110-C",
                "side": "sell",
                "quantity": 2,
            },
        ]
        result = simulate_strategy(
            legs,
            {
                "HYPE-20260731-90-C": {
                    "markPrice": 5,
                    "delta": 0.6,
                    "gamma": 0.04,
                    "vega": 0.8,
                    "theta": -0.2,
                },
                "HYPE-20260731-110-C": {
                    "markPrice": 2,
                    "delta": 0.3,
                    "gamma": 0.02,
                    "vega": 0.5,
                    "theta": -0.1,
                },
            },
        )

        self.assertEqual(result["totals"]["premium"], -6.0)
        self.assertEqual(result["totals"]["delta"], 0.6)
        self.assertEqual(result["totals"]["gamma"], 0.04)
        self.assertEqual(result["totals"]["vega"], 0.6)
        self.assertEqual(result["totals"]["theta"], -0.2)
        self.assertEqual(result["legs"][0]["premium"], -10.0)
        self.assertEqual(result["legs"][1]["premium"], 4.0)
        self.assertEqual(result["legs"][1]["signedQuantity"], -2.0)

    def test_pure_short_option_has_positive_premium_and_negative_greeks(self) -> None:
        result = simulate_strategy(
            [
                {
                    "instrumentName": "HYPE-20260731-90-C",
                    "side": "sell",
                    "quantity": 2,
                }
            ],
            {
                "HYPE-20260731-90-C": {
                    "markPrice": 5,
                    "delta": 0.6,
                    "gamma": 0.04,
                    "vega": 0.8,
                    "theta": -0.2,
                },
            },
        )

        self.assertEqual(result["totals"]["premium"], 10.0)
        self.assertEqual(result["totals"]["delta"], -1.2)
        self.assertEqual(result["totals"]["gamma"], -0.08)
        self.assertEqual(result["totals"]["vega"], -1.6)
        self.assertEqual(result["totals"]["theta"], 0.4)
        self.assertEqual(result["legs"][0]["premium"], 10.0)

    def test_simulation_accepts_frontend_call_put_option_type(self) -> None:
        result = simulate_strategy(
            [
                {
                    "instrumentName": "HYPE-20260731-90-C",
                    "optionType": "call",
                    "side": "buy",
                    "quantity": 2,
                }
            ],
            {
                "HYPE-20260731-90-C": {
                    "markPrice": 5,
                    "delta": 0.6,
                    "gamma": 0.04,
                    "vega": 0.8,
                    "theta": -0.2,
                },
            },
        )

        self.assertEqual(result["legs"][0]["optionType"], "C")
        self.assertEqual(result["totals"]["premium"], -10.0)


if __name__ == "__main__":
    unittest.main()
