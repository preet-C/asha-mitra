# backend/app/voice/gateway.py
# P10 — Voice gateway: one instance per browser WebSocket session.
#
# WHY this file exists: This is the central traffic cop. It bridges the
# browser WebSocket (contract 4.5) with Gnani STT, the brain (dialogue.py),
# and Gnani TTS. All three are kept strictly separate:
#   - Brain (dialogue.py): frozen, never edited here.
#   - speak() (speak.py): frozen, called here to get TTS text.
#   - Gnani STT/TTS: handled by gnani_stt.py / gnani_tts.py.
#
# Session lifecycle:
#   Browser connects → start → audio frames → commit → brain → TTS
#   → browser plays audio → worker corrects → commit → brain → TTS → save
#
# Contract 4.5 (browser ↔ server messages): docs/PLAN.md section 4.5.
#
# Latency target: first audio < 3s after button release.
# Key optimisations here:
#   1. Instant ack (cached "ji...") plays on commit before transcript arrives.
#   2. TTS cache for Tier A lines (disclosure, refer_phc, etc.) = 0 TTS latency.
#   3. Read-back split at ". " so first sentence plays before rest is synthesised.
#   4. Fresh TTS socket per request so each prompt starts with a clean stream.

import asyncio
import json
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.brain.dialogue import handle, new_session
from app.brain.speak import speak
from app.brain.templates import get_danger_sign_label
from app.voice.gnani_stt import GnaniSTT
from app.voice.gnani_tts import GnaniTTS, GnaniTTSRequestError
from app.voice.tts_cache import get_cached

log = logging.getLogger(__name__)

# How long to wait for a transcript after commit before giving up.
# 2.5s matches PLAN.md P10 ("wait for next transcript or 2.5s timeout").
_TRANSCRIPT_TIMEOUT_S = 2.5

# TTS sample rate that Gnani Timbre v3.0 outputs (from PLAN.md P10 + TTS docs).
# Browser's AudioContext is told this via tts_start so it can play correctly.
_TTS_SAMPLE_RATE = 24000

# Minimum text length (chars) before splitting into 2 TTS requests.
# Short texts (e.g. "जी...") must NOT be split — the join pause would be odd.
_SPLIT_MIN_CHARS = 60


def _http_status(exc: Exception) -> int | None:
    """Read a WebSocket handshake status without logging headers or secrets."""
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _stt_connection_message(exc: Exception) -> str:
    status = _http_status(exc)
    if status in (401, 403):
        return f"Gnani rejected the STT connection (HTTP {status}). Check that the key is active and the account has Prisma STT access."
    if status == 429:
        return "Gnani STT is rate-limited or out of quota (HTTP 429). Check the account limits and retry."
    if status in (400, 404, 422):
        return f"Gnani rejected the STT settings (HTTP {status}). Check the selected language and Prisma access."
    return f"Speech recognition could not connect ({type(exc).__name__}). Check network access and Gnani STT access, then retry."


def _tts_failure_message(exc: Exception) -> str:
    status = _http_status(exc)
    if status in (401, 403):
        return f"Gnani rejected the TTS connection (HTTP {status}). Check that the key is active and the account has Timbre access."
    if status == 429:
        return "Gnani TTS is rate-limited or out of quota (HTTP 429). Check the account limits and retry."
    if isinstance(exc, GnaniTTSRequestError):
        if exc.kind == "rejected":
            return "Gnani rejected the TTS request. Check the selected voice and that the account has Timbre access."
        return "Timbre audio stopped before the full reply finished. Retry the connection."
    if status:
        return f"Gnani rejected the TTS request (HTTP {status}). Check the voice name and Timbre v3.0 access."
    return f"Speech playback failed ({type(exc).__name__}). Check the Gnani connection and voice configuration."


class GnaniGateway:
    """Manages one browser WebSocket session end-to-end.

    Create one instance per WebSocket connection. Call run(websocket).
    The instance is discarded when the browser disconnects.
    """

    def __init__(self, repo=None):
        self._repo = repo
        self._stt: GnaniSTT | None = None
        self._tts: GnaniTTS | None = None
        self._session: dict | None = None          # brain session dict
        self._tts_task: asyncio.Task | None = None # current TTS streaming task
        self._stt_reader_task: asyncio.Task | None = None
        self._barge_active = asyncio.Event()       # set during barge_in cancel
        self._transcript_parts: list[str] = []    # collects STT segments since last commit
        self._transcript_ready = asyncio.Event()  # signals that commit transcript is in
        self._ws: WebSocket | None = None          # browser WebSocket (set in run())
        self._t0: float | None = None             # time of last commit (for latency calc)
        self._first_audio_sent: bool = False      # True once first audio byte is forwarded

    # ── Main entry point ───────────────────────────────────────────────────────

    async def run(self, websocket: WebSocket) -> None:
        """Main loop: accept browser messages and orchestrate STT/brain/TTS.

        The browser listener runs here. The STT reader starts only after the
        STT socket connects, so it cannot race ahead and exit before connect.
        """
        self._ws = websocket
        await websocket.accept()
        log.info("Gateway: browser connected")

        try:
            await self._browser_listener()
        except WebSocketDisconnect:
            log.info("Gateway: browser disconnected")
        except Exception as exc:
            log.exception("Gateway: unexpected error: %s", exc)
            await self._send_json({"type": "error", "message": "Internal server error"})
        finally:
            await self._cleanup()

    # ── Browser message listener ───────────────────────────────────────────────

    async def _browser_listener(self) -> None:
        """Receive and dispatch messages from the browser WebSocket.

        Message types (contract 4.5):
          JSON text: start, commit, barge_in, end
          Binary:    PCM16 audio frames from the microphone
        """
        while True:
            # Read raw ASGI frames so JSON control text and binary audio both survive.
            message = await self._ws.receive()
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(code=message.get("code", 1000))

            text_frame = message.get("text")
            if text_frame is not None:
                try:
                    await self._handle_json(json.loads(text_frame))
                except json.JSONDecodeError:
                    log.warning("Gateway: unrecognised text frame: %r", text_frame[:80])
                continue

            audio_frame = message.get("bytes")
            if audio_frame is not None:
                # Binary control frames are allowed; other binary frames are PCM audio.
                try:
                    msg = json.loads(audio_frame.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    await self._handle_audio(audio_frame)
                else:
                    await self._handle_json(msg)

    async def _handle_json(self, msg: dict) -> None:
        """Dispatch a JSON control message from the browser."""
        mtype = msg.get("type")

        if mtype == "start":
            await self._on_start(msg)
        elif mtype == "commit":
            await self._on_commit()
        elif mtype == "barge_in":
            await self._on_barge_in()
        elif mtype == "end":
            await self._on_end()
        else:
            log.warning("Gateway: unknown message type: %r", mtype)

    async def _handle_audio(self, chunk: bytes) -> None:
        """Forward a raw PCM16 chunk from the browser to Gnani STT.

        GnaniSTT.send_audio() handles 1024-byte re-chunking internally.
        Only send while STT is connected (i.e. after "start" message arrived).
        """
        if self._stt is not None:
            await self._stt.send_audio(chunk)

    # ── start ──────────────────────────────────────────────────────────────────

    async def _on_start(self, msg: dict) -> None:
        """Browser pressed the language button — open STT, say disclosure.

        Steps:
          1. Create brain session with chosen language.
          2. Open Gnani STT socket.
          3. Send {"type":"ready"} to browser.
          4. Play cached disclosure immediately (zero TTS latency for first word).
          5. Send brain "start" event to get the disclosure + ask_id actions.
             (Brain also returns these; we play the cached one first for speed,
             then the brain's disclosure is skipped — see _play_say_action.)
        """
        lang = msg.get("lang", "hi-IN")
        sample_rate = msg.get("sample_rate", 16000)

        # Keep one brain/STT session across multiple tap-to-talk turns.
        if self._session is not None and self._stt is not None:
            log.info("Gateway: duplicate start ignored; session is already active")
            return

        log.info("Gateway: start (lang=%s, rate=%d)", lang, sample_rate)

        # Create the brain session (new_session sets all required fields).
        self._session = new_session(lang, repo=self._repo)

        settings = get_settings()
        api_key = settings.GNANI_API_KEY.strip()
        voice = settings.TTS_VOICE.strip()

        if not api_key:
            await self._send_json({
                "type": "error",
                "message": "Live voice is not configured. Add GNANI_API_KEY to backend/.env and restart the backend.",
            })
            return

        if not voice:
            await self._send_json({
                "type": "error",
                "message": "Live voice is not configured. Set TTS_VOICE in backend/.env and restart the backend.",
            })
            return

        # Initialise STT and TTS clients
        self._stt = GnaniSTT(api_key=api_key, lang=lang, sample_rate=sample_rate)
        self._tts = GnaniTTS(api_key=api_key, voice=voice)

        # Open STT socket (non-fatal if it fails — session continues without STT)
        try:
            await self._stt.connect()
        except Exception as exc:
            status = _http_status(exc)
            log.warning(
                "Gateway: STT connect failed (%s, http_status=%s)",
                type(exc).__name__, status,
            )
            await self._send_json({
                "type": "error",
                "message": _stt_connection_message(exc),
            })
            await self._stt.close()
            self._stt = None
            if self._tts:
                await self._tts.close()
                self._tts = None
            return

        # Start reading only after connect() has populated the provider socket.
        self._stt_reader_task = asyncio.create_task(self._stt_reader())

        # Tell browser we're ready
        await self._send_json({"type": "ready"})

        # Play cached disclosure immediately — Tier A, never generated.
        # WHY cached: disclosure is the very first audio the worker hears.
        # Zero-latency start makes the app feel snappy.
        disclosure_pcm = get_cached("disclosure", lang)
        disclosure_played_from_cache = False
        if disclosure_pcm and self._tts:
            await self._stream_pcm_to_browser("disclosure", disclosure_pcm)
            disclosure_played_from_cache = True

        # Send "start" to brain → returns [say disclosure, say ask_id]
        actions = handle(self._session, {"type": "start", "lang": lang})
        for action in actions:
            # Skip "say disclosure" if we already played the cached version
            if (action.get("type") == "say"
                    and action.get("key") == "disclosure"
                    and disclosure_played_from_cache):
                continue
            await self._process_action(action)

    # ── commit ─────────────────────────────────────────────────────────────────

    async def _on_commit(self) -> None:
        """Button released — flush audio buffer, wait for transcript, run brain.

        Latency critical path:
          t0 = now
          → instant ack plays (cached "ji...")
          → STT commit sent
          → transcript collected (up to 2.5s)
          → brain.handle()
          → speak() → TTS → first audio byte
          t1 = first audio byte
          → send latency message
        """
        if self._stt is None or self._session is None:
            return

        self._t0 = time.monotonic()
        self._first_audio_sent = False
        log.info("Gateway: commit received")

        # Play instant ack so worker knows we heard them (cuts perceived wait).
        # WHY before waiting for transcript: starts immediately, overlaps with
        # the STT processing time — worker hears "जी..." in < 50ms.
        lang = self._session.get("lang", "hi-IN")
        ack_pcm = get_cached("ack", lang)
        if ack_pcm and self._tts:
            # Fire-and-forget: ack plays while STT processes in parallel.
            asyncio.create_task(self._stream_pcm_to_browser("ack", ack_pcm))

        # Flush leftover audio buffer + send commit to Gnani STT
        self._transcript_parts = []
        self._transcript_ready.clear()
        await self._stt.flush_and_commit()

        # Wait for the transcript (collected by _stt_reader in parallel task)
        try:
            await asyncio.wait_for(
                self._transcript_ready.wait(),
                timeout=_TRANSCRIPT_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            log.warning("Gateway: transcript timeout after %.1fs", _TRANSCRIPT_TIMEOUT_S)

        # Join all segments received since last commit
        transcript_text = " ".join(self._transcript_parts).strip()
        self._transcript_parts = []

        # Log transcript — redact in prod (rule: never log transcript in prod)
        app_env = get_settings().APP_ENV
        if app_env != "prod":
            log.info("Gateway: transcript: %r", transcript_text)
        else:
            log.info("Gateway: transcript received (redacted in prod)")

        # Send transcript to browser (UI shows live text)
        await self._send_json({"type": "transcript", "text": transcript_text})

        # Run brain — returns a list of ordered action dicts
        actions = handle(self._session, {"type": "user_text", "text": transcript_text})

        for action in actions:
            await self._process_action(action)

    # ── barge_in ───────────────────────────────────────────────────────────────

    async def _on_barge_in(self) -> None:
        """Worker pressed button while agent is speaking — cancel TTS immediately.

        WHY cancel task + set event: GnaniTTS.cancel() closes the socket.
        _barge_active event tells any in-progress _stream_pcm_to_browser loop
        to stop sending chunks to the browser even if cancel() races with it.
        """
        log.info("Gateway: barge_in")
        self._barge_active.set()

        # Cancel the in-progress TTS streaming task if one exists
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass

        # Cancel Gnani TTS socket (must happen after task cancel)
        if self._tts:
            await self._tts.cancel()

        # Tell browser TTS stream is over
        await self._send_json({"type": "tts_end"})

        # Clear barge flag so next TTS can start cleanly
        self._barge_active.clear()

    # ── end ────────────────────────────────────────────────────────────────────

    async def _on_end(self) -> None:
        """Browser sent "end" — close all sockets cleanly."""
        log.info("Gateway: end")
        await self._cleanup()

    # ── STT event reader ───────────────────────────────────────────────────────

    async def _stt_reader(self) -> None:
        """Read Gnani STT events continuously (runs as a parallel task).

        WHY separate from browser listener: STT events arrive asynchronously
        from Gnani — we can't block the browser message loop waiting for them.
        This task collects transcript segments and signals commit() when ready.
        """
        stt = self._stt
        if stt is None:
            return

        async for event in stt.listen():
            etype = event.get("type", "")

            if etype == "transcript":
                text = event.get("text", "").strip()
                if text:
                    self._transcript_parts.append(text)
                # Signal that transcript is ready (commit() is waiting on this)
                self._transcript_ready.set()

            elif etype == "speech_start":
                log.debug("Gateway: STT speech_start")

            elif etype == "processing":
                log.debug("Gateway: STT processing (utterance ended, transcribing)")

            elif etype == "error":
                log.error("Gateway: STT error: %s", event)
                await self._send_json({
                    "type": "error",
                    "message": f"STT error: {event.get('message', 'unknown')}"
                })
                # Unblock any waiting commit() so the session doesn't freeze
                self._transcript_ready.set()

            elif etype == "connected":
                log.debug("Gateway: STT confirmed connected: %s", event)

    # ── Action dispatcher ──────────────────────────────────────────────────────

    async def _process_action(self, action: dict) -> None:
        """Execute one action returned by brain.handle().

        Action types (contract 4.3):
          say     → TTS → stream PCM to browser
          alert   → danger banner + cached refer_phc audio
          card    → forward card JSON to browser
          saved   → forward saved JSON to browser
          setting → update STT/TTS params + forward to browser
        """
        atype = action.get("type")

        if atype == "say":
            await self._play_say_action(action)

        elif atype == "alert":
            await self._play_alert_action(action)

        elif atype == "card":
            await self._send_json({
                "type": "card",
                "draft": action.get("draft", {}),
                "uncertain": action.get("uncertain", []),
            })

        elif atype == "saved":
            await self._send_json({
                "type": "saved",
                "visit_id": action.get("visit_id", ""),
            })

        elif atype == "setting":
            await self._handle_setting_action(action)

        else:
            log.warning("Gateway: unknown action type: %r", atype)

    # ── say action → TTS ───────────────────────────────────────────────────────

    async def _play_say_action(self, action: dict) -> None:
        """Get text from speak(), split it, stream each segment via TTS.

        WHY use action["_text"]: dialogue.py pre-renders _text in every say
        action via speak(). We re-use it instead of calling speak() again.
        (Calling speak() twice returns the same text but wastes time and may
        pick a different Tier B variant on the second call.)

        WHY split at ". ": send 2-3 short TTS requests so the first audio
        starts playing while later segments are still being synthesised.
        This cuts perceived latency by 200-400ms on a full read-back.
        """
        # Use pre-rendered text from brain if available; fall back to speak()
        text = action.get("_text") or speak(action, self._session)

        if not text or not text.strip():
            return

        if self._tts is None:
            log.warning("Gateway: TTS not available — skipping say action key=%r", action.get("key"))
            return

        lang = self._session.get("lang", "hi-IN")
        # Speed may be set by a "setting" action from the intent router (P5b)
        speed = self._session.get("tts_speed", 1.0)

        # Split long text into 2-3 segments for lower latency.
        segments = _split_text(text)

        # Send tts_start once before all segments begin
        await self._send_json({
            "type": "tts_start",
            "sample_rate": _TTS_SAMPLE_RATE,
            "text": text,  # full text so UI can show subtitle
        })

        for segment in segments:
            if self._barge_active.is_set():
                break  # barge_in arrived — stop immediately

            # Stream this segment chunk by chunk
            try:
                async for pcm_chunk in self._tts.synthesize(segment, lang, speed=speed):
                    if self._barge_active.is_set():
                        break

                    # Report latency on the very first audio byte of the full response
                    if not self._first_audio_sent:
                        self._first_audio_sent = True
                        if self._t0 is not None:
                            latency_ms = int((time.monotonic() - self._t0) * 1000)
                            await self._send_json({
                                "type": "latency",
                                "what": "first_audio",
                                "ms": latency_ms,
                            })
                            log.info("Gateway: first_audio latency %dms", latency_ms)

                    await self._ws.send_bytes(pcm_chunk)
            except Exception as exc:
                log.warning(
                    "Gateway: TTS request failed (%s, http_status=%s)",
                    type(exc).__name__, _http_status(exc),
                )
                await self._send_json({
                    "type": "error",
                    "message": _tts_failure_message(exc),
                })
                return

        # Send tts_end after all segments (unless barge_in already sent it)
        if not self._barge_active.is_set():
            await self._send_json({"type": "tts_end"})

    # ── alert action ───────────────────────────────────────────────────────────

    async def _play_alert_action(self, action: dict) -> None:
        """Send danger banner JSON + play cached refer_phc audio immediately.

        WHY cached: danger alert is the most time-critical audio in the whole
        system. A live TTS round-trip would add 300-600ms. Cached = instant.
        WHY alert fires before other speech: brain.handle() already returns
        alert actions first (see dialogue.py _check_danger). We honour that
        order here — alert fires before any "say" actions in the same list.
        """
        signs = action.get("signs", [])
        lang = self._session.get("lang", "hi-IN") if self._session else "hi-IN"

        # Use closed-list labels so the worker sees which recorded flag needs review.
        labeled_signs = [
            {**sign, "label": get_danger_sign_label(sign.get("id", ""), lang)}
            for sign in signs
        ]
        await self._send_json({"type": "alert", "signs": labeled_signs})

        if self._tts is None:
            return

        # Play cached refer_phc audio for each sign
        for sign_id in signs:
            cache_key = f"refer_phc_{sign_id}"
            pcm = get_cached(cache_key, lang)

            if pcm:
                # Cache hit — play instantly
                await self._stream_pcm_to_browser(cache_key, pcm)
            else:
                # Cache miss — fall back to live TTS
                action_say = {
                    "type": "say",
                    "key": "refer_phc",
                    "vars": {"signs": [sign_id]},
                }
                await self._play_say_action(action_say)

    # ── setting action ─────────────────────────────────────────────────────────

    async def _handle_setting_action(self, action: dict) -> None:
        """Handle language/speed change from brain (intent router P5b).

        WHY reconnect STT: Gnani STT headers (including language_code) are set
        at connection time. The docs mention a settings_updated event from an
        update_settings control frame, but to be safe we reconnect the socket.
        Plan P10 says: "check STT doc whether settings can change on the open
        socket, else reconnect" — we reconnect for reliability.
        """
        if self._session is None:
            return

        new_lang = action.get("lang")
        new_speed = action.get("speed")

        if new_lang and self._session.get("lang") != new_lang:
            log.info("Gateway: language switch %s → %s", self._session["lang"], new_lang)
            self._session["lang"] = new_lang

            # Reconnect STT with new language header
            if self._stt:
                if self._stt_reader_task and not self._stt_reader_task.done():
                    self._stt_reader_task.cancel()
                    try:
                        await self._stt_reader_task
                    except asyncio.CancelledError:
                        pass
                self._stt._lang = new_lang
                await self._stt.reconnect()
                self._stt_reader_task = asyncio.create_task(self._stt_reader())

        if new_speed is not None:
            # Store speed in session so _play_say_action picks it up
            self._session["tts_speed"] = new_speed
            log.info("Gateway: TTS speed set to %s", new_speed)

        # Tell browser the setting changed (UI shows current language chip)
        setting_msg: dict = {"type": "setting"}
        if new_lang:
            setting_msg["lang"] = new_lang
        if new_speed is not None:
            setting_msg["speed"] = new_speed
        await self._send_json(setting_msg)

    # ── PCM streaming helpers ──────────────────────────────────────────────────

    async def _stream_pcm_to_browser(self, label: str, pcm: bytes) -> None:
        """Stream raw PCM16 bytes from cache to the browser.

        Sends tts_start → binary chunks → tts_end.
        WHY 4096-byte chunks: balances frame count vs jitter on slow connections.
        """
        if self._barge_active.is_set():
            return

        await self._send_json({
            "type": "tts_start",
            "sample_rate": _TTS_SAMPLE_RATE,
            "text": "",  # cached audio has no subtitle text
        })

        chunk_size = 4096
        pos = 0
        while pos < len(pcm):
            if self._barge_active.is_set():
                break
            await self._ws.send_bytes(pcm[pos : pos + chunk_size])
            pos += chunk_size

        if not self._barge_active.is_set():
            await self._send_json({"type": "tts_end"})

    # ── JSON send helper ───────────────────────────────────────────────────────

    async def _send_json(self, data: dict) -> None:
        """Send a JSON message to the browser. Swallows send errors gracefully.

        WHY swallow: browser may disconnect at any time. We don't want a send
        error on a "tts_end" message to crash the whole session.
        """
        try:
            await self._ws.send_text(json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            log.debug("Gateway: send_json failed (browser disconnected?): %s", exc)

    # ── Cleanup ────────────────────────────────────────────────────────────────

    async def _cleanup(self) -> None:
        """Close all sockets cleanly when session ends."""
        if self._stt_reader_task and not self._stt_reader_task.done():
            self._stt_reader_task.cancel()
            try:
                await self._stt_reader_task
            except asyncio.CancelledError:
                pass
        self._stt_reader_task = None
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()
        if self._stt:
            await self._stt.close()
            self._stt = None
        if self._tts:
            await self._tts.close()
            self._tts = None
        log.info("Gateway: session cleaned up")


# ── Text split helper ──────────────────────────────────────────────────────────

def _split_text(text: str) -> list[str]:
    """Split a long spoken text at sentence boundaries for lower TTS latency.

    WHY split: gateway sends the first segment to Gnani TTS immediately.
    While the browser plays segment 1, segment 2 is being synthesised.
    This cuts perceived latency on a full 5-field read-back by ~300ms.

    Rules:
    - Only split if text is long enough (>= _SPLIT_MIN_CHARS).
    - Split at ". " boundaries only — never mid-sentence or mid-field.
    - Cap at 3 segments maximum (more = too many TTS round-trips).
    - Merge very short segments (< 15 chars) into the previous one.
    """
    if len(text) < _SPLIT_MIN_CHARS:
        return [text]

    # Split at ". " — build_summary() in speak.py inserts real periods.
    raw_parts = text.split(". ")

    # Reconstruct parts with ". " added back (except the last)
    parts = []
    for i, p in enumerate(raw_parts):
        p = p.strip()
        if not p:
            continue
        if i < len(raw_parts) - 1:
            p = p + "."
        parts.append(p)

    # Merge very short fragments into the previous segment
    merged: list[str] = []
    for part in parts:
        if merged and len(part) < 15:
            merged[-1] = merged[-1] + " " + part
        else:
            merged.append(part)

    # Cap at 3 segments — merge everything beyond index 2 into the third
    if len(merged) <= 3:
        return merged

    head = merged[:2]
    tail = " ".join(merged[2:])
    return head + [tail]
