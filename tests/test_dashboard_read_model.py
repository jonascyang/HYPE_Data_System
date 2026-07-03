from __future__ import annotations

import unittest

from hype_options.dashboard_read_model import (
    RuntimeDashboardSnapshot,
    dashboard_panel_payloads,
    empty_vol_regime,
    vol_regime_from_terms,
)


LATEST_TS_MS = 1_700_086_400_000


class DashboardReadModelTest(unittest.TestCase):
    def test_bootstrap_payload_switches_expiry_and_recomputes_vol_regime(self) -> None:
        snapshot = _snapshot()

        payload = snapshot.bootstrap_payload(
            selected_expiry="20240112",
            lookback_days=1,
        )

        self.assertEqual(payload["selectedExpiry"], "20240112")
        self.assertEqual(payload["ivSmile"], [{"strike": 65.0, "callIv": 0.9}])
        self.assertEqual(payload["volRegime"]["lookbackDays"], 1)
        self.assertEqual(payload["volRegime"]["sampleCount"], 2)
        self.assertEqual(payload["summary"]["ivRank"], 100.0)
        self.assertEqual(payload["summary"]["ivPercentile"], 100.0)

    def test_panel_payloads_uses_snapshot_read_model_and_ignores_unknown_panels(self) -> None:
        snapshot = _snapshot()

        payload = dashboard_panel_payloads(
            snapshot,
            {
                "summary": {},
                "ivSmile": {"expiry": "20240112"},
                "volRegime": {"tenor": "1M", "lookbackDays": 1},
                "unknown": {},
            },
        )

        self.assertEqual(set(payload), {"summary", "ivSmile", "volRegime"})
        self.assertEqual(payload["summary"]["spotPrice"], 63.0)
        self.assertEqual(payload["ivSmile"], [{"strike": 65.0, "callIv": 0.9}])
        self.assertEqual(payload["volRegime"]["currentAtmIv"], 0.9)

    def test_vol_regime_returns_empty_payload_when_tenor_has_no_values(self) -> None:
        result = vol_regime_from_terms(
            current_terms=[],
            history_rows=[],
            tenor="1M",
            lookback_days=365,
            latest_ts_ms=LATEST_TS_MS,
        )

        self.assertEqual(result, empty_vol_regime("1M", 365, latest_ts_ms=LATEST_TS_MS))


def _snapshot() -> RuntimeDashboardSnapshot:
    return RuntimeDashboardSnapshot(
        snapshot_id=LATEST_TS_MS,
        bootstrap={
            "snapshot": {"latestTsMs": LATEST_TS_MS},
            "summary": {
                "spotPrice": 63.0,
                "volRegimeTenor": "1M",
                "volRegimeLookbackDays": 365,
                "ivRank": 50.0,
                "ivPercentile": 50.0,
            },
            "selectedExpiry": "20240105",
            "ivSmile": [{"strike": 60.0, "callIv": 0.8}],
            "gexByStrike": [{"strike": 60.0, "netGex": 100.0}],
            "gexByExpiry": [{"expiry": "20240105", "netGex": 100.0}],
            "oiByExpiry": [{"expiry": "20240105", "totalOi": 100.0}],
            "atmTerm": [{"tenor": "1M", "atmIv": 0.9}],
            "skewFly": [],
            "vrpHistory": [],
            "volRegime": {"lookbackDays": 365},
        },
        iv_smile_by_expiry={
            "20240105": [{"strike": 60.0, "callIv": 0.8}],
            "20240112": [{"strike": 65.0, "callIv": 0.9}],
        },
        oi_by_strike=[{"expiry": "20240105", "strike": 60.0, "totalOi": 100.0}],
        vol_regime_history=[
            {"ts_ms": LATEST_TS_MS - 2 * 86_400_000, "tenor": "1M", "atm_iv": 0.7},
            {"ts_ms": LATEST_TS_MS - 12 * 60 * 60 * 1000, "tenor": "1M", "atm_iv": 0.8},
        ],
        current_atm_terms=[{"tenor": "1M", "atm_iv": 0.9}],
        lookback_days=365,
    )


if __name__ == "__main__":
    unittest.main()
