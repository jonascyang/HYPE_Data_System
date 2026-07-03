from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.tsx").read_text()
ECHART = (ROOT / "frontend/src/components/EChart.tsx").read_text()
GREEK_SIMULATOR = (ROOT / "frontend/src/components/GreekSimulator.tsx").read_text()
STRATEGY_SIMULATOR = (ROOT / "frontend/src/components/StrategySimulator.tsx").read_text()
KPI_STRIP = (ROOT / "frontend/src/components/KpiStrip.tsx").read_text()
PORTFOLIO_STRIP = (ROOT / "frontend/src/components/PortfolioGreekStrip.tsx").read_text()
POSITIONS_TABLE = (ROOT / "frontend/src/components/PositionsTable.tsx").read_text()
GREEK_STRATEGY_PAGE = (ROOT / "frontend/src/pages/GreekStrategyPage.tsx").read_text()
GREEK_CURVE_PANEL = (ROOT / "frontend/src/components/GreekCurvePanel.tsx").read_text()
CHARTS_GREEKS = (ROOT / "frontend/src/charts/greeks.ts").read_text()
STYLES = (ROOT / "frontend/src/styles.css").read_text()
TYPES = (ROOT / "frontend/src/types.ts").read_text()
DISPLAY = (ROOT / "frontend/src/display.ts").read_text()
INDEX_HTML = (ROOT / "frontend/index.html").read_text()
REALTIME = (ROOT / "src/hype_options/realtime.py").read_text()
DASHBOARD_QUERIES = (ROOT / "src/hype_options/dashboard_queries.py").read_text()


def test_line_charts_redraw_with_line_drawing_animation() -> None:
    assert "triggerLineDrawing" in ECHART
    assert "line-drawing-active" in ECHART
    assert "getTotalLength" in ECHART
    assert "--line-length" in ECHART
    assert ".chart-host.line-drawing-active .highcharts-graph" in STYLES
    assert "@keyframes line-drawing" in STYLES
    assert "stroke-dashoffset: var(--line-length" in STYLES


def test_numeric_values_use_text_morph_animation() -> None:
    morph_value_path = ROOT / "frontend/src/components/MorphValue.tsx"
    assert morph_value_path.exists()
    morph_value = morph_value_path.read_text()
    assert "text-morph" in morph_value
    assert "text-morph-old" in morph_value
    assert "text-morph-new" in morph_value
    assert "MorphValue" in KPI_STRIP
    assert "MorphValue" in PORTFOLIO_STRIP
    assert "@keyframes text-morph-in" in STYLES
    assert "@keyframes text-morph-out" in STYLES


def test_market_dashboard_layout_matches_requested_rows() -> None:
    assert ".panel-oi-strike { grid-column: 1 / -1;" in STYLES
    assert ".panel-oi-expiry, .panel-atm-change { grid-column: span 6;" in STYLES
    assert ".panel-skew-fly { grid-column: span 6;" in STYLES


def test_dashboard_display_metadata_makes_units_and_history_rules_explicit() -> None:
    assert "label: 'Total Option OI'" in DISPLAY
    assert "unit: 'Contracts'" in DISPLAY
    assert "label: 'Total Option Volume'" in DISPLAY
    assert "unit: 'Gamma Exposure'" in DISPLAY
    assert "hasEnoughVolHistory" in DISPLAY
    assert "MIN_RANK_SAMPLES = 30" in DISPLAY
    assert "formatKpiDisplay('totalOptionOi'" in KPI_STRIP
    assert "flash === 'neutral'" in KPI_STRIP
    assert ".kpi-value.pulse-neutral" in STYLES


def test_expiry_colors_are_stable_and_multi_expiry_tooltips_are_capped() -> None:
    options = (ROOT / "frontend/src/charts/options.ts").read_text()
    assert "expiryColorIndex(expiry)" in options
    assert "sortExpiries(rows.map((row) => row.expiry))" in options
    assert "MULTI_SERIES_TOOLTIP_LIMIT" in options
    assert "+${hidden} more" in options
    assert "Net total" in options
    assert "Total OI" in options


def test_chart_axes_and_states_expose_units_and_structural_loading() -> None:
    options = (ROOT / "frontend/src/charts/options.ts").read_text()
    chart_panel = (ROOT / "frontend/src/components/ChartPanel.tsx").read_text()
    assert "valueAxis(percentAxis, 'IV (%)')" in options
    assert "valueAxis(compactAxis, 'Net GEX'" in options
    assert "valueAxis(compactAxis, 'Contracts')" in options
    assert "categoryAxis(rows.map((row) => row.tenor), undefined, 'DTE')" in options
    assert "panel-state-skeleton" in chart_panel
    assert ".panel-state-skeleton" in STYLES


def test_order_flow_uses_collapsible_advanced_filters_and_large_trade_priority() -> None:
    order_flow_rail = (ROOT / "frontend/src/components/OrderFlowRail.tsx").read_text()
    assert "advancedOpen" in order_flow_rail
    assert "order-flow-filter-toggle" in order_flow_rail
    assert "order-flow-advanced-filters" in order_flow_rail
    assert "eventPriority" in order_flow_rail
    assert "formatPremium(event.premiumUsd)" in order_flow_rail
    assert ".order-flow-card.large" in STYLES


def test_public_dashboard_has_metadata_and_favicon() -> None:
    assert 'name="description"' in INDEX_HTML
    assert 'property="og:title"' in INDEX_HTML
    assert 'href="/favicon.svg"' in INDEX_HTML
    assert (ROOT / "frontend/public/favicon.svg").exists()


def test_top_volatility_lookback_buttons_are_removed() -> None:
    assert "Volatility lookback days" not in APP
    assert "setLookback" not in APP
    assert "options={['90', '180', '365']}" not in APP
    assert "DEFAULT_VOL_LOOKBACK_DAYS = 365" in APP


def test_greek_simulator_supports_add_delete_and_multi_leg_simulation() -> None:
    assert "const [greekLegs, setGreekLegs]" in GREEK_SIMULATOR
    assert "addGreekLeg" in GREEK_SIMULATOR
    assert "removeGreekLeg" in GREEK_SIMULATOR
    assert "simulateGreek({" in GREEK_SIMULATOR
    assert "legs: greekLegsPayload(nextLegs)" in GREEK_SIMULATOR
    assert "function greekLegsPayload" in GREEK_SIMULATOR
    assert "ADD" in GREEK_SIMULATOR
    assert "Calculate" not in GREEK_SIMULATOR
    assert "×" in GREEK_SIMULATOR


def test_greek_simulator_summary_keeps_premium_with_greeks() -> None:
    assert "premium={result?.premium ?? null}" in GREEK_SIMULATOR
    assert "Premium" in PORTFOLIO_STRIP
    assert "totalDelta" in PORTFOLIO_STRIP
    assert "totalGamma" in PORTFOLIO_STRIP
    assert "totalVega" in PORTFOLIO_STRIP
    assert "totalTheta" in PORTFOLIO_STRIP


def test_greek_simulator_local_premium_estimate_uses_cashflow_sign() -> None:
    assert "leg.side === 'sell' ? 1 : -1" in GREEK_SIMULATOR


def test_greek_simulator_dropdowns_expand_without_panel_clipping() -> None:
    assert ".change-panel.simulator-control-panel" in STYLES
    assert "overflow: visible;" in STYLES
    assert ".simulator-controls .dropdown-menu" in STYLES
    assert "z-index: 240;" in STYLES


def test_simulation_request_accepts_multiple_legs() -> None:
    assert "export type GreekSimulationLeg" in TYPES
    assert "legs?: GreekSimulationLeg[]" in TYPES


def test_iv_smile_payload_includes_simulator_fields() -> None:
    for field in (
        "callPremium",
        "putPremium",
        "callGamma",
        "putGamma",
        "callVega",
        "putVega",
        "callTheta",
        "putTheta",
        "callRho",
        "putRho",
    ):
        assert field in TYPES
        assert field in REALTIME
        assert field in DASHBOARD_QUERIES


def test_position_lookup_removes_subtitle_and_scenario_table() -> None:
    assert "Wallet positions and portfolio-level Greeks" not in GREEK_STRATEGY_PAGE
    assert "Single-option premium and Greek scenarios" not in GREEK_STRATEGY_PAGE
    assert "Scenario Table" not in GREEK_CURVE_PANEL
    assert "greek-scenario-panel" not in GREEK_CURVE_PANEL


def test_position_lookup_filters_assets_and_uses_selected_premium() -> None:
    assert "assetFilter" in GREEK_STRATEGY_PAGE
    assert "underlyingOptions" in GREEK_STRATEGY_PAGE
    assert "selectedPremium" in GREEK_STRATEGY_PAGE
    assert "premium={selectedPremium}" in GREEK_STRATEGY_PAGE
    assert "onAssetFilterChange" in POSITIONS_TABLE
    assert "formatNotional" in POSITIONS_TABLE
    assert "formatPositionSide" in POSITIONS_TABLE
    assert "formatPositionType" in POSITIONS_TABLE
    assert "isPerpPosition" in POSITIONS_TABLE
    assert "isGreekEligiblePosition" in GREEK_STRATEGY_PAGE
    assert "payload.positions.filter(isGreekEligiblePosition).map(positionRowId)" in GREEK_STRATEGY_PAGE
    assert "isSelectable" in POSITIONS_TABLE
    assert "disabled={!selectable}" in POSITIONS_TABLE


def test_greek_and_strategy_pages_hide_duplicate_headings_and_show_premium_strip() -> None:
    assert "<h2>Greek Simulator</h2>" not in GREEK_SIMULATOR
    assert "premium={result?.premium ?? null}" in GREEK_SIMULATOR
    assert "premium={result?.premium ?? null}" in STRATEGY_SIMULATOR
    assert "simulator-summary" not in STRATEGY_SIMULATOR


def test_skew_and_fly_tables_render_change_columns() -> None:
    assert "changeMetric=\"skew\"" in APP
    assert "changeMetric=\"fly\"" in APP
    assert "row?.flyChg1d" in APP
    assert "row?.chg1d" in APP
    assert "<td>-</td>" not in APP
    assert "flyChg1d" in TYPES
    assert "flyChg1d" in REALTIME


def test_chart_tooltips_remove_unit_formula_and_use_dte_label() -> None:
    options = (ROOT / "frontend/src/charts/options.ts").read_text()
    assert "Unit: gamma * OI * spot^2" not in options
    assert "Unit: contracts" not in options
    assert "categoryLabel" in options
    assert "OI by Strike | ${valueLabel} (contracts)" in options
    assert "<th>DTE</th>" in APP
    assert "<th>到期</th>" not in APP


def test_chart_tooltips_use_explicit_point_x_labels() -> None:
    options = (ROOT / "frontend/src/charts/options.ts").read_text()
    greeks = (ROOT / "frontend/src/charts/greeks.ts").read_text()
    assert "custom: { xLabel" in options
    assert "custom: { xLabel" in greeks
    assert "tooltipLabel(this)" in options
    assert "tooltipLabel(this)" in greeks
    assert "header(String(this.x" not in greeks
    assert "rows[this.point?.index ?? 0]" not in options


def test_order_flow_removes_leg_structure_filter_badge() -> None:
    order_flow_rail = (ROOT / "frontend/src/components/OrderFlowRail.tsx").read_text()
    client = (ROOT / "frontend/src/api/client.ts").read_text()
    assert "LEG_OPTIONS" not in order_flow_rail
    assert 'label="Legs"' not in order_flow_rail
    assert "SINGLE" not in order_flow_rail
    assert "MULTI" not in order_flow_rail
    assert "legStructure" not in client
    assert "legStructure:" not in APP


def test_order_flow_supports_wallet_and_subaccount_filters() -> None:
    order_flow_rail = (ROOT / "frontend/src/components/OrderFlowRail.tsx").read_text()
    client = (ROOT / "frontend/src/api/client.ts").read_text()
    assert "wallet: ''" in APP
    assert "subaccountId: ''" in APP
    assert "walletAddress" in order_flow_rail
    assert 'label="Wallet"' in order_flow_rail
    assert 'label="Subaccount"' in order_flow_rail
    assert "['wallet', 'wallet']" in client
    assert "['subaccountId', 'subaccountId']" in client


def test_side_nav_removes_secondary_kickers() -> None:
    side_nav = (ROOT / "frontend/src/components/SideNav.tsx").read_text()
    assert "kicker" not in side_nav
    assert "<small>" not in side_nav
    for label in ("Surface", "Wallet", "Option", "Template"):
        assert label not in side_nav


def test_strategy_simulator_uses_editable_leg_builder_and_calendar_spread() -> None:
    assert "calendar_spread" in STRATEGY_SIMULATOR
    assert "strategyLegsPayload" in STRATEGY_SIMULATOR
    assert "StrategyLegEditor" in STRATEGY_SIMULATOR
    assert "Add Leg" in STRATEGY_SIMULATOR
    assert "Strike 1" not in STRATEGY_SIMULATOR
    assert "strategy: 'custom'" in STRATEGY_SIMULATOR
    assert "legs: payloadLegs" in STRATEGY_SIMULATOR


def test_responsive_strategy_builder_does_not_keep_fixed_desktop_columns() -> None:
    assert "grid-template-columns: 1.4rem minmax(0, 1fr) minmax(0, 1fr) 1.7rem;" in STYLES
    assert ".strategy-leg-editor-row .segment-control:nth-child(2)" in STYLES
    assert ".strategy-leg-editor-row .control:nth-child(4)" in STYLES
    assert ".strategy-leg-editor-row .dropdown-trigger" in STYLES


def test_side_nav_styles_match_removed_kickers() -> None:
    assert ".side-nav-item small" not in STYLES
    assert ".side-nav-item {" in STYLES
    assert "grid-template-columns: minmax(0, 1fr);" in STYLES


def test_wide_tables_use_dedicated_scroll_containers() -> None:
    wallet_lookup = (ROOT / "frontend/src/components/WalletLookupPanel.tsx").read_text()
    assert 'className="table-scroll"' in POSITIONS_TABLE
    assert 'className="table-scroll"' in STRATEGY_SIMULATOR
    assert 'className="table-scroll"' in wallet_lookup
    assert ".table-scroll" in STYLES
    assert "positions-table-panel .table-scroll" in STYLES
def test_payoff_curve_is_rendered_next_to_greek_curve_across_greek_pages() -> None:
    assert "payoffCurveOption" in GREEK_CURVE_PANEL
    assert "payoffCurve={portfolio?.payoffCurve ?? null}" in GREEK_STRATEGY_PAGE
    assert "payoffCurve={result?.payoffCurve ?? null}" in GREEK_SIMULATOR
    assert "payoffCurve={result?.payoffCurve ?? null}" in STRATEGY_SIMULATOR
    assert "Payoff" in CHARTS_GREEKS


def test_greek_metric_switches_use_prefetched_curves_without_refetching() -> None:
    assert "curves?: Partial<Record<GreekMetric, GreekCurveResponse | null>>" in TYPES
    assert "getPortfolioGreeks({ positions: selectedPositions, metric: 'delta' }" in GREEK_STRATEGY_PAGE
    assert "}, [wallet, selectedIds, selectedPositions, selectedUnderlyings]);" in GREEK_STRATEGY_PAGE
    assert "curve={portfolio?.curves?.[portfolioMetric] ?? portfolio?.curve ?? null}" in GREEK_STRATEGY_PAGE
    assert "void runSimulation(greekLegs, nextMetric)" not in GREEK_SIMULATOR
    assert "void runPreview(nextMetric)" not in STRATEGY_SIMULATOR
    assert "curve={result?.curves?.[metric] ?? result?.curve ?? null}" in GREEK_SIMULATOR
    assert "curve={result?.curves?.[metric] ?? result?.curve ?? null}" in STRATEGY_SIMULATOR


def test_position_lookup_allows_perp_but_blocks_cross_asset_portfolios() -> None:
    assert "instrumentType === 'perp'" in GREEK_STRATEGY_PAGE
    assert "selectedUnderlyings" in GREEK_STRATEGY_PAGE
    assert "Select one asset to calculate Greeks and payoff" in GREEK_STRATEGY_PAGE
    assert "selectedUnderlyings.length > 1" in GREEK_STRATEGY_PAGE


def test_position_lookup_accepts_underscore_decimal_strike_options() -> None:
    assert "[0-9._]+" in GREEK_STRATEGY_PAGE
