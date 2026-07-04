# HYPE Options Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a black-theme HYPE options dashboard with automatic WebSocket updates, REST bootstrap, and per-chart local controls.

**Architecture:** Keep the existing collector and derived SQLite/Turso schema as the source of truth. Add a FastAPI layer that exposes dashboard-ready REST payloads and a polling WebSocket broadcaster, then add a Vite React frontend that renders ECharts panels with Velo-like density and micro-interactions.

**Tech Stack:** Python stdlib + FastAPI/Uvicorn for API and WebSocket; React + Vite + TypeScript + ECharts for frontend; existing SQLite/Turso data model for metrics.

---

### Task 1: Dashboard Query Layer

**Files:**
- Create: `src/hype_options/dashboard_queries.py`
- Test: `tests/test_dashboard_queries.py`

**Steps:**
1. Write tests for latest snapshot lookup, bootstrap payload shape, IV smile filtering, GEX by strike filtering, OI by strike filtering, and IV rank/percentile.
2. Run `PYTHONPATH=src python3 -m unittest tests.test_dashboard_queries -v` and verify failures before implementation.
3. Implement query functions using the existing schema and `dashboard_data.build_dashboard_payload` where useful.
4. Re-run unittest and keep implementation minimal.

### Task 2: FastAPI REST and WebSocket Layer

**Files:**
- Create: `src/hype_options/realtime.py`
- Create: `src/hype_options/api.py`
- Modify: `src/hype_options/cli.py`
- Modify: `requirements.txt`

**Steps:**
1. Add `fastapi` and `uvicorn` to requirements.
2. Add REST endpoints for bootstrap and each chart panel.
3. Add WebSocket subscribe messages with per-panel params.
4. Add a polling broadcaster that checks the latest snapshot and pushes `dashboard.update` events.
5. Add `serve-dashboard` CLI command.

### Task 3: Frontend Project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/*`

**Steps:**
1. Create React/Vite app files without changing the Python collector.
2. Implement REST bootstrap client and WebSocket hook.
3. Render top live status, KPI strip, and chart grid.
4. Add per-chart local controls: expiry, side, period, tenor, lookback.
5. Use ECharts with stable chart containers and series updates.

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`
- Create: `docs/dashboard_frontend_plan.md`

**Steps:**
1. Document API/frontend run commands.
2. Run backend unit tests.
3. If dependencies are installed, run frontend build.
4. If not installed, report the exact unverified dependency gap.
