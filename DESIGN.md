---
name: "HYPE Options Dashboard"
description: "A dense institutional options terminal for monitoring HYPE volatility, positioning, and market structure."
colors:
  terminal-bg: "#0d0d0d"
  terminal-ink: "#f2f2f2"
  terminal-border: "#ffffff1a"
  terminal-border-strong: "#ffffff33"
  terminal-muted: "#f2f2f28c"
  terminal-faint: "#f2f2f257"
  data-blue: "#2962ff"
  data-cyan: "#26c6da"
  data-purple: "#d568fb"
  data-yellow: "#fbc130"
  data-orange: "#fe7f2d"
  success-green: "#00c805"
  danger-red: "#fa5000"
  gold-light: "#dbb863"
typography:
  display:
    fontFamily: "Geist Pixel Square, ui-monospace, SFMono-Regular, Menlo, Monaco, monospace"
    fontSize: "1.18rem"
    fontWeight: 500
    lineHeight: 1.31
    letterSpacing: "0.01em"
  headline:
    fontFamily: "Geist Pixel Square, ui-monospace, SFMono-Regular, Menlo, Monaco, monospace"
    fontSize: "0.95rem"
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: "0.01em"
  title:
    fontFamily: "Geist Pixel Square, ui-monospace, SFMono-Regular, Menlo, Monaco, monospace"
    fontSize: "0.86rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.01em"
  body:
    fontFamily: "Outfit, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0"
  label:
    fontFamily: "Outfit, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.70rem"
    fontWeight: 400
    lineHeight: 1.43
    letterSpacing: "0"
rounded:
  sharp: "0"
  panel: "4px"
  control: "6px"
  pill: "16px"
spacing:
  xxs: "4px"
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  chart-panel:
    backgroundColor: "{colors.terminal-bg}"
    textColor: "{colors.terminal-ink}"
    rounded: "{rounded.panel}"
    padding: "0"
  kpi-cell:
    backgroundColor: "{colors.terminal-bg}"
    textColor: "{colors.terminal-ink}"
    rounded: "{rounded.sharp}"
    padding: "8px 12px"
  select-control:
    backgroundColor: "{colors.terminal-bg}"
    textColor: "{colors.terminal-ink}"
    rounded: "{rounded.control}"
    height: "28px"
    padding: "0 24px 0 8px"
  segment-control-active:
    backgroundColor: "{colors.terminal-ink}"
    textColor: "{colors.terminal-bg}"
    rounded: "{rounded.pill}"
    height: "24px"
    padding: "0 8px"
  tooltip:
    backgroundColor: "{colors.terminal-bg}"
    textColor: "{colors.terminal-ink}"
    rounded: "{rounded.panel}"
    padding: "7px 9px"
---

# Design System: HYPE Options Dashboard

## 1. Overview

**Creative North Star: "Institutional Volatility Console"**

The system is a black, high-density market surface built for traders who need to read volatility, positioning, and flow without being slowed down by decorative UI. It should feel like a serious options terminal: precise, compact, technical, and quietly premium. The design borrows discipline from Velo-like market tooling, but it must remain a HYPE-specific data product rather than a cloned marketing surface.

The interface rejects generic SaaS dashboard card grids, marketing-page composition, oversized hero sections, low information density, over-decorated UI, ornamental gradients, glass effects, and arbitrary colorful accents. Color exists to assign data roles, state, and chart meaning. Typography carries the feeling of a technical instrument: refined enough for institutional use, never theatrical.

**Key Characteristics:**
- Black terminal surface with thin white-alpha strokes and minimal tonal layering.
- High information density with local controls placed beside the chart they affect.
- Highcharts SVG chart language: thin rounded lines, small circular points, dark SVG tooltips, and restrained data colors.
- Outfit remains the dense UI reading face. Geist Pixel Square is used narrowly for brand text, KPI values, strip values, and chart/table titles.
- Honest state language: live, stale, reconnecting, unavailable, and insufficient-history states are part of the design system.

## 2. Colors

The palette is restrained: a near-black terminal surface, one white ink system, and a small set of explicit data colors for chart roles and state.

### Primary
- **Terminal Black**: the default app, panel, chart, tooltip, and control background. It creates the trading-terminal atmosphere and prevents routine data views from becoming decorative.
- **Terminal Ink**: the primary text and active control color. It is intentionally near-white rather than pure white so dense screens remain readable.

### Secondary
- **Data Blue**: the default primary series color for IV, total OI, and core chart emphasis.
- **Data Cyan**: a supporting series color for calls, secondary volatility structures, or cool-side comparison.
- **Data Purple**: a supporting series color for puts or secondary comparative lines when green/red would overstate directionality.
- **Data Yellow / Gold**: warning, updating, and intermediate state accents. Use sparingly.

### Tertiary
- **Success Green**: positive state, live connection, call-side or positive GEX where that semantic is clear.
- **Danger Red**: stale/offline state, put-side or negative GEX where that semantic is clear.
- **Data Orange**: reserved for a fourth or fifth data role; do not use it as decoration.

### Neutral
- **Terminal Border**: the default panel, grid, divider, and control stroke. It is white at low alpha, not gray paint.
- **Terminal Border Strong**: hover and active boundary emphasis for panels and controls.
- **Terminal Muted**: labels, status details, axis labels, and secondary table cells.
- **Terminal Faint**: tertiary text and low-priority annotation support.

### Named Rules

**The Data-Role Rule.** Every saturated color must explain a data category, a state, or a selected control. If the color is only making the page feel more exciting, remove it.

**The Black Surface Rule.** Panels, toolbars, charts, and tooltips stay on Terminal Black. Depth comes from border strength, text hierarchy, and chart geometry, not from stacked gray cards.

## 3. Typography

**Display Font:** Geist Pixel Square with monospace fallbacks
**Body Font:** Outfit with system fallbacks
**Label/Mono Font:** Outfit for labels and controls; Geist Pixel Square for selected terminal-style display text

**Character:** Outfit gives the dashboard a technical, market-tool quality for dense labels, controls, axes, and tooltips. Geist Pixel Square adds a more explicit terminal texture for high-signal display roles, but it should not spread into tiny UI labels, table cells, controls, or tooltip body text.

### Hierarchy
- **Display** (Geist Pixel Square, 500, 1.18rem, 1.31): KPI values and important numeric summaries. This is the largest routine type in the product.
- **Headline** (Geist Pixel Square, 500, 0.95rem, 1.5): product identity in the top bar and the strongest persistent label.
- **Title** (Geist Pixel Square, 500, 0.86rem, 1.4): chart titles, table titles, and compact section headings.
- **Body** (400, 1rem, 1.5): base document text and inherited control text. Product prose should remain short and operational.
- **Label** (400, 0.70rem, 1.43, uppercase allowed): KPI labels, strip labels, status support text, and dense control labels.
- **Chart Axis** (200, 0.75rem): Highcharts axis labels and legend text. Use the light weight only inside chart scaffolding.

### Named Rules

**The No Display Drama Rule.** This is a product surface. Do not introduce oversized marketing headings, fluid hero type, or display-font labels.

**The Numeric Clarity Rule.** Numbers must be formatted for scanning: compact units for large values, percentages with controlled decimals, and dates as `yyyy/mm/dd` when shown to users.

## 4. Elevation

This system is flat by default. Depth is conveyed through border strength, hover states, grid lines, and SVG layering inside charts. Shadows are not used for panels or routine controls. The only shadow-like treatment is the Highcharts tooltip drop-shadow, which is a functional hover affordance rather than decorative elevation.

### Shadow Vocabulary
- **Tooltip Drop** (`drop-shadow(0 .25rem .125rem rgba(0,0,0,.16))`): used only on chart tooltips so hover content separates from the plot area.
- **Status Glow** (`0 0 0 .25rem rgba(...)`): used only on small status dots to make live/updating/stale state readable.

### Named Rules

**The Flat Terminal Rule.** Surfaces are flat at rest. If a panel needs emphasis, strengthen the border or improve hierarchy; do not add a soft card shadow.

## 5. Components

### Buttons
- **Shape:** compact pill or segmented control shape (16px radius for the segmented wrapper; active buttons inherit that pill geometry).
- **Primary:** active segment uses Terminal Ink on Terminal Black inversion: light fill with dark text.
- **Hover / Focus:** hover increases opacity and adds a subtle white-alpha background. Focus uses the same border vocabulary as controls.
- **Secondary / Ghost:** inactive segments are transparent, low-opacity Terminal Ink, and must not use saturated color.

### Chips
- **Style:** chips are represented by the top-bar `OPTIONS` marker and segmented controls: compact, bordered, text-first, no icon decoration.
- **State:** selected state is a color inversion, not a new hue.

### Cards / Containers
- **Corner Style:** panels use a sharp 4px radius.
- **Background:** Terminal Black only.
- **Shadow Strategy:** no panel shadows. Use border, alignment, and content hierarchy.
- **Border:** 2px white-alpha default border, stronger white-alpha on hover.
- **Internal Padding:** KPI cells use 8px 12px; table panels use 14px; chart panels reserve content space mostly through Highcharts spacing.

### Inputs / Fields
- **Style:** native select controls are restyled as compact 28px controls with Terminal Black background, 2px white-alpha border, 6px radius, and a custom chevron.
- **Focus:** border shifts to Terminal Ink. No glow unless the state is a clear warning or error.
- **Error / Disabled:** not fully defined in the current UI; future states should use explicit copy plus red/gold state color, never color alone.

### Navigation
- **Style:** a sticky 40px top bar with brand on the left, a compact `OPTIONS` marker, and live snapshot status on the right.
- **Typography:** 0.95rem brand, 0.75rem status labels.
- **Default / Hover / Active:** navigation is informational rather than route-heavy. State appears in the status dot and status label.
- **Mobile:** the top bar stacks into one column and removes the `OPTIONS` marker to preserve space.

### Highcharts Panels
- **Character:** chart panels are the signature component. They use styledMode Highcharts SVG with terminal typography, minimal grid lines, thin rounded series strokes, 2px circular markers, dark tooltips, and chart-local controls.
- **Tooltip:** SVG tooltip, 4px radius, Terminal Black fill, Terminal Ink stroke, 0.85rem text, 0.75rem date header.
- **ATM / Zero Lines:** ATM uses a dashed plot line and inline label; zero lines use low-alpha white. Plot annotations must never obscure the data.

### KPI Strip
- **Character:** a single continuous information strip, not separate floating cards.
- **Shape:** no individual card radius; cells divide by 2px low-alpha borders.
- **Content:** label first, value second, no explanatory prose. Missing values use an em dash.

### Tables
- **Style:** compact, right-aligned numeric cells with a sticky header and subtle row hover.
- **State:** rows may brighten on hover, but should not introduce new background colors.

## 6. Do's and Don'ts

### Do:
- **Do** keep the surface black, dense, and terminal-like. This product is for traders reading live market structure.
- **Do** use saturated colors only for chart roles, semantic state, or selected controls.
- **Do** keep chart controls local to the chart panel they affect.
- **Do** label units directly in KPI titles, table headers, or tooltips.
- **Do** show stale, reconnecting, unavailable, and insufficient-history states honestly.
- **Do** preserve Highcharts-style SVG tooltips, thin rounded line strokes, small circle markers, and restrained axis labels.
- **Do** test text and chart labels on mobile so controls, annotations, and titles do not overlap.

### Don't:
- **Don't** use generic SaaS dashboard card grids.
- **Don't** use marketing-page composition, oversized hero sections, or homepage-style value propositions inside the dashboard.
- **Don't** reduce information density to make the surface feel friendlier; improve structure instead.
- **Don't** add ornamental gradients, glass effects, decorative shadows, or arbitrary colorful accents.
- **Don't** make unavailable or statistically weak metrics look complete.
- **Don't** rely on red/green alone to communicate call/put or positive/negative meaning; pair it with labels, legends, signs, or position.
- **Don't** add soft card shadows to bordered panels. That breaks the terminal material.
- **Don't** introduce display fonts, novelty mono labels, or fluid hero typography into operational UI.
