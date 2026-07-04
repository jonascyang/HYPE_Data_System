# WebSocket Panel Patch And Cache Calibration

Status: ready-for-agent

## Parent

.scratch/dashboard-performance-optimization/PRD.md

## User stories covered

8, 9, 10, 20, 21, 23, 24, 25, 26, 27, 30, 32, 33, 34, 36, 38

## What to build

Improve live update behavior so WebSocket messages send and apply changed panel data without disturbing current user interactions. Add compatible patch/version/checksum semantics and a lightweight calibration path so the frontend can detect missed or stale updates and recover with a full refresh only when necessary.

This slice should build on existing panel revision behavior and preserve current WebSocket compatibility during migration.

## Acceptance criteria

- [ ] WebSocket updates continue to support existing `dashboard.update`, `options.update`, and `orderFlow.update` consumers.
- [ ] Messages include enough revision/version metadata for the frontend to skip repeated panel payloads.
- [ ] Payloads avoid sending unchanged panels to subscribed clients.
- [ ] The frontend deduplicates stale or repeated revisions before merging state.
- [ ] Frontend merges are scheduled so incoming live updates do not block hover, drag, active selection, or typing.
- [ ] A lightweight state/checksum or equivalent calibration path lets the frontend detect stale cache and request a full refresh when needed.
- [ ] Tests cover changed-panel broadcast behavior, resubscribe revision reset, stale update skipping, and calibration/full-refresh behavior.
- [ ] Performance baseline shows improved or no-regression WebSocket receive-to-visible timing.
- [ ] Existing dashboard data and API response shapes remain backward compatible.
- [ ] VPS verification confirms services running, collectors running, database writes current, frontend opens, WebSocket connects, and bootstrap API returns expected panel data.

## Blocked by

- 01-performance-baseline-and-observability.md
- 02-market-dashboard-snapshot-cache-fast-switching.md
