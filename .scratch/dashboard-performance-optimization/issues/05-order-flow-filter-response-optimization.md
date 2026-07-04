# Order Flow Filter Response Optimization

Status: ready-for-agent

## Parent

.scratch/dashboard-performance-optimization/PRD.md

## User stories covered

8, 11, 12, 13, 18, 19, 24, 29, 30, 31, 32, 33, 34, 35, 36, 38

## What to build

Make normal Order Flow filtering respond quickly without changing the display range. Type, Mix, Side, Advanced Filters, wallet, subaccount, minimum amount, and minimum premium filters should remain accurate. Recent small-filter interactions can use loaded data where valid, while heavier or more specific filters continue to use indexed backend queries.

This slice must preserve the existing Order Flow visual range and card content.

## Acceptance criteria

- [ ] Order Flow display range remains unchanged.
- [ ] Existing filter controls remain available and keep their current meanings.
- [ ] Recent loaded events can be filtered locally only when doing so is accurate for the active filter scope.
- [ ] Backend query path remains authoritative for wallet, subaccount, long-window, and advanced filters that cannot be fully satisfied by loaded data.
- [ ] Query performance is measured and slow queries are visible in timing logs.
- [ ] Any added indexes or query changes are non-destructive and do not alter stored event data.
- [ ] Order Flow WebSocket updates do not force unnecessary dashboard-wide re-renders.
- [ ] Tests cover basic filters, advanced filters, wallet/subaccount filters, and no change to display range.
- [ ] Performance baseline reports p50/p95 for ordinary Order Flow filter changes.
- [ ] VPS verification confirms services running, orderflow collector running, orderflow database writes current, frontend opens, and Order Flow API returns expected data.

## Blocked by

- 01-performance-baseline-and-observability.md
- 03-websocket-panel-patch-and-cache-calibration.md
