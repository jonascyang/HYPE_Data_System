# HYPE Data System

This repository contains two related HYPE data projects:

1. `src/hype_options/` - a database-backed HYPE options data system.
2. `validator_monitor_sanitized/` - a lightweight validator delegation monitor.

The two projects are intentionally separate. Options data is snapshot-based, higher-volume, and needs a database schema, retention policy, and derived metrics. Validator delegation data is lower-volume event data, so it is handled with a simple file-based monitor.

## Components

| Component | Path | Source | Storage | Output |
| --- | --- | --- | --- | --- |
| HYPE options data system | `src/hype_options/` | Derive public API | SQLite or Turso/libSQL | Normalized tables, derived metrics, realtime dashboard API |
| HYPE options dashboard | `frontend/` | FastAPI REST and `WS /ws/options` | Browser state and realtime cache | Professional options terminal UI |
| Validator delegation monitor | `validator_monitor_sanitized/` | Hypurrscan API | Local files | CSV, XLSX, summary JSON |

## HYPE Options Data System

The options system collects recurring HYPE options market snapshots from Derive. Each run discovers active instruments, fetches per-expiry ticker data, normalizes the response into option-level rows, stores the result in SQLite or Turso/libSQL, calculates derived metrics, and exports dashboard-ready JSON.

```text
Derive public API
-> active instruments
-> per-expiry ticker snapshots
-> normalized database rows
-> derived options metrics
-> dashboard JSON
```

Main responsibilities:

- Track active HYPE option instruments, expiries, strikes, and option types.
- Store option ticker snapshots with prices, spreads, IVs, Greeks, OI, and volume.
- Keep short-lived raw payloads for traceability and reprocessing.
- Compute expiry-level metrics such as ATM IV, skew, fly, max pain, OI, volume, and GEX.
- Compute global metrics such as realized volatility, VRP, aggregate OI, aggregate volume, and aggregate GEX.
- Serve dashboard bootstrap, panel data, Greek/strategy simulations, and realtime WebSocket updates.
- Apply retention rules to high-volume tables.

### Options Database Model

| Layer | Tables | Purpose |
| --- | --- | --- |
| Source and normalized data | `derive_instruments`, `derive_ticker_snapshots`, `derive_raw_ticker_payloads`, `hype_price_snapshots` | Store instrument metadata, option snapshots, compressed source payloads, and spot price history. |
| Derived metrics | `derived_expiry_metrics`, `derived_global_metrics`, `derived_atm_term_metrics`, `derived_gex_by_strike` | Store analytics outputs for expiry views, global market views, ATM term structure, and recent strike-level GEX. |
| Order flow | `derive_order_flow_events`, `derive_order_flow_legs` | Store recent Derive orderbook and RFQ flow for the dashboard right rail. |
| Collection state | `collection_runs` | Track collection attempts, row counts, status, endpoint, and source payload hashes. |

Retention is explicit because option snapshots can grow quickly. The current design keeps raw payloads, ticker snapshots, collection run records, and strike-level GEX on configurable retention windows. Expiry-level, global, and ATM term metrics are the main long-lived analytical tables.

## Validator Delegation Monitor

The validator monitor fetches delegation events for one Hyperliquid validator from Hypurrscan. It normalizes delegate and undelegate events, signs undelegations as negative amounts, deduplicates events locally, and writes files that can be reviewed or shared without a database.

```text
Hypurrscan delegationsByValidator
-> normalized event rows
-> event_id deduplication
-> cumulative event file
-> latest new rows
-> summary JSON
```

Main responsibilities:

- Fetch validator delegation events from Hypurrscan.
- Normalize raw event fields into stable columns.
- Convert HYPE amounts from wei-style integer units.
- Store delegations as positive amounts and undelegations as negative `signed_amount_hype`.
- Deduplicate repeated pulls by `event_id`.
- Write cumulative events, new rows from the latest run, and a summary file.

## Quick Start

Requirements:

- Python 3.10+
- Dependencies in `requirements.txt`
- SQLite for local/VPS collection, or Turso/libSQL credentials for remote database collection

Install dependencies:

```bash
cd HYPE_Data_System
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run a public options snapshot without database credentials:

```bash
python examples/collect_options_once.py --expiry-limit 3 --output output/options_collect_once.json
```

Run the options collector in dry-run mode:

```bash
PYTHONPATH=src python -m hype_options.cli dry-run-live --expiry-limit 3
```

Run database-backed options collection:

```bash
cp .env.example .env.local
# For VPS/local fallback, keep DATABASE_URL=sqlite:///data/hype_options.sqlite
# For Turso, set DATABASE_URL and DATABASE_AUTH_TOKEN to your libSQL credentials

PYTHONPATH=src python -m hype_options.cli --env-file .env.local init-db
PYTHONPATH=src python -m hype_options.cli --env-file .env.local collect-once --expiry-limit 3
PYTHONPATH=src python -m hype_options.cli --env-file .env.local retention
PYTHONPATH=src python -m hype_options.cli --env-file .env.local export-dashboard-data --output output/dashboard.json
```

Run the validator monitor:

```bash
python validator_monitor_sanitized/monitor_validator_delegations.py \
  --validator 0xd6a72f04b9868d5d6050376d5d7b729f47305cec \
  --output-dir output/data
```

## Runtime Commands

| Command | Purpose |
| --- | --- |
| `dry-run-live` | Fetch live Derive options data and calculate outputs without writing to the database. |
| `init-db` | Apply `src/hype_options/schema.sql` to the configured SQLite or Turso/libSQL database. |
| `collect-once` | Run one database-backed options collection cycle. |
| `collect-loop` | Run repeated options collection on a configured interval. |
| `collect-order-flow-loop` | Run repeated Derive order-flow collection for the dashboard right rail. |
| `serve-dashboard` | Start the FastAPI dashboard API and WebSocket service. |
| `retention` | Delete rows from short-retention tables according to configured windows. |
| `export-dashboard-data` | Build dashboard JSON from stored database data. |

## Repository Structure

```text
HYPE_Data_System/
├── README.md                         # Main repository guide
├── .env.example                      # Template for Derive, database backend, and retention settings
├── .gitignore                        # Excludes local env files, caches, virtualenvs, and runtime outputs
├── requirements.txt                  # Python dependencies for both subprojects
├── docs/
│   ├── data_sources.md               # Data source inventory and source usage
│   ├── data_structure.md             # Database objects, grains, and key fields
│   └── metrics.md                    # Options metric formulas and inputs
├── examples/
│   └── collect_options_once.py       # No-database Derive options snapshot example
├── src/
│   └── hype_options/
│       ├── __init__.py               # Package marker
│       ├── cli.py                    # Command-line entry point
│       ├── config.py                 # Environment-driven runtime settings
│       ├── derive_client.py          # Derive API client
│       ├── normalizer.py             # API payload to structured option rows
│       ├── models.py                 # Data objects shared across the package
│       ├── schema.sql                # SQLite-compatible schema and indexes
│       ├── db.py                     # Database connection, schema setup, inserts, and queries
│       ├── collector.py              # One-cycle collection orchestration
│       ├── metrics.py                # Options metric calculations
│       ├── retention.py              # Short-retention table cleanup
│       ├── realtime.py               # Realtime snapshot cache and WebSocket broadcasts
│       ├── api.py                    # FastAPI REST, WebSocket, and Greek/strategy endpoints
│       └── dashboard_data.py         # Dashboard read-model data assembly
├── frontend/
│   ├── src/                          # React/Vite dashboard application
│   └── package.json                  # Frontend build and dev scripts
└── validator_monitor_sanitized/
    ├── README.md                     # Validator monitor notes
    └── monitor_validator_delegations.py
                                      # Hypurrscan fetch, normalization, deduplication, and file export
```

## Configuration

Database-backed collection reads settings from an env file, normally `.env.local`. For a local or VPS fallback, use SQLite. For Turso/libSQL, set the same `DATABASE_URL` and `DATABASE_AUTH_TOKEN` fields to the hosted database credentials. Legacy `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are still accepted.

```text
DATABASE_URL=sqlite:///data/hype_options.sqlite
DATABASE_AUTH_TOKEN=

# Turso/libSQL also works:
# DATABASE_URL=libsql://your-database.turso.io
# DATABASE_AUTH_TOKEN=replace_with_your_token

DERIVE_BASE_URL=https://api.lyra.finance
DERIVE_CURRENCY=HYPE
DERIVE_COLLECTION_INTERVAL_SECONDS=300

RAW_PAYLOAD_RETENTION_DAYS=3
TICKER_RETENTION_DAYS=7
GEX_BY_STRIKE_RETENTION_DAYS=7
COLLECTION_RUN_RETENTION_DAYS=90
```

Local output directories are generated at runtime and are not part of the source tree.

## HYPE Options Dashboard UI

The repository includes a realtime dark terminal-style HYPE options dashboard in `frontend/` and a FastAPI dashboard API in `src/hype_options/api.py`.

The dashboard is designed for professional options monitoring:

- Market dashboard: spot, snapshot time, OI, volume, put/call ratio, net GEX, ATM IV, IV rank/percentile, term structure, IV smile, GEX/OI by strike and expiry, skew/fly tables, and order flow.
- Position lookup: wallet lookup, selected positions, portfolio Greeks, delta curve, and payoff.
- Greek simulator: multi-leg option simulation with prefetched Greek curves.
- Strategy simulator: editable strategy legs, templates, payoff, and Greek curve previews.

Runtime data flow:

```text
Derive API
-> FastAPI realtime snapshot cache
-> REST bootstrap for first render
-> panel-level WebSocket updates
-> React/Vite terminal dashboard
```

Core endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/options/dashboard/bootstrap` | First-load dashboard payload. |
| `GET /api/options/dashboard/state` | Snapshot version and panel checksum state. |
| `GET /api/options/iv-smile?expiry=YYYYMMDD` | IV smile for a selected expiry. |
| `GET /api/options/gex-by-strike` | GEX aggregated across all expiries by strike. |
| `GET /api/options/gex-by-expiry` | GEX strike distribution split by expiry. |
| `GET /api/options/oi-by-strike` | OI strike distribution split by expiry. |
| `GET /api/order-flow/events` | Recent orderbook/RFQ order-flow rows. |
| `WS /ws/options` | Panel subscriptions and realtime updates. |

The REST API adds `X-Response-Time-Ms` headers. WebSocket updates include panel revisions plus payload timing metadata so interaction speed can be measured without changing user-facing data.

Run the API server:

```bash
PYTHONPATH=src python -m hype_options.cli --env-file .env.local serve-dashboard --host 127.0.0.1 --port 8000
```

Run the frontend:

```bash
cd frontend
npm install
npm run dev
```

The dashboard uses REST for first-load bootstrap and `WS /ws/options` for automatic updates. There is no main refresh workflow; the header reports live/stale/reconnecting state. Expiry and window controls are local to each chart panel.

Build and test before deployment:

```bash
PYTHONPATH=src pytest -p no:cacheprovider

cd frontend
npm run build
```

## Current VPS Deployment

Current production target:

| Item | Value |
| --- | --- |
| SSH alias | `<vps-ssh-alias>` |
| Project path | `<server-project-path>` |
| Public frontend | `<dashboard-url>/` |
| Frontend root | `<server-project-path>/frontend/dist` |
| API bind | `127.0.0.1:8000` behind nginx |

Systemd services:

| Service | Purpose |
| --- | --- |
| `hype-options-api.service` | FastAPI dashboard API, WebSocket, and realtime options snapshot cache. |
| `hype-options-orderflow.service` | Repeated Derive order-flow collection. |
| `hype-validator-monitor.service` | Validator delegation monitor. |

After deploy, verify the same four things every time:

```bash
systemctl is-active hype-options-api.service hype-options-orderflow.service hype-validator-monitor.service
curl -i <dashboard-url>/api/options/dashboard/state
curl -i '<dashboard-url>/api/order-flow/events?limit=1'
curl -I <dashboard-url>/
```

Expected result:

- Services are `active`.
- Options snapshot `latestTsMs` is recent and keeps moving.
- Order-flow rows return recent `observedAtMs`.
- Frontend returns HTTP 200 and loads assets from `frontend/dist`.
