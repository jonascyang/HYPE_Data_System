# Data Sources

## Purpose

This file lists the sources used by the HYPE data system and where each source enters the package.

## Source Inventory

| Source | Source Path | Used For | Output |
| --- | --- | --- | --- |
| Derive public API | `POST https://api.lyra.finance/public/get_instruments` | HYPE option instrument metadata from Derive | `derive_instruments` |
| Derive public API | `POST https://api.lyra.finance/public/get_tickers` | HYPE option tickers, IV, Greeks, OI, and volume from Derive | `derive_raw_ticker_payloads`, `derive_ticker_snapshots`, derived options metrics |
| Hypurrscan API | `GET https://api.hypurrscan.io/delegationsByValidator/{validator}` | Validator delegate and undelegate events from a supporting source | Validator monitor CSV, XLSX, and summary JSON |
| Local HYPE options package | `src/hype_options/` | Runnable options collection and derivation logic | SQL schema, normalized rows, derived metrics, dashboard JSON |
| Local options example | `examples/collect_options_once.py` | One-shot public Derive options collection without database credentials | Options metrics JSON |
| Local validator monitor | `validator_monitor_sanitized/` | Review copy of the validator delegation monitor | Validator event rows and summary output |
