# HYPE Dashboard Performance Optimization PRD

Status: ready-for-agent

## Problem Statement

The HYPE options dashboard is intended to feel like a professional trading terminal for a broad trader audience. The current product already exposes the right market surfaces, but interaction speed is not yet reliable enough for repeated trading workflows. Users need fast responses when switching pages, selecting different expiries or dates, applying filters, changing Call/Put/Total modes, hovering charts, and interacting with simulators.

The main user-facing problem is not only raw API latency. The perceived slowness can come from any part of the path: API bootstrap size, backend aggregation, database queries, WebSocket payloads, React state churn, chart option rebuilding, Highcharts redraws, or order flow filtering. Without performance measurements, changes can optimize the wrong layer and risk destabilizing a live dashboard.

The optimization must not disrupt historical data collection, change indicator formulas, rewrite historical data, reduce displayed data, or break existing public API contracts. The dashboard is already running locally and on a VPS, so performance work must be staged and independently verifiable.

## Solution

Optimize the dashboard as an end-to-end interaction-speed project, not as a single frontend or backend tweak.

The user experience target is:

- Page switching feels immediate.
- Expiry/date/tenor/side/filter changes render from a current snapshot/cache first.
- Background refresh then calibrates to the latest snapshot without blocking the interaction.
- Core market dashboard data is preloaded enough that common chart switches are local and near-instant.
- Heavy or historical queries remain server-backed and show explicit loading states.
- WebSocket updates only update changed panels and should not interrupt current interactions.
- The existing data collection path and historical database writes continue unchanged.

The delivery should be split into multiple tasks:

1. Add lightweight performance observability.
2. Strengthen the backend in-memory read model for current dashboard state.
3. Add Market Dashboard snapshot/cache usage for local switching.
4. Optimize Highcharts update mechanics.
5. Convert WebSocket refreshes toward patch/version/checksum behavior.
6. Optimize Order Flow filtering without changing its display range.
7. Optimize Greek and Strategy simulator interaction loops.
8. Verify and deploy each phase to the VPS with the established service/data/frontend checks.

## User Stories

1. As a trader, I want the dashboard to respond immediately when I switch between main pages, so that I can move between market, positions, Greek simulation, and strategy views without waiting.
2. As a trader, I want expiry selection to update charts quickly, so that I can compare volatility and positioning across expiries during active market monitoring.
3. As a trader, I want date or expiry-like selectors to render from already available snapshot data when possible, so that each selection does not feel like a fresh database query.
4. As a trader, I want Call/Put/Total controls to update instantly, so that I can scan open interest and positioning without losing context.
5. As a trader, I want 1W/1M/3M/6M controls to respond quickly, so that volatility regime views feel interactive.
6. As a trader, I want chart hover tooltips to remain smooth, so that I can inspect exact values without frame drops.
7. As a trader, I want chart drag and zoom interactions to remain responsive, so that axis exploration does not lag.
8. As a trader, I want incoming live updates to avoid freezing my current interaction, so that live data does not make the terminal feel unstable.
9. As a trader, I want currently visible data to clearly show snapshot time and live state, so that I understand whether I am viewing the current snapshot or a refreshed update.
10. As a trader, I want the dashboard to keep showing usable data while a background refresh runs, so that I am not blocked by loading states for common interactions.
11. As a trader, I want Order Flow filters to respond quickly for normal recent-flow filtering, so that I can scan trade flow without waiting.
12. As a trader, I want the Order Flow display range to remain unchanged, so that performance work does not alter the visible product behavior I rely on.
13. As a trader, I want advanced Order Flow filters to remain accurate, so that speed improvements do not produce misleading filtered events.
14. As a trader, I want Position Lookup to keep prior results visible when navigating away and back, so that page switching does not discard useful context.
15. As a trader, I want Greek Simulator input changes to update tables and curves quickly, so that I can iterate on option legs without constant waiting.
16. As a trader, I want Strategy Simulator edits to update preview results quickly, so that multi-leg strategy design feels direct.
17. As a trader, I want metric switches in Greek and Strategy views to use already fetched curve data when possible, so that switching Delta/Gamma/Vega/Theta does not refetch unnecessarily.
18. As a trader, I want heavy or historical queries to show a clear loading state, so that slower operations are understandable rather than feeling broken.
19. As a trader, I want the dashboard to preserve all existing data points and formulas, so that faster rendering does not mean lower analytical quality.
20. As a trader, I want WebSocket updates to apply only changed panels, so that unchanged charts do not redraw unnecessarily.
21. As a trader, I want stale or disconnected live state to be visible, so that I know when data freshness is degraded.
22. As a data operator, I want historical collection and writes to continue unchanged, so that performance optimization does not create gaps in the database.
23. As a data operator, I want current snapshot reads to be served from an in-memory read model when available, so that UI reads are not blocked by repeated aggregation.
24. As a data operator, I want every snapshot or panel payload to have version or revision metadata, so that the frontend can avoid duplicate updates.
25. As a data operator, I want lightweight checksum/version checks, so that the frontend can detect missed updates and recover with a full refresh.
26. As a data operator, I want API endpoints to remain backward compatible, so that existing frontend code and tools do not break during rollout.
27. As a data operator, I want new performance metadata to be additive, so that clients can adopt it gradually.
28. As an engineer, I want frontend interaction timing marks, so that I can identify slow route switches, filter changes, chart option builds, and chart redraws.
29. As an engineer, I want API response timing and slow-query timing, so that I can distinguish backend latency from frontend rendering latency.
30. As an engineer, I want WebSocket payload size and merge timing, so that I can see whether live updates are too large or too frequent.
31. As an engineer, I want a repeatable performance acceptance script, so that p50 and p95 measurements are not based only on visual impressions.
32. As an engineer, I want to reuse existing test seams for read model, WebSocket, API, and frontend UI contracts, so that the change stays maintainable.
33. As an engineer, I want phase-by-phase deployment to VPS, so that each optimization can be verified independently before the next one.
34. As an engineer, I want each phase to confirm services, data collection, database writes, and frontend availability, so that performance work does not hide operational regressions.
35. As an engineer, I want to avoid broad refactors while optimizing, so that the dashboard remains stable through incremental improvements.
36. As an institutional-style dashboard user, I want performance to be measured against explicit targets, so that the terminal has an objective quality bar.
37. As an institutional-style dashboard user, I want the interface to remain dense, clear, and data-complete, so that speed improvements do not turn into visual simplification.
38. As a future agent, I want the PRD split into implementable phases, so that each task can be completed, tested, deployed, and verified without touching unrelated areas.

## Implementation Decisions

- The first implementation task is observability. Add minimal performance measurement before changing behavior, because current slowness may originate in frontend rendering, WebSocket merge, backend aggregation, API response time, database query time, or chart redraw behavior.
- The performance targets for the first complete optimization pass are:
  - Page switch p95 below 100 ms.
  - Expiry/date selection p95 below 120 ms.
  - Call/Put/Total filter p95 below 80 ms.
  - Chart hover/tooltip p95 within 16-32 ms where practical.
  - Order Flow ordinary filter p95 below 250 ms.
  - First bootstrap p95 below 800 ms.
  - WebSocket update to visible frontend update p95 below 500 ms.
  - Large historical or wallet-style queries may take 500 ms to 2 s but must show clear loading state.
- Keep historical data collection unchanged. The collector, raw payload ingestion, order flow collector, historical tables, and indicator calculation formulas are not part of the optimization scope except for non-destructive index additions or read-side acceleration.
- Keep existing API contracts backward compatible. Existing bootstrap and panel endpoints must remain usable with their current field names. New metadata may be added but must not remove or rename existing fields.
- Add compatible metadata to support faster and safer reads. Candidate additions include snapshot version, per-panel versions, server timing, payload size, and checksum-like identifiers.
- Add a lightweight state/checksum endpoint if needed for background calibration. This endpoint should let the frontend detect whether its cached snapshot is current without pulling the full payload.
- Use a current dashboard read model as the primary read source. The API and WebSocket paths should prefer an in-memory current snapshot when it is available and fall back to refresh/database paths only when the read model is not ready or when historical data is explicitly requested.
- Treat the existing runtime snapshot/read-model pattern as the foundation. Strengthen it rather than introducing an unrelated caching subsystem.
- Use current snapshot/cache first for normal interactions. Page switching, expiry switching, tenor switching, and side switching should render from cached current data where the required dataset is already loaded.
- Preload Market Dashboard core datasets in the first bootstrap. This includes current snapshot summary, expiries, ATM term, skew/fly, IV smile by expiry, GEX by strike, GEX by expiry, OI by strike, OI by expiry, and volatility regime data needed for the main controls.
- Do not preload unlimited historical windows or large order flow histories. Those remain demand-driven.
- Keep Order Flow display range unchanged. Performance work may optimize query/index/cache behavior and frontend rendering, but not reduce or expand the visible range as a side effect.
- Order Flow recent filtering can use already loaded recent events where accurate. Long-range, wallet, subaccount, or heavy advanced filters should continue to use backend queries with indexes.
- WebSocket should send changed panels rather than re-sending unchanged state. Existing per-panel revision behavior should be preserved and extended with payload measurement and frontend merge timing.
- WebSocket payloads should support patch/snapshot semantics over time, while keeping existing update formats compatible during migration.
- The frontend should deduplicate stale or repeated revisions before merging state.
- The frontend should schedule live update merges in animation frames or similarly non-blocking batches, so incoming data does not interrupt hover, drag, or active input.
- Highcharts should not be destroyed and recreated for ordinary data changes. Reuse chart instances and apply minimal series/data/axis updates where series shape is compatible.
- Chart updates must not reduce data density or hide important series for performance reasons.
- Chart option building should be memoized around stable data dependencies. A state change in one panel should not rebuild every chart option when unrelated.
- Heavy chart panels and Order Flow should remain isolated memoized components so updates are local.
- The Greek and Strategy pages should cache options and reuse prefetched curve data where possible. Metric switches should not refetch when existing response data already contains the needed curve.
- The Position Lookup page should keep previously loaded state when navigating back, unless the wallet or selected positions change.
- API timing should be visible through headers or structured logs. Slow query timing should be logged only above a threshold to avoid noisy logs.
- Frontend performance logging should be lightweight and gated for production, for example by local storage or a query parameter.
- The final implementation should be deployed phase by phase to the VPS. Each phase must pass local verification before sync.
- After each VPS sync, confirm:
  - Which services are running.
  - Which data collectors are running.
  - Whether data is being written to the database.
  - Whether the frontend opens.
  - Whether the relevant API endpoints return expected data.

## Testing Decisions

- Prefer the highest practical seam: user-visible behavior, API contracts, WebSocket message behavior, and dashboard read-model outputs. Avoid tests that only assert private implementation details.
- Existing read-model tests are the correct seam for snapshot switching, panel payload selection, vol regime recomputation, and backward-compatible payload shape.
- Existing WebSocket broadcast tests are the correct seam for panel revision skipping, resubscribe behavior, changed-panel broadcasts, and future patch/version behavior.
- Existing dashboard query tests are the correct seam for ensuring GEX, OI, IV smile, expiry breakout, and vol regime calculations remain unchanged.
- Existing frontend UI contract tests are the correct seam for confirming controls, chart behavior, Order Flow filters, and simulator interactions stay available.
- Existing Order Flow tests should be extended to cover ordinary filter behavior, advanced filter behavior, wallet/subaccount filters, and any added index/query assumptions.
- Existing Greek strategy API and simulator-related tests should be extended to confirm metric switches and simulator edits reuse cached/prefetched results where possible.
- Add lightweight API timing tests only when they verify externally observable behavior, such as the presence of timing headers or metadata. Do not assert exact internal timing in unit tests.
- Add frontend performance acceptance tests that drive representative interactions and report p50/p95. These should be used for measurement and regression detection, not fragile unit pass/fail on one noisy run unless thresholds are stable.
- P0 interaction paths for the first performance pass:
  - Market Dashboard route.
  - Position Lookup route.
  - Greek Simulator route.
  - Strategy Simulator route.
  - Expiry selection.
  - 1W/1M/3M/6M selection.
  - Call/Put/Total switching.
  - Chart hover tooltip.
  - Chart drag/zoom where present.
  - Order Flow Type/Mix/Side/Advanced Filters.
  - Greek and Strategy expiry/strike/side/quantity changes.
  - WebSocket update while the user is interacting.
- P0 acceptance should include local build/test, targeted backend tests, targeted frontend tests, and a VPS smoke check.
- Do not use tests that require changing production data or rewriting historical tables.
- A good test for this PRD proves that behavior is faster or no slower while preserving the same visible data and API shape.

## Out of Scope

- Changing option metric formulas, volatility formulas, GEX calculations, OI calculations, skew/fly calculations, or Greek calculations.
- Rebuilding the data collection pipeline.
- Deleting, rewriting, or backfilling historical data as part of performance work.
- Changing Order Flow display range.
- Redesigning the visual style of the dashboard.
- Removing data points, reducing chart data density, or hiding series to make rendering faster.
- Breaking or replacing existing API endpoints.
- Introducing a separate external cache service unless later evidence proves in-process caching is insufficient.
- Multi-worker distributed cache correctness. Current deployment can first assume the existing single-process service model; if deployment topology changes, cache coherence becomes a separate design.
- Large historical analytics, long-range order flow exploration, and wallet lookup speedups beyond clear loading states and obvious indexing/query hygiene.

## Further Notes

- This PRD synthesizes the agreed strategy from the performance grilling session: optimize user interaction responsiveness first, preserve data collection and API compatibility, preload core dashboard data, use current snapshot/cache for common switches, and stage delivery into multiple tasks.
- The first implementation issue should be performance observability only. It should not change user-visible behavior except optional debug/timing metadata.
- The second implementation issue should strengthen the current snapshot/read model and API read path without changing historical writes.
- Later issues can use observations from the first phase to prioritize frontend chart updates, WebSocket payload reductions, and Order Flow query work.
- Each task should be small enough to build, test, sync to VPS, and verify independently.
