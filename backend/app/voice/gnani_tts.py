# backend/app/voice/gnani_tts.py
# P10 — Gnani Timbre v3.0 TTS WebSocket client.
#
# WHY this file exists: TTS must be called from the backend only (key stays
# server-side). Each synthesis request gets a fresh WebSocket because the
# live Timbre endpoint may acknowledge a later request with an empty complete
# event on a reused socket. This avoids silently cutting off the next prompt.
#
# Docs read:
#   https://docs.gnani.ai/api/TTS/tts-websocket.md
#   https://docs.gnani.ai/api/TTS/tts-input-formating.md
#
# IMPORTANT on numbers: Gnani docs say "pass numbers as fully expanded spoken
# words" to avoid mispronunciation. speak.py + render_number() already handle
# this BEFORE text reaches here. Do NOT convert numbers in this file.
#
# Endpoint: wss://api.vachana.ai/api/v1/tts
# Auth header: X-API-Key-ID (exact case from Gnani docs)
#
# Usage:
#   tts = GnaniTTS(api_key, voice="Shivani")
#   async for pcm_bytes in tts.synthesize("Hello ji", "hi-IN", speed=1.0):
#       await browser_ws.send_bytes(pcm_bytes)
#   await tts.cancel()   # on barge_in

import asyncio
import base64
import json
import logging

import websockets

log = logging.getLogger(__name__)

# ── Gnani TTS endpoint (from official docs) ───────────────────────────────────
_TTS_URL = "wss://api.vachana.ai/api/v1/tts"

# ── Allowed Timbre v3.0 speed values (from Gnani docs) ───────────────────────
# WHY clamp: Gnani only accepts 0.8 / 1.0 / 1.2 for Timbre v3.0.
# Sending anything else causes an error response.
_ALLOWED_SPEEDS = {0.8, 1.0, 1.2}
_DEFAULT_SPEED = 1.0


class GnaniTTSRequestError(RuntimeError):
    """A safe, non-secret description of a failed TTS request."""

    def __init__(self, message: str, *, kind: str = "stream"):
        super().__init__(message)
        # Only provider error events should suggest checking voice/account access.
        self.kind = kind


def _clamp_speed(speed: float) -> float:
    """Return the nearest allowed speed value.

    WHY: Gnani v3.0 rejects arbitrary floats. If brain sends 0.9, we quietly
    round to nearest allowed value rather than crashing the session.
    """
    return min(_ALLOWED_SPEEDS, key=lambda s: abs(s - speed))


class GnaniTTS:
    """Manages Timbre v3.0 synthesis for one browser WebSocket session.

    The provider socket opens lazily and closes after each synthesis request.
    On the next request it opens a fresh socket. cancel() also closes the
    current socket immediately when the worker interrupts speech.
    """

    def __init__(self, api_key: str, voice: str):
        # WHY store separately: voice may come from TTS_VOICE env, which can
        # be empty before the listening test. Caller passes it in.
        self._api_key = api_key
        self._voice = voice
        self._ws = None          # the websockets connection (or None if closed)
        self._cancelled = False  # set True on cancel() to stop the streaming loop

    # ── Socket lifecycle ───────────────────────────────────────────────────────

    async def _ensure_connected(self) -> None:
        """Open TTS socket if not already open (lazy connect).

        WHY lazy: app starts before Gnani may be reachable. We connect only
        when we actually need to synthesise something.
        """
        if self._ws is not None:
            # Already open — check if it's still alive by peeking state
            try:
                # websockets >= 10: .closed is a bool property
                if self._ws.closed:
                    self._ws = None
            except AttributeError:
                pass  # older websockets version — assume still open

        if self._ws is None:
            headers = {
                # Exact header name from Gnani TTS docs
                "X-API-Key-ID": self._api_key,
            }
            log.info("GnaniTTS: connecting to %s", _TTS_URL)
            try:
                self._ws = await websockets.connect(_TTS_URL, additional_headers=headers)
            except TypeError:
                self._ws = await websockets.connect(_TTS_URL, extra_headers=headers)  # type: ignore[call-arg]
            log.info("GnaniTTS: connected")

    async def _close_socket(self) -> None:
        """Close the TTS socket. Called on cancel() and on error."""
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        log.debug("GnaniTTS: socket closed")

    # ── Synthesis ──────────────────────────────────────────────────────────────

    async def synthesize(self, text: str, lang: str, speed: float = 1.0):
        """Async generator: synthesise text and yield raw PCM16 byte chunks.

        One TTS request per call. The WebSocket closes when this request ends.
        Gnani response flow per docs:
          server → {"event": "start"}           (synthesis started)
          server → {"event": "audio", "data": {"audio": "<base64>"}}  (chunk)
          ...  (more audio chunks)
          server → {"event": "complete", "is_final": true}             (done)

        WHY generator: gateway can forward each chunk to the browser as it
        arrives, so the first audio byte plays while later chunks are still
        being synthesised. This cuts perceived latency significantly.

        WHY NOT convert numbers here: speak.py already called render_number()
        and produced spoken-word text. Gnani docs say send spoken words, not
        digits. That contract is enforced upstream. This function sends as-is.
        """
        if not text or not text.strip():
            return  # nothing to say

        self._cancelled = False
        speed = _clamp_speed(speed)

        await self._ensure_connected()

        # Request payload — exact field names from Gnani TTS docs.
        # audio_config: raw PCM16 mono at 24000 Hz (gateway forwards as-is).
        # WHY container: "raw" (no WAV header) so we can stream bytes directly
        # to the browser without stripping a header on each chunk.
        request = {
            "text": text,
            "voice": self._voice,
            "model": "timbre-v3.0",
            "language": lang,
            "speed": speed,
            "audio_config": {
                "sample_rate": 24000,
                "num_channels": 1,
                "sample_width": 2,          # 2 bytes = 16-bit
                "encoding": "linear_pcm",
                "container": "raw",         # no WAV header — raw PCM bytes
            },
        }

        try:
            await self._ws.send(json.dumps(request))
        except Exception as exc:
            log.warning("GnaniTTS: send failed (%s)", type(exc).__name__)
            await self._close_socket()
            raise GnaniTTSRequestError("TTS request could not be sent.") from exc

        # Receive audio chunks until "complete" or cancellation
        completed = False
        received_audio = False
        try:
            async for raw in self._ws:
                # Check barge_in cancellation before each chunk
                if self._cancelled:
                    log.debug("GnaniTTS: synthesis cancelled mid-stream")
                    break

                # All Gnani TTS events are JSON text frames (per docs)
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    log.warning("GnaniTTS: non-JSON frame: %r", raw[:80])
                    continue

                event_type = msg.get("event") or msg.get("type", "")
                data = msg.get("data")
                if not isinstance(data, dict):
                    data = {}

                if event_type == "error":
                    error_code = str(msg.get("code") or msg.get("error_code") or "provider_error")[:60]
                    log.error("GnaniTTS: provider rejected synthesis (code=%s)", error_code)
                    await self._close_socket()
                    raise GnaniTTSRequestError(
                        "Gnani rejected the speech request.", kind="rejected"
                    )

                elif event_type == "start":
                    log.debug("GnaniTTS: synthesis started")
                    # Nothing to yield yet — just an ack from server

                elif event_type == "audio":
                    # Decode base64 → raw PCM16 bytes and yield to caller
                    b64 = data.get("audio", "")
                    if b64:
                        try:
                            pcm_bytes = base64.b64decode(b64, validate=True)
                            received_audio = True
                            yield pcm_bytes
                        except Exception as exc:
                            log.warning("GnaniTTS: invalid audio chunk (%s)", type(exc).__name__)
                            raise GnaniTTSRequestError("TTS returned invalid audio data.") from exc

                    # Some deployments mark the final audio frame itself as
                    # final instead of sending a separate complete event.
                    if msg.get("is_final") or data.get("is_final"):
                        log.debug("GnaniTTS: final audio chunk received")
                        completed = True
                        break

                elif event_type == "complete" or msg.get("is_final") or data.get("is_final"):
                    log.debug("GnaniTTS: synthesis complete")
                    completed = True
                    break

        except Exception as exc:
            if self._cancelled:
                return
            if isinstance(exc, GnaniTTSRequestError):
                await self._close_socket()
                raise
            log.warning("GnaniTTS: receive failed (%s)", type(exc).__name__)
            await self._close_socket()
            raise GnaniTTSRequestError("TTS connection ended unexpectedly.") from exc

        if self._cancelled:
            return
        # Reusing the provider socket caused empty completion events for the
        # next prompt, so always start the next synthesis on a clean socket.
        await self._close_socket()
        if not completed:
            raise GnaniTTSRequestError("TTS did not complete the speech request.")
        if not received_audio:
            raise GnaniTTSRequestError("TTS completed without returning audio.")

    # ── Barge-in cancel ────────────────────────────────────────────────────────

    async def cancel(self) -> None:
        """Cancel any in-progress synthesis and close the socket.

        WHY close socket: Gnani does not support mid-stream cancel on the same
        connection — we must drop the socket. It reopens lazily on next call.
        This is fast (< 5ms) since we're just closing a socket handle.

        Called by gateway on "barge_in" from browser (worker presses button
        while agent is speaking). Gateway sends "tts_end" to browser after this.
        """
        self._cancelled = True
        await self._close_socket()
        log.debug("GnaniTTS: cancelled")

    # ── Cleanup ────────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close TTS socket at end of session."""
        await self._close_socket()
