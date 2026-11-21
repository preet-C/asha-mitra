# backend/app/voice/gnani_stt.py
# P10 — Gnani Prisma v3.0 STT WebSocket client.
#
# WHY this file exists: The browser cannot set custom WebSocket headers (browser
# security restriction), so the backend opens the Gnani socket with the API key
# and all config headers, then forwards audio frames from the browser to Gnani.
# This keeps the API key server-side only (rule 6, AGENTS.md).
#
# Docs read: https://docs.gnani.ai/api/STT/stt-websocket.md
# Endpoint:  wss://api.vachana.ai/stt/v3/stream
#
# Usage:
#   stt = GnaniSTT(api_key, lang="hi-IN", sample_rate=16000)
#   await stt.connect()
#   await stt.send_audio(pcm_bytes)
#   await stt.commit()
#   async for event in stt.listen():
#       if event["type"] == "transcript":
#           print(event["text"])
#   await stt.close()

import asyncio
import json
import logging
import pathlib

import websockets

log = logging.getLogger(__name__)

# ── Gnani STT endpoint (from official docs) ───────────────────────────────────
_STT_URL = "wss://api.vachana.ai/stt/v3/stream"

# ── Frame size Gnani requires: exactly 1024 bytes = 512 PCM16 samples ─────────
# WHY fixed size: Gnani STT processes audio in fixed-size frames. Any deviation
# causes VAD to misbehave or the stream to error. Source: PLAN.md P10.
_FRAME_BYTES = 1024

# ── 15-minute session cap (Gnani closes the socket after this) ────────────────
# WHY track this: Gnani will close the connection at 15 min. We reconnect
# quietly so the worker never sees an interruption. Source: PLAN.md P10.
_SESSION_CAP_SECONDS = 14 * 60  # reconnect at 14 min to avoid hitting the cap

# ── Health words the Gnani model should favour (improves accuracy on ASHA terms)
# Source: PLAN.md P10 keyterms list + all synthetic beneficiary names.
# Max 200 terms per Gnani docs.
_BASE_KEYTERMS = [
    # ASHA programme terms
    "ASHA", "ANM", "PHC", "ANC", "PNC", "HBNC", "MCP", "IFA",
    # Vaccines (ID strings as spoken — Gnani transcribes these)
    "BCG", "OPV", "Penta", "Penta 1", "Penta 2", "Penta 3",
    "fIPV", "RVV", "PCV", "MR", "Rotavirus", "DPT",
    "Td", "TD1", "TD2", "Vitamin A", "Anganwadi",
    # Common ASHA spoken words
    "TT injection", "TT", "IFA goli", "IFA tablet",
    "home visit", "immunisation", "vaccination",
    # Danger sign keywords (English forms — model hears Hinglish often)
    "fever", "convulsion", "fits", "jaundice", "anaemia",
    "bleeding", "discharge", "navel", "cord",
    # Weights & measurements
    "kilogram", "kilo", "gram",
]


def _load_beneficiary_names() -> list[str]:
    """Load synthetic beneficiary names so STT knows these names.

    WHY: Gnani docs say keyterms improve accuracy on names. ASHA workers say the
    child's or mother's name while giving visit notes. Without this hint the STT
    may mishear uncommon names.
    """
    data_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "app" / "data" / "synthetic_beneficiaries.json"
    )
    try:
        import json as _json
        with open(data_path, encoding="utf-8") as f:
            people = _json.load(f)
        # Each person has a "name" field like "Sunita Devi"
        return [p["name"] for p in people if p.get("name")]
    except Exception as exc:
        log.warning("Could not load beneficiary names for keyterms: %s", exc)
        return []


# Build once at import time — stays well under 200 terms.
_KEYTERMS: list[str] = (_BASE_KEYTERMS + _load_beneficiary_names())[:200]


class GnaniSTT:
    """Manages one Gnani Prisma v3.0 STT WebSocket session.

    One instance per browser WebSocket session. Create a new instance
    for each new visitor (or on reconnect after 15-min cap).
    """

    def __init__(self, api_key: str, lang: str = "hi-IN", sample_rate: int = 16000):
        # WHY store these: needed both at connect() and on reconnect().
        self._api_key = api_key
        self._lang = lang
        self._sample_rate = sample_rate

        self._ws = None          # the websockets connection object
        self._buf = bytearray()  # leftover bytes that haven't filled a full frame yet
        self._connected = False
        self._connect_time: float | None = None  # epoch seconds at last connect

    # ── Connection ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open the Gnani STT WebSocket with all required headers.

        Headers are set at connection time only — Gnani does not support changing
        most of them mid-session without a reconnect. Source: Gnani STT docs.
        """
        # WHY json.dumps for keyterms: Gnani docs say keyterms header must be
        # ASCII-escaped JSON list (not a plain comma-separated string).
        keyterms_json = json.dumps(_KEYTERMS, ensure_ascii=True)

        headers = {
            # Auth — exact header name from Gnani docs
            "x-api-key-id": self._api_key,
            # Model selection — required for Prisma v3.0 (hackathon spec)
            "model": "prisma-v3.0",
            # Language: comma-separated BCP-47 codes so STT handles code-mix.
            # Gateway updates this on "setting" action by reconnecting.
            "language_code": self._lang,
            # Sample rate must match what the browser AudioWorklet sends.
            # Browser sends 16000 by default; fallback to native rate if refused.
            "x-sample-rate": str(self._sample_rate),
            # "transcribe" mode: formats numbers as digits, cleaner for extraction.
            # A/B test vs "codemix" during noise tuning (P11).
            "format": "transcribe",
            # Keyterms: JSON-encoded list, max 200. Improves recall on ASHA vocab.
            "keyterms": keyterms_json,
            # Context hint: helps the model bias towards medical / ASHA domain.
            "topic": "ASHA home visit notes: pregnancy, newborn, immunisation",
            # Keep session alive for quiet dictation (default 60s is too short).
            "x-idle-timeout-sec": "300",
            # VAD threshold: 0.6 is standard; raise to 0.65-0.75 in noisy rooms.
            "x-vad-threshold": "0.6",
            # Minimum silence between utterances — 700ms suits dictation pace.
            "x-min-silence-ms": "700",
            # Minimum speech length to trigger a segment — 150ms standard.
            "x-min-speech-ms": "150",
        }

        log.info("GnaniSTT: connecting to %s (lang=%s, rate=%d)", _STT_URL, self._lang, self._sample_rate)

        # websockets >= 10 uses additional_headers; < 10 uses extra_headers.
        # Try the newer kwarg first, fall back so old installs don't break.
        try:
            self._ws = await websockets.connect(_STT_URL, additional_headers=headers)
        except TypeError:
            self._ws = await websockets.connect(_STT_URL, extra_headers=headers)  # type: ignore[call-arg]

        import time
        self._connect_time = time.monotonic()
        self._connected = True
        self._buf = bytearray()  # fresh buffer on each connect
        log.info("GnaniSTT: connected")

    async def reconnect(self) -> None:
        """Silently reconnect when the 15-min session cap is approaching.

        WHY silent: worker should not notice. We just open a fresh socket and
        keep streaming. The partial utterance since last commit is lost, but
        commits happen at button-release, so this window is tiny.
        """
        log.info("GnaniSTT: reconnecting (15-min cap)")
        await self.close()
        await self.connect()

    # ── Audio ──────────────────────────────────────────────────────────────────

    async def send_audio(self, chunk: bytes) -> None:
        """Buffer incoming bytes and flush complete 1024-byte frames to Gnani.

        WHY re-chunk: Gnani requires exactly 1024 bytes per frame. The browser
        AudioWorklet fires arbitrary chunk sizes (depends on browser, latency,
        and worklet buffer). We buffer here and emit only full frames.

        WHY NOT send partial frame immediately: sending < 1024 bytes causes
        Gnani VAD to miscount samples and may produce garbage transcripts.
        """
        if not self._connected or self._ws is None:
            return

        # Check 15-min cap and reconnect quietly if near the limit.
        import time
        if self._connect_time and (time.monotonic() - self._connect_time) > _SESSION_CAP_SECONDS:
            await self.reconnect()

        self._buf.extend(chunk)

        # Drain complete frames
        while len(self._buf) >= _FRAME_BYTES:
            frame = bytes(self._buf[:_FRAME_BYTES])
            self._buf = self._buf[_FRAME_BYTES:]
            try:
                await self._ws.send(frame)
            except Exception as exc:
                log.warning("GnaniSTT: send_audio error: %s", exc)
                self._connected = False
                return

    async def flush_and_commit(self) -> None:
        """Send any remaining buffered bytes (zero-padded) then send commit.

        WHY zero-pad: leftover bytes after the last full frame are padded to
        exactly 1024 bytes so Gnani processes the tail of the utterance.
        Without this, the last ~10ms of speech is silently dropped.

        WHY commit JSON: Gnani docs say sending {"type":"commit"} forces
        immediate VAD segmentation without waiting for the silence timeout.
        This cuts latency by up to 700ms on button-release.
        """
        if not self._connected or self._ws is None:
            return

        # Flush leftover bytes, zero-padded to full frame
        if len(self._buf) > 0:
            padded = bytes(self._buf) + b"\x00" * (_FRAME_BYTES - len(self._buf))
            self._buf = bytearray()
            try:
                await self._ws.send(padded)
            except Exception as exc:
                log.warning("GnaniSTT: flush error: %s", exc)

        # Send commit signal
        await self.commit()

    async def commit(self) -> None:
        """Tell Gnani the utterance is complete (button released).

        WHY separate from flush_and_commit: gateway may want to call commit
        without flushing in some edge cases (e.g., timeout recovery).
        """
        if not self._connected or self._ws is None:
            return
        try:
            await self._ws.send(json.dumps({"type": "commit"}))
            log.debug("GnaniSTT: commit sent")
        except Exception as exc:
            log.warning("GnaniSTT: commit error: %s", exc)
            self._connected = False

    # ── Event stream ───────────────────────────────────────────────────────────

    async def listen(self):
        """Async generator that yields parsed Gnani events as dicts.

        Event types yielded (from Gnani docs):
          {"type": "connected", ...config...}
          {"type": "speech_start"}
          {"type": "processing"}
          {"type": "transcript", "text": "...", "latency": ..., "detected_language_code": "hi-IN"}
          {"type": "error", "message": "..."}
          {"type": "settings_updated"}  — confirm of update_settings control frame

        WHY generator: gateway consumes events one by one in a loop. Generator
        lets us separate "receive from Gnani" from "process in brain" cleanly.
        """
        if self._ws is None:
            return

        try:
            async for raw in self._ws:
                # Gnani sends JSON text frames (not binary) for all events.
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    log.warning("GnaniSTT: non-JSON frame: %r", raw[:120])
                    continue

                log.debug("GnaniSTT event: %s", event.get("type"))
                yield event

        except websockets.exceptions.ConnectionClosedOK:
            log.info("GnaniSTT: connection closed normally")
        except websockets.exceptions.ConnectionClosedError as exc:
            log.warning("GnaniSTT: connection closed with error: %s", exc)
        except Exception as exc:
            log.warning("GnaniSTT: listen error: %s", exc)

    # ── Cleanup ────────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the STT WebSocket cleanly."""
        self._connected = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass  # already closed — ignore
            self._ws = None
        log.debug("GnaniSTT: closed")
