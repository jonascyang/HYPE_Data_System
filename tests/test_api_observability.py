from __future__ import annotations

import asyncio
import time
import unittest

from fastapi.testclient import TestClient

from hype_options import api


class FakeSnapshot:
    def state_payload(self) -> dict:
        return {
            "snapshot": {"latestTsMs": 1},
            "snapshotVersion": "1",
            "panelVersions": {"summary": "abc"},
            "availablePanels": ["summary"],
        }


class FakeOptionsService:
    def __init__(self) -> None:
        self.snapshot = FakeSnapshot()

    def get_snapshot(self) -> FakeSnapshot:
        return self.snapshot

    def refresh_once(self) -> FakeSnapshot:
        return self.snapshot

    async def refresh_loop(self, manager=None) -> None:
        await asyncio.sleep(3600)


class ApiObservabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_service = api._options_service
        self.previous_task = api._options_task
        api._options_service = FakeOptionsService()
        api._options_task = None

    def tearDown(self) -> None:
        api._options_service = self.previous_service
        api._options_task = self.previous_task

    def test_dashboard_state_returns_timing_header_and_versions(self) -> None:
        client = TestClient(api.app)

        response = client.get("/api/options/dashboard/state")

        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Response-Time-Ms", response.headers)
        self.assertEqual(response.json()["snapshotVersion"], "1")
        self.assertEqual(response.json()["panelVersions"], {"summary": "abc"})

    def test_slow_query_hook_logs_only_after_threshold(self) -> None:
        start = time.perf_counter() - 1

        with self.assertLogs(api.logger, level="INFO") as captured:
            api._log_slow_query("order_flow.events", start, {"limit": 100})

        self.assertIn("slow_backend_query", captured.output[0])


if __name__ == "__main__":
    unittest.main()
