# Metrics

## Purpose

This file defines the metrics used by the HYPE data system.

## Options Metrics

| Metric | Formula | Input | Output |
| --- | --- | --- | --- |
| ATM IV | Interpolate IV around forward price or spot reference | `derive_ticker_snapshots` | `derived_expiry_metrics.atm_iv` |
| ATM strike | Nearest listed strike to forward price or spot reference | `derive_ticker_snapshots` | `derived_expiry_metrics.atm_strike` |
| 25D call IV | Interpolate call IV at delta `0.25` | `derive_ticker_snapshots` | `derived_expiry_metrics.call_25d_iv` |
| 25D put IV | Interpolate put IV at delta `-0.25` | `derive_ticker_snapshots` | `derived_expiry_metrics.put_25d_iv` |
| 25D skew | `put_25d_iv - call_25d_iv` | `derived_expiry_metrics` | `derived_expiry_metrics.skew_25d` |
| 25D fly | `((put_25d_iv + call_25d_iv) / 2) - atm_iv` | `derived_expiry_metrics` | `derived_expiry_metrics.fly_25d` |
| GEX | `gamma * open_interest * spot_price^2`; puts use negative sign | `derive_ticker_snapshots` | `derived_gex_by_strike`, `derived_expiry_metrics`, `derived_global_metrics` |
| Max pain | Settlement strike with minimum aggregate option holder payoff from OI | `derive_ticker_snapshots` | `derived_expiry_metrics.max_pain_price` |
| Put / call OI ratio | `put_oi / call_oi` | `derive_ticker_snapshots` | `derived_expiry_metrics.put_call_oi_ratio` |
| Put / call volume ratio | `put_volume / call_volume` | `derive_ticker_snapshots` | `derived_expiry_metrics.put_call_volume_ratio`, `derived_global_metrics.put_call_volume_ratio` |
| Realized volatility | `sqrt(sum(log_return^2) / elapsed_years)`, using 365-day crypto annualization | `hype_price_snapshots` | `derived_global_metrics.rv_1d`, `rv_7d`, `rv_14d`, `rv_30d` |
| Standard-tenor ATM IV | Linear interpolation across expiry-level ATM IV by DTE | `derived_expiry_metrics` | `derived_atm_term_metrics`, `derived_global_metrics.atm_iv_*` |
| VRP | Term-matched `ATM IV - realized volatility` | `derived_global_metrics` | `derived_global_metrics.vrp_7d`, `vrp_30d` |
| IV curve display | Group valid option rows by expiry and strike at export time | `derive_ticker_snapshots` | dashboard `ivCurve` |
| Surface quality | Classify as `tradable`, `model`, or `invalid` from IV, delta, and market signals | `derive_ticker_snapshots` | `derive_ticker_snapshots.surface_quality` |

## Validator Metrics

| Metric | Formula | Input | Output |
| --- | --- | --- | --- |
| Delegation amount | `action.wei / 100_000_000` | Hypurrscan delegation response | `amount_hype` |
| Signed delegation amount | Delegate is positive; undelegate is negative | Normalized validator events | `signed_amount_hype` |
| New events per run | Fetched events not already present in local event ids | Normalized validator events | `new_rows_this_run` |
| Combined unique events | Deduplicated event rows by `event_id` | Normalized validator events | `combined_unique_rows` |
| Latest event time | Most recent normalized event timestamp | Normalized validator events | `latest_event_utc` |
