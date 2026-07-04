from __future__ import annotations

import asyncio
import unittest

from hype_options.realtime import DashboardConnectionManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, message: dict) -> None:
        self.messages.append(message)


class RealtimeBroadcastTest(unittest.TestCase):
    def test_snapshot_broadcast_skips_unchanged_panel_payload(self) -> None:
        async def run() -> list[dict]:
            manager = DashboardConnectionManager()
            websocket = FakeWebSocket()
            await manager.connect(websocket)
            manager.subscribe(websocket, "summary")

            await manager.broadcast_snapshot(
                snapshot_id=1,
                message_type="options.update",
                payload_builder=lambda panels: {"summary": {"spotPrice": 1}},
            )
            await manager.broadcast_snapshot(
                snapshot_id=2,
                message_type="options.update",
                payload_builder=lambda panels: {"summary": {"spotPrice": 1}},
            )
            await manager.broadcast_snapshot(
                snapshot_id=3,
                message_type="options.update",
                payload_builder=lambda panels: {"summary": {"spotPrice": 2}},
            )
            return websocket.messages

        messages = asyncio.run(run())

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["snapshotId"], 1)
        self.assertEqual(messages[1]["snapshotId"], 3)
        self.assertEqual(messages[0]["payload"], {"summary": {"spotPrice": 1}})
        self.assertEqual(messages[1]["payload"], {"summary": {"spotPrice": 2}})
        self.assertIn("summary", messages[0]["revisions"])
        self.assertGreater(messages[0]["payloadBytes"], 0)
        self.assertIsInstance(messages[0]["serverBuildMs"], float)

    def test_resubscribe_with_new_params_resets_panel_revision(self) -> None:
        async def run() -> list[dict]:
            manager = DashboardConnectionManager()
            websocket = FakeWebSocket()
            await manager.connect(websocket)
            manager.subscribe(websocket, "ivSmile", {"expiry": "20260731"})

            await manager.broadcast_panel_update(
                panel="ivSmile",
                snapshot_id=1,
                payload_builder=lambda params: [{"expiry": params["expiry"], "strike": 100}],
            )
            manager.subscribe(websocket, "ivSmile", {"expiry": "20260828"})
            await manager.broadcast_panel_update(
                panel="ivSmile",
                snapshot_id=2,
                payload_builder=lambda params: [{"expiry": params["expiry"], "strike": 100}],
            )
            return websocket.messages

        messages = asyncio.run(run())

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["payload"]["ivSmile"][0]["expiry"], "20260731")
        self.assertEqual(messages[1]["payload"]["ivSmile"][0]["expiry"], "20260828")
        self.assertGreater(messages[1]["payloadBytes"], 0)
