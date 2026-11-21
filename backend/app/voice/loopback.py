# backend/app/voice/loopback.py
# WHY this file: proof that phone mic → backend → phone speaker works,
# with no Gnani calls. Collects PCM16 audio until "commit", writes a WAV
# so we can listen to it on laptop, then sends back a 2-second 440 Hz tone.
#
# Used ONLY by /ws/loopback (P9 spike). Delete or ignore in production.

import asyncio
import json
import math
import struct

from fastapi import WebSocket, WebSocketDisconnect


# ── WAV header helper ─────────────────────────────────────────────────────────

def _make_wav_header(num_samples: int, sample_rate: int = 16000) -> bytes:
    """Build a minimal 44-byte WAV header for mono PCM16 audio.

    WHY manual header: we don't want to add an extra library just for the
    loopback spike. struct.pack is stdlib and always available.
    """
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = num_samples * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,            # PCM subchunk size
        1,             # audio format: PCM
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header


# ── 440 Hz test tone generator ────────────────────────────────────────────────

def _make_tone(duration_s: float = 2.0, sample_rate: int = 24000, freq: float = 440.0) -> bytes:
    """Generate a 440 Hz sine wave as raw PCM16 little-endian bytes.

    WHY 24000 Hz: matches the TTS output rate used in contract 4.5 so the
    browser player code path is exercised at the same sample rate as real TTS.
    WHY 440 Hz: audible, standard A4 pitch, easy to confirm it's working.
    """
    n_samples = int(duration_s * sample_rate)
    # Build as list of Int16 values, then pack all at once (faster than appending)
    samples = []
    for i in range(n_samples):
        # sine wave, amplitude 0.4 so it's not too loud
        value = int(0.4 * 32767 * math.sin(2 * math.pi * freq * i / sample_rate))
        # clamp to Int16 range just in case
        value = max(-32768, min(32767, value))
        samples.append(value)
    return struct.pack(f"<{n_samples}h", *samples)


# ── loopback WebSocket handler ────────────────────────────────────────────────

CHUNK_SIZE = 2048  # bytes per send — matches contract 4.5 chunk size guidance

WAV_PATH = "loopback.wav"  # written relative to working directory (backend/)


async def run_loopback(ws: WebSocket):
    """Handle one /ws/loopback connection.

    Protocol loop:
      1. Accept connection.
      2. Collect binary frames into audio_buf until {"type":"commit"} arrives.
         Ignore {"type":"start"} (just means browser is ready).
         Honour {"type":"end"} to close cleanly.
      3. Write loopback.wav (for manual listening test on laptop).
      4. Send tts_start → PCM16 tone in chunks → tts_end.
      5. Go back to step 2 (allow another record → playback round trip).
    """
    await ws.accept()
    print("[loopback] client connected")

    try:
        while True:
            audio_buf = bytearray()

            # ── PHASE 1: collect audio frames ─────────────────────────────────
            while True:
                raw = await ws.receive()

                if "bytes" in raw and raw["bytes"] is not None:
                    # Binary frame = PCM16 audio from the browser recorder
                    audio_buf.extend(raw["bytes"])

                elif "text" in raw and raw["text"] is not None:
                    msg = json.loads(raw["text"])
                    msg_type = msg.get("type", "")

                    if msg_type == "start":
                        # Browser signals it's starting a new recording session.
                        # Reset buffer in case this is the second round.
                        audio_buf = bytearray()
                        print(f"[loopback] start received, sample_rate={msg.get('sample_rate')}")

                    elif msg_type == "commit":
                        # Button released — done recording.
                        print(f"[loopback] commit — received {len(audio_buf)} bytes of audio")
                        break

                    elif msg_type == "end":
                        # Browser closing the session.
                        print("[loopback] end received — closing")
                        await ws.close()
                        return

                    elif msg_type == "barge_in":
                        # Barge-in during recording phase: ignore here.
                        # In real gateway (P10) this cancels TTS.
                        pass

            # ── PHASE 2: write WAV to disk ────────────────────────────────────
            if audio_buf:
                num_samples = len(audio_buf) // 2  # 2 bytes per Int16 sample
                wav_header = _make_wav_header(num_samples, sample_rate=16000)
                # asyncio.to_thread keeps the event loop unblocked during file I/O.
                # WHY: a large WAV write on slow disk would stall ALL WebSocket
                # connections on this event loop without this.
                await asyncio.to_thread(_write_wav, WAV_PATH, wav_header, bytes(audio_buf))
                print(f"[loopback] wrote {WAV_PATH} ({num_samples} samples)")
            else:
                print("[loopback] no audio received — skipping WAV write")

            # ── PHASE 3: send test tone back ──────────────────────────────────
            tone_bytes = _make_tone(duration_s=2.0, sample_rate=24000, freq=440.0)

            await ws.send_text(json.dumps({
                "type": "tts_start",
                "sample_rate": 24000,
                "text": "loopback test",
            }))

            # Send tone in chunks so the browser player can start immediately
            # (same pattern as real TTS streaming in P10)
            for offset in range(0, len(tone_bytes), CHUNK_SIZE):
                chunk = tone_bytes[offset: offset + CHUNK_SIZE]
                await ws.send_bytes(chunk)
                # Small yield so other coroutines get a turn between chunks
                await asyncio.sleep(0)

            await ws.send_text(json.dumps({"type": "tts_end"}))
            print("[loopback] tone sent — waiting for next round")

            # Loop back to phase 1: wait for next record → commit cycle.

    except WebSocketDisconnect:
        print("[loopback] client disconnected")
    except Exception as exc:
        print(f"[loopback] error: {exc}")
        try:
            await ws.close()
        except Exception:
            pass


def _write_wav(path: str, header: bytes, data: bytes) -> None:
    """Write WAV header + raw PCM data to a file. Runs in a thread (see above)."""
    with open(path, "wb") as f:
        f.write(header)
        f.write(data)
