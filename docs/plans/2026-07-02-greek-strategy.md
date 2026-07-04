# Greek & Strategy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `Greek & Strategy` route to the existing HYPE Options terminal that supports Derive wallet position lookup, portfolio-level Greek display, Greek scenario curves, single-option simulation, and strategy simulation.

**Architecture:** Keep the existing FastAPI + React/Vite + Highcharts architecture. Backend owns Derive Wallet Lookup parsing, ticker joins, Greek aggregation, scenario generation, and strategy previews. Frontend owns route navigation, terminal-style layout, portfolio-level display, and simulator interactions, using the current CSS tokens and component language.

**Tech Stack:** Python stdlib + httpx + FastAPI; React + TypeScript + Vite + Highcharts; unittest for backend; `npm run build` for frontend.

---

## Non-Negotiable Product Rules

- Visual style must match the current frontend exactly: use current CSS variables, 2px panels, thin borders, compact tables, terminal typography, and Highcharts style.
- Do not introduce a new color palette, large cards, rounded dashboard redesign, marketing hero, or new design system.
- Position table must not show per-position Delta/Gamma/Vega/Theta columns.
- Wallet Lookup position Greek fields are treated as already amount-adjusted. Portfolio Greek aggregation sums them directly and never multiplies by `amount`.
- Greek curves show portfolio-level values only. One selected Greek metric is shown at a time.
- Tx Hash links open `https://explorer.derive.xyz/tx/{tx_hash}`.

## Work Split

Backend worker owns:

- `src/hype_options/wallet_lookup.py`
- `src/hype_options/greeks.py`
- `src/hype_options/strategy_templates.py`
- backend changes in `src/hype_options/api.py`, `src/hype_options/config.py`
- backend tests under `tests/`

Frontend worker owns:

- `frontend/src/pages/GreekStrategyPage.tsx`
- `frontend/src/components/*Greek*`
- `frontend/src/components/SideNav.tsx`
- `frontend/src/charts/greeks.ts`
- frontend changes in `frontend/src/App.tsx`, `frontend/src/types.ts`, `frontend/src/api/client.ts`, `frontend/src/styles.css`

Workers must not revert or rewrite unrelated existing work. Main integrator resolves cross-boundary type and API mismatches.

---

### Task 1: Backend Wallet Lookup Parser

**Files:**
- Create: `src/hype_options/wallet_lookup.py`
- Test: `tests/test_wallet_lookup.py`
- Modify: `src/hype_options/config.py`

**Steps:**
1. Add `derive_app_base_url: str = "https://app.derive.xyz"` to `Settings`.
2. Implement `WalletLookupClient.fetch_wallet(address: str) -> dict`.
3. Request path: `GET {derive_app_base_url}/wallet/{address}?_rsc=1` with header `RSC: 1`.
4. Parse RSC text payload and extract the props object containing `wallet`, `scwOwner`, `ensName`, `trades`, `subaccounts`, `subaccountDeposits`, and `currencies`.
5. Normalize output shape:
   - `inputAddress`
   - `wallet`
   - `scwOwner`
   - `ensName`
   - `subaccounts`
   - `positions`
   - `trades`
   - `currencies`
   - `source`
6. Preserve raw position Greek fields as numbers: `delta`, `gamma`, `vega`, `theta`.
7. Add parser tests using a small fixture string with an RSC line containing wallet props.

**Verification:**

```bash
PYTHONPATH=src python3 -m unittest tests.test_wallet_lookup -v
```

Expected: parser extracts wallet, owner, positions, trades, and does not transform Greek values.

---

### Task 2: Backend Greek Aggregation And Curves

**Files:**
- Create: `src/hype_options/greeks.py`
- Test: `tests/test_greeks.py`

**Steps:**
1. Define `sum_position_greeks(positions)` that directly sums `delta`, `gamma`, `vega`, `theta`.
2. Explicitly test that `amount` is ignored for Wallet Lookup positions.
3. Implement Black-style forward option helper functions using only stdlib math:
   - normal pdf
   - normal cdf via `math.erf`
   - `d1`, `d2`
   - delta, gamma, vega, theta
4. Implement `build_portfolio_curve(selected_positions, ticker_by_instrument, metric, shock_min=-0.30, shock_max=0.30, step=0.01)`.
5. For position curves, anchor each position's current value to Wallet Lookup:
   - current value = Wallet Lookup Greek
   - scenario value = walletGreek * modelScenarioGreek / modelCurrentGreek
   - if model current is missing or near zero, skip the curve contribution and include an `unavailableInstruments` note
6. Add scenario table points for `-20%`, `-10%`, `0%`, `+10%`, `+20%`.

**Verification:**

```bash
PYTHONPATH=src python3 -m unittest tests.test_greeks -v
```

Expected: direct sum ignores amount, curve has 61 points by default, current point equals summed Wallet Lookup Greek.

---

### Task 3: Backend Strategy Templates And Simulation

**Files:**
- Create: `src/hype_options/strategy_templates.py`
- Test: `tests/test_strategy_templates.py`

**Steps:**
1. Define supported strategy names:
   - `long_call`
   - `long_put`
   - `vertical_call_spread`
   - `vertical_put_spread`
   - `straddle`
   - `strangle`
   - `risk_reversal`
   - `butterfly`
   - `iron_condor`
   - `custom`
2. Implement template leg generation from expiry, strikes, quantity, and side.
3. Implement simulation aggregation from ticker unit Greek:
   - signed quantity is positive for buy, negative for sell
   - premium is `mark_price * signed quantity`
   - total Greek is `unitGreek * signed quantity`
4. Return both leg rows and portfolio totals.

**Verification:**

```bash
PYTHONPATH=src python3 -m unittest tests.test_strategy_templates -v
```

Expected: strategy legs match templates and total Greek uses signed quantity.

---

### Task 4: Backend API Endpoints

**Files:**
- Modify: `src/hype_options/api.py`
- Test: `tests/test_greek_strategy_api.py`

**Endpoints:**
- `GET /api/greek-strategy/wallet?address=...`
- `POST /api/greek-strategy/portfolio-greeks`
- `GET /api/greek-strategy/options`
- `POST /api/greek-strategy/simulate`
- `POST /api/greek-strategy/strategy-preview`

**Steps:**
1. Add endpoint response shapes that match frontend types.
2. Use existing realtime options snapshot or latest ticker rows to build option lists and ticker maps.
3. Do not block dashboard endpoints if wallet lookup fails.
4. Return clear HTTP 400 for invalid address or missing required fields.
5. Return HTTP 503 for upstream Wallet Lookup unavailable.

**Verification:**

```bash
PYTHONPATH=src python3 -m unittest tests.test_greek_strategy_api -v
PYTHONPATH=src python3 -m unittest tests.test_dashboard_queries tests.test_order_flow tests.test_order_flow_collector -v
```

Expected: new API tests pass and existing dashboard/order-flow tests still pass.

---

### Task 5: Frontend Route Shell And Navigation

**Files:**
- Create: `frontend/src/components/SideNav.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

**Steps:**
1. Add route state with two top-level routes: `market` and `greekStrategy`.
2. Move existing dashboard content behind `market`.
3. Add `SideNav` with `Market Dashboard`, `Order Flow`, `Greek & Strategy`, and `Settings`.
4. Preserve current topbar, panel spacing, chart grid, and order-flow rail behavior.
5. Use existing CSS variables only.

**Verification:**

```bash
cd frontend
npm run build
```

Expected: build passes and market dashboard remains visible by default.

---

### Task 6: Frontend Greek Strategy Types And API Client

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api/client.ts`

**Steps:**
1. Add TypeScript types for:
   - wallet lookup response
   - wallet position
   - wallet trade
   - portfolio Greek summary
   - Greek curve point
   - option instrument choice
   - simulation request/response
   - strategy preview request/response
2. Add API client functions for all new endpoints.
3. Keep client functions thin like existing dashboard functions.

**Verification:**

```bash
cd frontend
npm run build
```

Expected: TypeScript compiles with no implicit shape mismatch.

---

### Task 7: Frontend Position Lookup Page

**Files:**
- Create: `frontend/src/pages/GreekStrategyPage.tsx`
- Create: `frontend/src/components/WalletLookupPanel.tsx`
- Create: `frontend/src/components/PositionsTable.tsx`
- Create: `frontend/src/components/PortfolioGreekStrip.tsx`
- Modify: `frontend/src/styles.css`

**Steps:**
1. Implement page tabs: `Position Lookup`, `Greek Simulator`, `Strategy Simulator`.
2. Implement address input and lookup button.
3. Show loading, empty, and error states using current panel language.
4. Show wallet summary strip.
5. Show selectable positions table.
6. Omit per-position Greek columns.
7. Tx hash links use `https://explorer.derive.xyz/tx/{txHash}`.
8. On selection change, call portfolio Greek endpoint and update total Greek strip.

**Verification:**

```bash
cd frontend
npm run build
```

Expected: page builds and no per-row Greek columns exist in `PositionsTable`.

---

### Task 8: Frontend Greek Curve Panel

**Files:**
- Create: `frontend/src/components/GreekCurvePanel.tsx`
- Create: `frontend/src/charts/greeks.ts`
- Modify: `frontend/src/styles.css`

**Steps:**
1. Use Highcharts option style consistent with `frontend/src/charts/options.ts`.
2. Add segment control for `Delta`, `Gamma`, `Vega`, `Theta`.
3. Render one portfolio-level line only.
4. Add current price vertical marker at `0%`.
5. Add scenario table for `-20%`, `-10%`, `Current`, `+10%`, `+20%`.
6. Show notice when instruments are missing curve data.

**Verification:**

```bash
cd frontend
npm run build
```

Expected: chart option compiles and uses the same `hype-chart` styling vocabulary.

---

### Task 9: Frontend Simulators

**Files:**
- Create: `frontend/src/components/GreekSimulator.tsx`
- Create: `frontend/src/components/StrategySimulator.tsx`
- Modify: `frontend/src/pages/GreekStrategyPage.tsx`
- Modify: `frontend/src/styles.css`

**Steps:**
1. `Greek Simulator`: expiry, strike, call/put, side, quantity, calculate.
2. `Strategy Simulator`: strategy template, expiry, strike inputs, quantity, preview.
3. Both show premium and portfolio-level Greek totals.
4. Both reuse `GreekCurvePanel` for scenario display.
5. Keep controls compact and local to panels.

**Verification:**

```bash
cd frontend
npm run build
```

Expected: both simulator tabs compile and share portfolio-level result display.

---

### Task 10: Final Integration And Visual Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/dashboard_frontend_plan.md` or create a focused doc under `docs/`

**Steps:**
1. Run all backend tests.
2. Install frontend dependencies if needed.
3. Run frontend build.
4. Start backend and frontend if environment variables are available.
5. Capture screenshots for Market Dashboard and Greek & Strategy.
6. Compare visual style against current frontend:
   - background color
   - panel color
   - border strength
   - active blue
   - compact typography
   - table density
7. Document run commands and endpoint behavior.

**Verification:**

```bash
PYTHONPATH=src python3 -m unittest discover tests -v
cd frontend
npm run build
```

Expected: tests and build pass, screenshots match current terminal style.
