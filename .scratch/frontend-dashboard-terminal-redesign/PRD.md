# PRD: Frontend Dashboard Terminal Redesign

Status: ready-for-agent

## Problem Statement

The current HYPE options dashboard works as a functional realtime market surface, but it does not yet feel like a professional options terminal for broad trader usage. Users can see HYPE spot price, option OI, volume, IV term structure, IV smile, GEX, OI distribution, skew/fly tables, and order flow, but the presentation still creates doubt around units, precision, chart meaning, and interaction state.

The main user-facing problems are:

- The dashboard has high data volume but weak visual hierarchy, so primary market signals compete with secondary tables and controls.
- Units and calculation meaning are not always visible at the moment the user reads a number.
- Multi-expiry charts can become visually noisy, and expiry colors are not treated as a stable semantic mapping.
- Tooltips are dense and can overload the user when many expiries have data at the same strike.
- Realtime updates exist, but motion, hover, loading, stale, and empty states do not yet feel as polished as a high-end trading terminal.
- Order Flow is useful but too busy by default, with too many filters and details competing in the right rail.
- The dark UI direction is correct, but typography, surfaces, panel hierarchy, and brand metadata still read closer to an internal tool than an institution-grade public product.

The intended audience is broad active traders, including sophisticated retail and institutional-style users. They need fast comprehension, clear data meaning, stable visual encoding, and a refined black terminal aesthetic without excessive cards or flashy decoration.

## Solution

Upgrade the existing HYPE options frontend into a more professional, responsive, black terminal-style data dashboard while keeping the current product scope and realtime API model.

The solution should improve clarity, polish, and interaction speed without introducing a new frontend framework or broad backend redesign. The dashboard should remain data-dense, dark, and trader-focused. It should preserve the existing metrics and panels, but make each number and chart easier to interpret through stronger unit labeling, chart metadata, stable colors, richer tooltip structure, better loading states, and cleaner motion.

The redesigned surface should:

- Keep the current React, Vite, Highcharts, REST bootstrap, and WebSocket update architecture.
- Treat units, precision, sign, and semantic polarity as first-class display metadata.
- Use stable expiry color assignment across GEX by Expiry and OI by Strike.
- Make chart axes, legends, labels, and tooltips explain contracts, IV percent, GEX, strike, expiry, and DTE without requiring guesswork.
- Make realtime updates feel smooth and controlled rather than noisy.
- Reduce the card-heavy feel by using a more integrated terminal grid, subtle depth, clear section hierarchy, and denser but readable controls.
- Make Order Flow scan faster with clearer event priority, collapsible advanced filters, and better large-trade emphasis.
- Preserve local per-panel controls for expiry, side, tenor, and window choices.
- Keep IV Rank, IV Percentile, and VRP hidden unless the available historical data and backend support make them reliable.
- Verify the result locally and then deploy/sync the frontend to the VPS target used by this project.

## User Stories

1. As an options trader, I want every KPI to show a clear unit or metric meaning, so that I know whether I am reading contracts, percent, ratio, GEX, or dollars.
2. As an options trader, I want Total Option OI to clearly state that it is measured in contracts, so that I do not confuse it with notional value.
3. As an options trader, I want Total Option Volume to clearly state that it is measured in contracts, so that I can compare activity across time correctly.
4. As an options trader, I want Net GEX to explain its display unit and sign, so that I can understand whether dealer positioning is net positive or negative.
5. As an options trader, I want ATM IV values to use consistent percent formatting, so that I can compare 1D, 1W, 1M, 3M, and 6M quickly.
6. As an options trader, I want dates to use a consistent yyyy/mm/dd display, so that I can read expiries and snapshot times without format switching.
7. As an options trader, I want the latest snapshot time to be visible and trustworthy, so that I know whether I am looking at current market data.
8. As an options trader, I want stale, reconnecting, offline, and live states to be visually distinct, so that I know whether to trust the screen.
9. As an options trader, I want realtime updates to animate subtly, so that I notice changes without losing focus.
10. As an options trader, I want KPI number changes to avoid misleading green/red semantics, so that neutral metrics do not look directional when they are not.
11. As an options trader, I want chart panels to have clearer hierarchy, so that the most important charts receive attention first.
12. As an options trader, I want the dashboard to feel like a terminal rather than a stack of cards, so that the product feels professional and data-native.
13. As an options trader, I want chart labels and legends to stay readable in a black UI, so that I can scan charts in low-light trading setups.
14. As an options trader, I want GEX by Strike to aggregate all expiries without an expiry selector, so that I can see the full market strike distribution.
15. As an options trader, I want GEX by Strike to clearly mark ATM, so that I can anchor the GEX distribution around current spot.
16. As an options trader, I want GEX by Expiry to show all expiries with separate colors, so that I can compare which expiries contribute to strike-level GEX.
17. As an options trader, I want OI by Strike to show all expiries with separate colors, so that I can compare open interest concentration across expiries.
18. As an options trader, I want OI by Strike to preserve Total, Call, and Put side filters, so that I can switch between aggregate and option-type views.
19. As an options trader, I want expiry colors to remain stable across charts and refreshes, so that I can build visual memory.
20. As an options trader, I want legends to remain useful when many expiries are present, so that color encoding does not become noise.
21. As an options trader, I want chart tooltips to show concise top contributors first, so that I do not have to read a long list of every expiry.
22. As an options trader, I want tooltips to show the hovered strike, expiry, unit, and value in a structured layout, so that I can interpret values quickly.
23. As an options trader, I want IV Smile to distinguish call IV and put IV where the data differs, so that I can understand skew and smile structure.
24. As an options trader, I want IV Smile controls to remain local to the panel, so that changing one chart does not unexpectedly alter the whole dashboard.
25. As an options trader, I want 25D RR and 25D Fly to be displayed as separate tables, so that I can read skew and fly independently.
26. As an options trader, I want 25D RR and Fly change columns to show unavailable values as a clear dash when historical comparison is not supported, so that I do not mistake missing data for zero.
27. As an options trader, I want ATM IV change columns to use consistent change formatting, so that positive, negative, and unavailable changes are easy to compare.
28. As an options trader, I want IV Rank and IV Percentile hidden when history is insufficient, so that incomplete statistics do not imply false confidence.
29. As an options trader, I want VRP hidden until backend support is complete, so that unsupported analytics do not appear broken.
30. As an options trader, I want loading states to resemble the final chart or table shape, so that the dashboard feels stable while data loads.
31. As an options trader, I want empty states to explain whether data is missing, unavailable, or still loading, so that I know what action or waiting is appropriate.
32. As an options trader, I want previous valid data to remain visible during realtime refresh when possible, so that the dashboard does not flicker or go blank.
33. As an options trader, I want the Order Flow rail to show recent trades with clear priority, so that large or unusual trades are easier to notice.
34. As an options trader, I want advanced Order Flow filters to be collapsible, so that the right rail does not waste scan space when I only want live flow.
35. As an options trader, I want wallet and subaccount filters to remain available, so that I can investigate specific participants.
36. As an options trader, I want Order Flow cards to show side, mix, execution type, size, premium, and time in a consistent hierarchy, so that each event is easy to compare.
37. As an options trader, I want expanded Order Flow legs to feel like a detail view, so that multi-leg orders are readable without crowding every card.
38. As an options trader, I want copy interactions for wallet addresses to be obvious and responsive, so that I can use them without hunting for hidden controls.
39. As an options trader, I want dropdowns, segmented controls, inputs, and hover states to share one visual language, so that the interface feels designed rather than browser-default.
40. As an options trader, I want keyboard focus states to be visible in the dark UI, so that I can navigate controls efficiently.
41. As an options trader, I want reduced motion preferences respected, so that realtime animations do not cause discomfort or distraction.
42. As an options trader, I want the dashboard to remain usable on narrower screens, so that I can monitor it on secondary displays or browser side panes.
43. As an options trader, I want the typography to feel technical but readable, so that dense data does not become tiring.
44. As an options trader, I want public-page metadata and favicon to be present, so that the product feels complete when opened, shared, or bookmarked.
45. As a dashboard operator, I want the frontend deployment to be verified on the VPS after local build, so that users see the upgraded experience online.
46. As a dashboard operator, I want the frontend to keep using the current REST and WebSocket contracts unless a change is explicitly required, so that the backend collector and API remain stable.
47. As a dashboard operator, I want the data-source and database write path unaffected by the redesign, so that visual upgrades do not risk collection reliability.
48. As a future implementation agent, I want the redesign scope to be contained to display metadata, chart options, frontend components, styling, and minor API metadata only if needed, so that I can implement the work without unnecessary architecture churn.

## Implementation Decisions

- Work inside the existing HYPE options dashboard architecture: React frontend, Vite build, Highcharts charts, REST bootstrap endpoints, and WebSocket panel updates.
- Do not migrate frontend frameworks, charting libraries, or state management as part of this PRD.
- Treat this as a frontend product-quality redesign, not a new analytics project.
- Preserve the current metric set and panel-level control model unless a metric is explicitly unsupported by backend history.
- Keep refresh automatic through WebSocket updates. Do not add a manual refresh as the primary workflow.
- Add or centralize display metadata for each market metric: unit, precision, compacting rules, sign display, semantic polarity, and unavailable state.
- Use this metadata across KPIs, axis labels, tooltip values, tables, and Order Flow values.
- Keep Total Option OI and Total Option Volume labeled as contracts until a notional value is explicitly added by backend data.
- Keep IV values displayed as percent and changes displayed as percentage-point-style deltas using the existing volatility formatting convention.
- Keep dates in yyyy/mm/dd format across expiry labels, snapshot labels, and order-flow timestamps where applicable.
- Keep IV Rank and IV Percentile hidden until the configured minimum sample threshold is met and backend values are present.
- Keep VRP hidden until backend support produces reliable values for the relevant windows.
- Make expiry color assignment deterministic and shared across charts. A given expiry should use the same color within the dashboard session and should not depend on unordered API response behavior.
- For charts with more expiries than the base palette, choose a deterministic overflow strategy rather than silently reusing confusing near-identical colors.
- Keep GEX by Strike aggregated across all expiries and remove any expiry-level selector from that panel.
- Keep GEX by Expiry as a strike-distribution chart with each expiry represented by its own color.
- Keep OI by Strike as an all-expiry strike-distribution chart with side filtering for Total, Call, and Put.
- Keep OI by Expiry side filtering for Total, Call, and Put, and make the displayed unit explicit.
- Always mark ATM on strike-distribution charts when spot price is available.
- Improve Highcharts axis labeling so the user can identify strike on x-axis and contracts, IV percent, or GEX on y-axis without relying only on title text.
- Redesign chart tooltips so they show a compact header, unit-aware rows, and the most relevant series first.
- For multi-expiry tooltips, avoid showing an unlimited list of series. Use top contributors, grouped summary, or a capped list with an additional count or total.
- Prefer rich tooltip layout when needed, as long as it remains performant and visually consistent in the dark terminal theme.
- Reduce repeated line-drawing animation on every data update. Use animation for initial entry or meaningful data replacement, not for every realtime tick.
- Preserve requestAnimationFrame scheduling and memoization patterns that prevent unnecessary chart redraws.
- Make loading states structural: chart skeletons should resemble axes and data shapes; table skeletons should resemble rows and columns.
- Make empty states specific to the data problem: loading, unavailable, no current records, insufficient history, or backend error.
- Keep previous valid panel data visible during background updates when possible.
- Improve panel hierarchy by distinguishing primary charts, secondary charts, and tables through spacing, header treatment, and surface contrast rather than heavy cards.
- Preserve the black theme and avoid bright gradient-heavy decoration, excessive color, or marketing-style hero layout.
- Refine typography by using Geist Pixel Square where it adds terminal character, while ensuring numbers, labels, tables, and tooltip text remain legible at dense sizes.
- Make dropdowns, segmented controls, inputs, and buttons share a consistent dark component style.
- Add or refine keyboard-visible focus states for custom controls.
- Keep per-panel selectors local to the relevant chart instead of adding global selectors that affect unrelated panels.
- Redesign Order Flow so high-priority event information is immediately visible and secondary filters/details are available without dominating the rail.
- Keep wallet and subaccount filtering in Order Flow.
- Add public-facing metadata such as description and favicon so the dashboard feels complete when opened or bookmarked.
- Keep backend API changes optional and minimal. If a frontend display issue requires backend-provided metadata, add a small non-breaking field rather than changing existing payload shapes.
- Do not change database collection, data retention, Turso/libSQL configuration, or VPS data collector behavior unless a defect is discovered during verification.
- After implementation, build locally, verify the dashboard behavior, then sync the deployed frontend to the configured VPS target for this project.

## Testing Decisions

- The highest-value testing seam is the dashboard as rendered by the frontend against stable REST and WebSocket-like market data fixtures. This should verify user-visible behavior rather than implementation details.
- Existing frontend-oriented tests currently provide prior art for checking requested UI structure, chart tooltip behavior, realtime update wiring, Order Flow filters, and responsive layout expectations.
- Existing backend query tests provide prior art for validating dashboard payload shape and aggregation behavior.
- Add tests for display metadata behavior: contracts labels, IV percent formatting, GEX formatting, unavailable values, and hidden unsupported metrics.
- Add tests for deterministic expiry color assignment: the same expiry should map to the same display color when input order changes.
- Add tests for GEX by Strike using all expiries with no expiry selector.
- Add tests for GEX by Expiry rendering each expiry as a distinct series grouped by strike.
- Add tests for OI by Strike using all expiries while preserving Total, Call, and Put filtering.
- Add tests for ATM marker presence on strike-distribution charts when spot price is available.
- Add tests for tooltip caps or summary behavior when many expiries exist at one strike.
- Add tests for IV Rank, IV Percentile, and VRP visibility rules when backend history is insufficient or unsupported.
- Add tests for Order Flow filter behavior, including collapsed advanced filters if that state is introduced.
- Add tests for loading and empty states by asserting user-visible status text and structural skeleton classes rather than internal component state.
- Add responsive verification for desktop, narrow desktop, and mobile-width layouts to ensure controls and text do not overlap.
- Run the frontend production build as a required verification step.
- Run the existing Python test suite for dashboard query and frontend UI expectations where relevant.
- Manually verify the public VPS page after deployment by checking that the frontend loads, the API responds, WebSocket status becomes live or reconnecting as expected, and market data is visible.
- If a visual regression tool is introduced, use it only for high-level screenshots of the dashboard states and avoid brittle pixel-perfect assertions for live charts.

## Out of Scope

- Building new options metrics beyond the already selected dashboard metric set.
- Implementing VRP or IV Rank/Percentile backend history if the current database does not support it yet.
- Changing the remote data collector schedule, database provider, Turso/libSQL credentials, or retention policy.
- Adding authentication, user accounts, saved layouts, alerts, or paid product flows.
- Supporting assets beyond HYPE.
- Replacing Highcharts with another charting library.
- Migrating React, Vite, or the current frontend build system.
- Redesigning the Greek strategy simulator beyond shared component and typography improvements needed for visual consistency.
- Creating a marketing landing page.
- Adding broad documentation outside the project issue tracker.

## Further Notes

- The desired feel is a black, data-dense, professional options terminal suitable for broad trader usage and institutional-style monitoring.
- The design should remain restrained: technical, precise, and high-quality without excessive neon, decorative cards, or over-branded effects.
- Data clarity is more important than visual novelty. Every number should answer: what is this, what unit is it in, how fresh is it, and can I compare it safely?
- This PRD is ready for an implementation agent, but the agent should still inspect the latest live frontend before making changes because the current dashboard is actively evolving.
