# Greek And Strategy Interaction Cache

Status: ready-for-agent

## Parent

.scratch/dashboard-performance-optimization/PRD.md

## User stories covered

1, 14, 15, 16, 17, 18, 19, 28, 29, 31, 32, 33, 34, 35, 36, 38

## What to build

Improve interaction responsiveness in Position Lookup, Greek Simulator, and Strategy Simulator. Page switches should preserve useful existing results where appropriate, simulator input changes should update quickly, and metric switches should reuse prefetched curve data instead of refetching when the response already contains the needed curve.

This slice should preserve simulator formulas, existing API compatibility, and visible table/chart semantics.

## Acceptance criteria

- [ ] Position Lookup keeps previously loaded wallet/position results when navigating away and back unless wallet or selected positions change.
- [ ] Greek Simulator input changes are measured and avoid unnecessary refetches when local cached data is sufficient.
- [ ] Strategy Simulator leg edits and metric switches reuse cached/prefetched result data where possible.
- [ ] Greek/Strategy API endpoints remain backward compatible.
- [ ] Heavy wallet lookup or external-source operations keep clear loading states rather than blocking unrelated navigation.
- [ ] Existing Greek and strategy calculations remain unchanged.
- [ ] Tests cover metric switching without unnecessary refetch, preserved page state, and unchanged Greek/strategy output semantics.
- [ ] Performance baseline reports p50/p95 for simulator edits and metric switches.
- [ ] Local frontend build and targeted backend tests succeed.
- [ ] VPS verification confirms services running, collectors running, database writes current, frontend opens, and Greek/Strategy endpoints return expected data.

## Blocked by

- 01-performance-baseline-and-observability.md
