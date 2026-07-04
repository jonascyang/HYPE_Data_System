# Highcharts Interaction Update Performance

Status: ready-for-agent

## Parent

.scratch/dashboard-performance-optimization/PRD.md

## User stories covered

2, 3, 4, 5, 6, 7, 8, 19, 20, 28, 31, 32, 33, 34, 36, 37, 38

## What to build

Optimize chart update behavior for the Market Dashboard so ordinary data changes reuse existing chart instances and apply minimal updates instead of causing full chart rebuilds. Chart hover, tooltip, drag, zoom, and live-update redraw behavior should remain smooth and should not reduce displayed data density or alter metric formulas.

This slice should focus on externally visible chart responsiveness and should preserve current chart titles, series semantics, axis labels, tooltip behavior, and data completeness.

## Acceptance criteria

- [ ] Compatible chart updates reuse chart instances and patch series/data/axes where possible.
- [ ] Fallback full chart updates still work when series shape changes.
- [ ] Chart option construction is memoized around stable dependencies so unrelated state updates do not rebuild all chart options.
- [ ] Live updates do not interrupt active hover or drag interactions more than necessary.
- [ ] Chart hover/tooltip, drag/zoom, expiry switch, and Call/Put/Total switch performance are measured through the baseline tooling.
- [ ] No chart loses data points, displayed series, unit labels, ATM markers, or tooltips as part of the performance work.
- [ ] Frontend UI tests cover the presence of chart controls and chart contract behavior.
- [ ] Performance check reports p50/p95 for chart update and hover paths.
- [ ] Local frontend build succeeds.
- [ ] VPS verification confirms services running, collectors running, database writes current, frontend opens, and core charts render expected data.

## Blocked by

- 01-performance-baseline-and-observability.md
- 02-market-dashboard-snapshot-cache-fast-switching.md
