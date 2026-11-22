"""Regression checks for mixed JSON-control and binary-audio WebSocket frames."""

import asyncio
import json

import pytest

from fastapi import WebSocketDisconnect

from app.voice.gateway import GnaniGateway


def test_browser_listener_reads_text_controls_and_binary_audio():
    async def exercise_listener():
        gateway = GnaniGateway()
        received = []

        async def record_json(message):
            received.append(("json", message))

        async def record_audio(frame):
            received.append(("audio", frame))

        class FakeBrowserSocket:
            def __init__(self):
                self.messages = iter([
                    {"type": "websocket.receive", "text": json.dumps({"type": "commit"})},
                    {"type": "websocket.receive", "bytes": b"\x01\x02\x03"},
                    {"type": "websocket.disconnect", "code": 1000},
                ])

            async def receive(self):
                return next(self.messages)

        gateway._ws = FakeBrowserSocket()
        gateway._handle_json = record_json
        gateway._handle_audio = record_audio

        with pytest.raises(WebSocketDisconnect):
            await gateway._browser_listener()

        assert received == [
            ("json", {"type": "commit"}),
            ("audio", b"\x01\x02\x03"),
        ]

    asyncio.run(exercise_listener())
