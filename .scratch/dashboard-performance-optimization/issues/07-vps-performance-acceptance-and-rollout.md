# VPS Performance Acceptance And Rollout

Status: ready-for-agent

## Parent

.scratch/dashboard-performance-optimization/PRD.md

## User stories covered

31, 32, 33, 34, 35, 36, 38

## What to build

Create the final acceptance and rollout slice for the performance optimization effort. This should run the agreed P0 performance paths, summarize p50/p95 results, verify no data behavior was changed, and confirm the deployed VPS stack is healthy after the completed performance work.

This issue is not a redesign or feature expansion. It is the verification layer that proves the previous slices are ready to use on the live dashboard.

## Acceptance criteria

- [ ] A repeatable acceptance check runs the P0 interaction paths from the PRD and reports p50/p95.
- [ ] Acceptance output covers route switching, Market Dashboard filters, chart hover/update paths, Order Flow filters, Greek/Strategy inputs, and WebSocket update behavior.
- [ ] The report confirms whether each target is met or identifies which target remains out of range.
- [ ] Local verification includes frontend build and targeted backend/frontend tests.
- [ ] VPS sync is performed only after local verification passes.
- [ ] VPS services are confirmed active/running after rollout.
- [ ] VPS collectors are confirmed running after rollout.
- [ ] Database writes are confirmed current after rollout.
- [ ] Frontend opens from the VPS after rollout.
- [ ] Dashboard bootstrap and representative panel APIs return expected data after rollout.
- [ ] No historical data collection, API compatibility, Order Flow display range, chart data density, or metric formula regressions are found.

## Blocked by

- 02-market-dashboard-snapshot-cache-fast-switching.md
- 03-websocket-panel-patch-and-cache-calibration.md
- 04-highcharts-interaction-update-performance.md
- 05-order-flow-filter-response-optimization.md
- 06-greek-strategy-interaction-cache.md
