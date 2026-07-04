# Performance Baseline And Observability

Status: ready-for-agent

## Parent

.scratch/dashboard-performance-optimization/PRD.md

## User stories covered

28, 29, 30, 31, 32, 33, 34, 35, 36, 38

## What to build

Add a thin, low-risk performance observability layer for the current HYPE dashboard without changing user-visible behavior. The slice should measure the P0 interaction paths defined in the PRD across frontend interactions, API responses, WebSocket parsing/flush/merge, chart update work, and slow backend queries.

This issue is the baseline slice. It should make later optimization decisions evidence-driven and should produce a repeatable way to compare before/after performance.

## Acceptance criteria

- [ ] Frontend interaction timing exists for route switches, expiry changes, tenor changes, side filters, order-flow filter changes, chart option build, chart update, and WebSocket receive-to-merge.
- [ ] API responses expose or log response duration for dashboard bootstrap, panel endpoints, order-flow events, and Greek/Strategy endpoints without changing existing payload fields.
- [ ] WebSocket logs or debug metadata include message type, panel keys, payload size, and server-side payload build duration.
- [ ] Slow backend query logging exists with a clear threshold and does not spam normal logs.
- [ ] A repeatable local performance check covers the P0 interaction paths and reports p50/p95 where practical.
- [ ] Existing API response shapes and dashboard visuals remain unchanged.
- [ ] Targeted tests verify timing metadata or logging hooks at public seams, not private implementation details.
- [ ] Local verification includes targeted tests and frontend build.
- [ ] VPS verification confirms services running, collectors running, database writes current, frontend opens, and bootstrap API returns expected panel data.

## Blocked by

None - can start immediately
