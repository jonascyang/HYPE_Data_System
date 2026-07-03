from __future__ import annotations

import sqlite3
import unittest

from hype_options.db import apply_schema
from hype_options.dashboard_queries import (
    build_dashboard_bootstrap,
    get_gex_by_expiry,
    get_gex_by_strike,
    get_iv_smile,
    get_oi_by_strike,
    get_vol_regime,
)


TS_OLD = 1_700_000_000_000
TS_NEW = TS_OLD + 86_400_000
EXPIRY_A = 1_702_592_000_000
EXPIRY_B = 1_703_456_000_000


class DashboardQueriesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(':memory:')
        apply_schema(self.conn)
        self._seed()

    def tearDown(self) -> None:
        self.conn.close()

    def _seed(self) -> None:
        self.conn.executemany(
            '''
            INSERT INTO derived_global_metrics (
              ts_ms, spot_price, rv_1d, rv_7d, rv_14d, rv_30d,
              atm_iv_7d, atm_iv_30d, atm_iv_60d, atm_iv_90d,
              vrp_7d, vrp_30d, total_option_oi, total_option_volume,
              call_volume, put_volume, put_call_volume_ratio,
              total_gex, net_gex, abs_gex
            ) VALUES (?, ?, NULL, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (TS_OLD, 60.0, 0.40, 0.35, 0.80, 0.82, 0.83, 0.84, 0.40, 0.47, 1000, 2000, 1200, 800, 0.6667, 100, -50, 150),
                (TS_NEW, 63.0, 0.42, 0.36, 0.90, 0.92, 0.93, 0.94, 0.48, 0.56, 1300, 2600, 1400, 1200, 0.8571, 200, 75, 225),
            ],
        )
        self.conn.executemany(
            '''
            INSERT INTO derived_atm_term_metrics (
              ts_ms, tenor, target_dte_days, atm_iv, method,
              left_expiry_yyyymmdd, left_dte_days, left_atm_iv,
              right_expiry_yyyymmdd, right_dte_days, right_atm_iv
            ) VALUES (?, ?, ?, ?, 'linear_interpolation', '20240105', 1, ?, '20240112', 7, ?)
            ''',
            [
                (TS_OLD, '1D', 1, 0.70, 0.70, 0.70),
                (TS_OLD, '1W', 7, 0.80, 0.80, 0.80),
                (TS_OLD, '1M', 30, 0.90, 0.90, 0.90),
                (TS_NEW, '1D', 1, 0.75, 0.75, 0.75),
                (TS_NEW, '1W', 7, 0.85, 0.85, 0.85),
                (TS_NEW, '1M', 30, 0.95, 0.95, 0.95),
                (TS_NEW, '3M', 90, 1.05, 1.05, 1.05),
                (TS_NEW, '6M', 180, 1.15, 1.15, 1.15),
            ],
        )
        self.conn.executemany(
            '''
            INSERT INTO derived_expiry_metrics (
              ts_ms, expiry_ts_ms, expiry_yyyymmdd, dte_days,
              atm_iv, atm_strike, call_25d_iv, put_25d_iv, skew_25d, fly_25d,
              total_oi, call_oi, put_oi, put_call_oi_ratio,
              total_volume, call_volume, put_volume, put_call_volume_ratio,
              max_pain_price, total_gex, net_gex, abs_gex,
              model_point_count, tradable_point_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (TS_OLD, EXPIRY_A, '20240105', 1, 0.90, 63, 0.80, 1.00, 0.20, 0.00, 100, 40, 60, 1.5, 200, 120, 80, 0.6667, 62, 10, -5, 15, 2, 10),
                (TS_NEW, EXPIRY_A, '20240105', 1, 1.00, 63, 0.85, 1.10, 0.25, 0.025, 150, 70, 80, 1.1429, 300, 160, 140, 0.875, 62, 20, 8, 28, 3, 12),
                (TS_NEW, EXPIRY_B, '20240112', 7, 1.20, 65, 0.90, 1.30, 0.40, -0.10, 200, 100, 100, 1.0, 400, 200, 200, 1.0, 64, 30, 12, 42, 4, 16),
            ],
        )
        ticker_rows = [
            (TS_NEW, None, 'HYPE-20240105-60-C', EXPIRY_A, '20240105', 60, 'C', 63, 1.0, 63, 0.9, 1.1, None, None, 1.0, 0.2, 2000, 0.80, None, None, 0.65, 0.01, None, None, None, None, 70, 160, None, None, None, 'tradable', None),
            (TS_NEW, None, 'HYPE-20240105-60-P', EXPIRY_A, '20240105', 60, 'P', 63, 1.0, 63, 0.9, 1.1, None, None, 1.0, 0.2, 2000, 1.10, None, None, -0.35, 0.02, None, None, None, None, 80, 140, None, None, None, 'tradable', None),
            (TS_NEW, None, 'HYPE-20240112-65-C', EXPIRY_B, '20240112', 65, 'C', 63, 1.2, 64, 1.1, 1.3, None, None, 1.2, 0.2, 1800, 0.90, None, None, 0.55, 0.01, None, None, None, None, 100, 200, None, None, None, 'tradable', None),
        ]
        self.conn.executemany(
            '''
            INSERT INTO derive_ticker_snapshots (
              ts_ms, source_ts_ms, instrument_name, expiry_ts_ms, expiry_yyyymmdd,
              strike, option_type, index_price, mark_price, forward_price,
              bid_price, ask_price, bid_size, ask_size, mid_price, spread_abs,
              spread_bps, mark_iv, bid_iv, ask_iv, delta, gamma, vega, theta, rho,
              rate, open_interest, volume, trade_count, high_price, low_price,
              surface_quality, raw_payload_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            ticker_rows,
        )
        self.conn.executemany(
            '''
            INSERT INTO derived_gex_by_strike (
              ts_ms, expiry_ts_ms, strike, call_gex, put_gex, net_gex, abs_gex, call_oi, put_oi
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (TS_NEW, EXPIRY_A, 60, 100, -80, 20, 180, 70, 80),
                (TS_NEW, EXPIRY_B, 60, 50, -20, 30, 70, 30, 40),
                (TS_NEW, EXPIRY_B, 65, 120, -70, 50, 190, 100, 100),
            ],
        )
        self.conn.commit()

    def test_bootstrap_returns_summary_and_default_panel_data(self) -> None:
        payload = build_dashboard_bootstrap(self.conn)

        self.assertEqual(payload['snapshot']['latestTsMs'], TS_NEW)
        self.assertEqual(payload['summary']['spotPrice'], 63.0)
        self.assertEqual(payload['summary']['totalOptionOi'], 1300.0)
        self.assertEqual(payload['summary']['netGex'], 75.0)
        self.assertEqual(payload['selectedExpiry'], '20240112')
        self.assertTrue(payload['ivSmile'])
        self.assertTrue(payload['gexByStrike'])
        self.assertTrue(payload['gexByExpiry'])
        self.assertTrue(payload['oiByStrike'])
        self.assertEqual({row['expiry'] for row in payload['oiByStrike']}, {'20240105', '20240112'})
        self.assertEqual([row['tenor'] for row in payload['skewFly']], ['1D', '1W', '1M', '3M', '6M', '1Y'])
        self.assertIn('fly25d', payload['skewFly'][0])
        self.assertIsNone(payload['skewFly'][0]['chg1d'])

    def test_iv_smile_filters_by_expiry(self) -> None:
        rows = get_iv_smile(self.conn, '20240105')

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['strike'], 60.0)
        self.assertEqual(rows[0]['callIv'], 0.80)
        self.assertEqual(rows[0]['putIv'], 1.10)

    def test_gex_by_strike_aggregates_all_expiries(self) -> None:
        gex_rows = get_gex_by_strike(self.conn)

        self.assertEqual(
            gex_rows,
            [
                {'strike': 60.0, 'callGex': 150.0, 'putGex': -100.0, 'netGex': 50.0, 'absGex': 250.0},
                {'strike': 65.0, 'callGex': 120.0, 'putGex': -70.0, 'netGex': 50.0, 'absGex': 190.0},
            ],
        )

    def test_gex_by_expiry_keeps_expiry_breakout(self) -> None:
        gex_rows = get_gex_by_expiry(self.conn)

        self.assertEqual(
            gex_rows,
            [
                {'expiry': '20240105', 'strike': 60.0, 'callGex': 100.0, 'putGex': -80.0, 'netGex': 20.0, 'absGex': 180.0},
                {'expiry': '20240112', 'strike': 60.0, 'callGex': 50.0, 'putGex': -20.0, 'netGex': 30.0, 'absGex': 70.0},
                {'expiry': '20240112', 'strike': 65.0, 'callGex': 120.0, 'putGex': -70.0, 'netGex': 50.0, 'absGex': 190.0},
            ],
        )

    def test_oi_by_strike_keeps_expiry_breakout(self) -> None:
        oi_rows = get_oi_by_strike(self.conn)

        self.assertEqual(
            oi_rows,
            [
                {'expiry': '20240105', 'strike': 60.0, 'callOi': 70.0, 'putOi': 80.0, 'totalOi': 150.0},
                {'expiry': '20240112', 'strike': 65.0, 'callOi': 100.0, 'putOi': 0.0, 'totalOi': 100.0},
            ],
        )

    def test_vol_regime_calculates_rank_and_percentile(self) -> None:
        regime = get_vol_regime(self.conn, tenor='1M', lookback_days=2)

        self.assertEqual(regime['tenor'], '1M')
        self.assertEqual(regime['lookbackDays'], 2)
        self.assertEqual(regime['currentAtmIv'], 0.95)
        self.assertEqual(regime['ivRank'], 100.0)
        self.assertEqual(regime['ivPercentile'], 100.0)


if __name__ == '__main__':
    unittest.main()
