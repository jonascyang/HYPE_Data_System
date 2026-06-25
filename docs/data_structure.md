# Data Structure

## Purpose

This file describes how HYPE source data is organized after collection.

## Layer Overview

| Layer | Role |
| --- | --- |
| Raw | Preserve source responses for traceability and debugging |
| Normalized | Convert source responses into queryable option and price records |
| Metrics | Store derived volatility, positioning, and term-structure values |
| Operations | Track collection status and payload health |
| File Outputs | Store small exported samples outside the options database |

## Options Data Path

```text
Derive get_instruments
-> derive_instruments
-> active expiry list

Derive get_tickers
-> derive_raw_ticker_payloads
-> derive_ticker_snapshots
-> derived_expiry_metrics
-> derived_gex_by_strike
-> derived_global_metrics
-> derived_atm_term_metrics
-> dashboard runtime ivCurve
```

The SQL source is stored in:

```text
src/hype_options/schema.sql
```

## Object Inventory

| Layer | Object | Grain | Key Fields | Description |
| --- | --- | --- | --- | --- |
| Raw | `derive_raw_ticker_payloads` | One payload per expiry per snapshot | `id`, `ts_ms`, `expiry_yyyymmdd`, `payload_sha256` | Compressed Derive ticker response |
| Normalized | `derive_instruments` | One row per Derive instrument | `instrument_name`, `expiry_ts_ms`, `expiry_yyyymmdd`, `strike`, `option_type` | HYPE option metadata and active instrument tracking |
| Normalized | `derive_ticker_snapshots` | One row per instrument per snapshot | `ts_ms`, `instrument_name`, `expiry_ts_ms`, `strike`, `option_type`, `raw_payload_id` | Per-contract option prices, IV, Greeks, OI, volume, and surface quality |
| Normalized | `hype_price_snapshots` | One price observation per timestamp | `ts_ms`, `source`, `index_name`, `price` | HYPE price series for RV and VRP calculations |
| Metrics | `derived_expiry_metrics` | One row per expiry per snapshot | `ts_ms`, `expiry_ts_ms`, `expiry_yyyymmdd` | Expiry-level ATM IV, skew, OI, volume, max pain, GEX, and surface counts |
| Metrics | `derived_gex_by_strike` | One row per strike per expiry per snapshot | `ts_ms`, `expiry_ts_ms`, `strike` | Short-retention strike-level call, put, net, and absolute GEX |
| Metrics | `derived_global_metrics` | One row per snapshot | `ts_ms` | Snapshot-level RV, ATM IV tenors, VRP, total OI, total volume, and GEX aggregates |
| Metrics | `derived_atm_term_metrics` | One row per standard tenor per snapshot | `ts_ms`, `tenor` | Standard-tenor ATM IV values and interpolation method |
| Runtime View | dashboard `ivCurve` | One grouped point per expiry and strike at export time | `expiry`, `strike`, `callIv`, `putIv`, `callDelta`, `putDelta` | Generated from `derive_ticker_snapshots`; not stored as a long-lived table |
| Operations | `collection_runs` | One row per endpoint call or collection run | `id`, `started_ms`, `finished_ms`, `endpoint`, `status`, `payload_sha256` | Collection status, row count, error, and payload hash records |
| File Outputs | validator monitor files | One exported file per run or snapshot | `validator`, `event_id`, `time_ms`, `signed_amount_hype` | Delegation event CSV / XLSX and summary JSON files |
