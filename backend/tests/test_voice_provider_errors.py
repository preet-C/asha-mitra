"""Regression checks for safe, actionable speech-provider failures."""

import asyncio
import base64
import json

import pytest

from app.voice.gateway import _stt_connection_message, _tts_failure_message
from app.voice.gnani_tts import GnaniTTS, GnaniTTSRequestError


class FakeSocket:
    """Small fake that lets tests exercise TTS events without network access."""

    def __init__(self, messages):
        self.messages = iter(messages)
        self.closed = False

    async def send(self, _request):
        return None

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration

    async def close(self):
        self.closed = True


def test_stt_rejection_explains_access_without_showing_credentials():
    class RejectedHandshake(Exception):
        response = type("Response", (), {"status_code": 403})()

    message = _stt_connection_message(RejectedHandshake())
    assert "HTTP 403" in message
    assert "Prisma STT access" in message
    assert "key" in message


def test_tts_provider_rejection_points_to_voice_and_account_access():
    message = _tts_failure_message(
        GnaniTTSRequestError("provider rejected request", kind="rejected")
    )
    assert "selected voice" in message
    assert "Timbre" in message
    assert "provider rejected request" not in message


def test_tts_stream_failure_does_not_blame_voice_configuration():
    message = _tts_failure_message(
        GnaniTTSRequestError("TTS completed without returning audio.")
    )
    assert "stopped before the full reply" in message
    assert "voice" not in message


def test_tts_server_error_is_not_silently_reported_as_success():
    client = GnaniTTS(api_key="test-only", voice="DemoVoice")
    client._ws = FakeSocket([
        json.dumps({"type": "error", "message": "Invalid voice", "code": "invalid_voice"})
    ])

    async def consume():
        return [chunk async for chunk in client.synthesize("Hello", "en-IN")]

    with pytest.raises(GnaniTTSRequestError, match="rejected the speech request"):
        asyncio.run(consume())
    assert client._ws is None


def test_tts_audio_and_completion_events_are_forwarded():
    audio = base64.b64encode(b"synthetic-pcm").decode("ascii")
    client = GnaniTTS(api_key="test-only", voice="DemoVoice")
    client._ws = FakeSocket([
        json.dumps({"type": "audio", "data": {"audio": audio}}),
        json.dumps({"type": "complete", "is_final": True}),
    ])

    async def consume():
        return [chunk async for chunk in client.synthesize("Hello", "en-IN")]

    assert asyncio.run(consume()) == [b"synthetic-pcm"]
    assert client._ws is None


def test_tts_empty_completion_is_reported_as_failure():
    client = GnaniTTS(api_key="test-only", voice="DemoVoice")
    client._ws = FakeSocket([json.dumps({"type": "complete", "is_final": True})])

    async def consume():
        return [chunk async for chunk in client.synthesize("Hello", "en-IN")]

    with pytest.raises(GnaniTTSRequestError, match="without returning audio"):
        asyncio.run(consume())


def test_tts_final_audio_frame_completes_without_separate_event():
    audio = base64.b64encode(b"final-pcm").decode("ascii")
    client = GnaniTTS(api_key="test-only", voice="DemoVoice")
    client._ws = FakeSocket([
        json.dumps({"type": "audio", "data": {"audio": audio, "is_final": True}})
    ])

    async def consume():
        return [chunk async for chunk in client.synthesize("Hello", "en-IN")]

    assert asyncio.run(consume()) == [b"final-pcm"]
    assert client._ws is None


def test_tts_opens_a_fresh_socket_for_each_request(monkeypatch):
    audio = base64.b64encode(b"fresh-pcm").decode("ascii")
    sockets = [
        FakeSocket([
            json.dumps({"type": "audio", "data": {"audio": audio}}),
            json.dumps({"type": "complete", "data": {"is_final": True}}),
        ]),
        FakeSocket([
            json.dumps({"type": "audio", "data": {"audio": audio}}),
            json.dumps({"type": "complete", "data": {"is_final": True}}),
        ]),
    ]
    connected = []

    async def fake_connect(*_args, **_kwargs):
        socket = sockets[len(connected)]
        connected.append(socket)
        return socket

    monkeypatch.setattr("app.voice.gnani_tts.websockets.connect", fake_connect)
    client = GnaniTTS(api_key="test-only", voice="DemoVoice")

    async def consume_twice():
        first = [chunk async for chunk in client.synthesize("First prompt", "en-IN")]
        second = [chunk async for chunk in client.synthesize("Second prompt", "en-IN")]
        return first, second

    assert asyncio.run(consume_twice()) == ([b"fresh-pcm"], [b"fresh-pcm"])
    assert len(connected) == 2
    assert all(socket.closed for socket in connected)
    assert client._ws is None
