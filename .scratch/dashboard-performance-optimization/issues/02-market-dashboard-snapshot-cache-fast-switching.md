# Market Dashboard Snapshot Cache Fast Switching

Status: ready-for-agent

## Parent

.scratch/dashboard-performance-optimization/PRD.md

## User stories covered

1, 2, 3, 4, 5, 9, 10, 18, 19, 22, 23, 24, 26, 27, 32, 33, 34, 36, 37, 38

## What to build

Make core Market Dashboard interactions respond from the current snapshot/cache first, with background calibration to latest data. Expiry, date-like, tenor, and Call/Put/Total changes should not trigger unnecessary database-backed waits when the required data already exists in the loaded current snapshot.

The slice should strengthen the current read model and frontend state path only for the Market Dashboard core panels. It must preserve all metric formulas, existing API fields, historical writes, and displayed data density.

## Acceptance criteria

- [ ] Bootstrap includes the current snapshot data needed for common Market Dashboard switching: summary, expiries, ATM term, skew/fly, IV smile by expiry, GEX by strike, GEX by expiry, OI by strike, OI by expiry, and volatility regime data required by existing controls.
- [ ] Existing dashboard bootstrap and panel endpoints remain backward compatible.
- [ ] Expiry selection renders from loaded snapshot data when available and only fetches if the requested data is missing.
- [ ] 1W/1M/3M/6M and Call/Put/Total changes update from local state/cache when possible.
- [ ] UI keeps snapshot time and live status visible so users understand freshness.
- [ ] Historical collection, historical table writes, and indicator formulas are not modified.
- [ ] Read-model and dashboard query tests prove payloads, formulas, and expiry/GEX/OI semantics remain unchanged.
- [ ] Frontend UI tests prove existing controls remain available and no important data is hidden.
- [ ] Performance baseline shows improved or no-regression timing for expiry, tenor, and side switches.
- [ ] VPS verification confirms services running, collectors running, database writes current, frontend opens, and bootstrap API returns expected panel data.

## Blocked by

- 01-performance-baseline-and-observability.md
