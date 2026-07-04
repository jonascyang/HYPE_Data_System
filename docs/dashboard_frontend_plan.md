# HYPE Options Dashboard Frontend

## Product Direction

The dashboard is a black-theme options workstation inspired by Velo's density and interaction rhythm. It avoids a global expiry or window selector. Each chart owns the local controls that affect only that chart.

## Runtime Shape

```text
collector / scheduled job
-> derived SQLite or Turso tables
-> FastAPI REST bootstrap
-> WebSocket snapshot polling broadcaster
-> React + ECharts dashboard
```

The page loads with `GET /api/options/dashboard/bootstrap`, then connects to `WS /ws/options`. The WebSocket pushes updates when the latest database snapshot changes. Controls remain local to each panel.

## Panels

| Panel | Local controls | Data source |
| --- | --- | --- |
| KPI strip | none | `derived_global_metrics`, `derived_atm_term_metrics` |
| ATM IV term structure | none | `derived_atm_term_metrics` |
| IV Smile by Expiry | expiry | `derive_ticker_snapshots` |
| GEX by Strike | expiry | `derived_gex_by_strike` + `derived_expiry_metrics` |
| OI by Strike | expiry, side | `derive_ticker_snapshots` |
| OI by Expiry | side | `derived_expiry_metrics` |
| 25D Skew / Fly | none in first version | `derived_expiry_metrics` |
| VRP | 7D / 30D | `derived_global_metrics`, price history fallback |
| IV Rank / Percentile | tenor, lookback | `derived_atm_term_metrics` |
| Change table | none in first version | dashboard term/skew change exports |

## Interaction Rules

- No main refresh button. Data is automatic.
- Header shows `Live`, `Updating`, `Stale`, `Reconnecting`, or `Offline`.
- Panel controls are 24px high and local to the chart.
- A panel keeps old data visible while its local params update.
- WebSocket subscriptions are per panel: changing GEX expiry does not change IV Smile expiry.
- Chart instances stay mounted; only series/options update.

## Local Run

Backend:

```bash
cd HYPE_Data_System
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m hype_options.cli --env-file .env.local serve-dashboard --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd HYPE_Data_System/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Verification

Backend query tests:

```bash
cd HYPE_Data_System
PYTHONPATH=src python3 -m unittest tests.test_dashboard_queries -v
```

Frontend build:

```bash
cd HYPE_Data_System/frontend
npm run build
```
