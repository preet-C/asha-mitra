# backend/scripts/smoke_stt.py
# P10 — Smoke test for Gnani Prisma v3.0 STT.
#
# WHY this script exists: Run this FIRST when you get the GNANI_API_KEY.
# It proves the key works, checks all header names, measures round-trip
# latency (commit → transcript), and prints the transcript for review.
# Run BEFORE writing gateway.py so any Gnani API problems surface early.
#
# Usage:
#   cd backend
#   python -m scripts.smoke_stt path/to/sample.wav
#
# The WAV file must be: PCM16, mono, 16000 Hz (or any rate Gnani accepts).
# Record one using: python -m scripts.smoke_tts "text" hi-IN sample.wav
# Or use a real recording. File is local only — never uploaded to git.
#
# Output:
#   Connected to Gnani STT
#   [0.42s] speech_start
#   [1.83s] transcript: "ID 1042, bache ka wazn teen kilo..."
#   [1.83s] detected_language: hi-IN  latency_ms: 412

import asyncio
import os
import sys
import time
import wave
import pathlib

# Allow running as: python -m scripts.smoke_stt  (from backend/ folder)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Load backend/.env into os.environ so GNANI_API_KEY is visible.
# WHY dotenv here: pydantic-settings populates its own model, not os.environ.
from dotenv import load_dotenv
load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

from app.voice.gnani_stt import GnaniSTT

# How many seconds to wait for a transcript after commit before giving up
_TRANSCRIPT_TIMEOUT_S = 5.0


def _load_wav_as_pcm16(wav_path: str) -> tuple[bytes, int]:
    """Read a WAV file and return (raw PCM16 bytes, sample_rate).

    WHY wave module: stdlib, no extra deps. Handles RIFF header parsing.
    Returns the raw audio data without the WAV header so we can stream it.
    """
    with wave.open(wav_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sample_width != 2:
        print(f"WARNING: WAV sample width is {sample_width} bytes, expected 2 (PCM16).")
        print("         Gnani may reject this audio. Convert with ffmpeg:")
        print("         ffmpeg -i input.wav -ar 16000 -ac 1 -f s16le output.wav")

    if n_channels != 1:
        print(f"WARNING: WAV has {n_channels} channels, expected 1 (mono).")
        print("         Only the first channel will be used by Gnani.")

    return raw, sample_rate


async def run_smoke(wav_path: str) -> None:
    api_key = os.environ.get("GNANI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: No GNANI_API_KEY in env.")
        print("       Set it in backend/.env or export GNANI_API_KEY=<your_key>")
        sys.exit(1)

    # Load audio file
    if not pathlib.Path(wav_path).exists():
        print(f"ERROR: File not found: {wav_path}")
        sys.exit(1)

    print(f"Loading: {wav_path}")
    pcm_bytes, sample_rate = _load_wav_as_pcm16(wav_path)
    duration_s = len(pcm_bytes) / (sample_rate * 2)  # 2 bytes per sample, mono
    print(f"Audio:   {len(pcm_bytes)} bytes, {sample_rate} Hz, {duration_s:.1f}s")

    # Connect to Gnani STT
    stt = GnaniSTT(api_key=api_key, lang="hi-IN,en-IN", sample_rate=sample_rate)
    print(f"\nConnecting to Gnani STT...")
    t_start = time.monotonic()

    try:
        await stt.connect()
    except Exception as exc:
        print(f"ERROR: Could not connect to Gnani STT: {exc}")
        print("       Check GNANI_API_KEY and network connectivity.")
        sys.exit(1)

    print(f"Connected. ({(time.monotonic()-t_start)*1000:.0f}ms)")

    # Stream audio at real-time pace (don't burst — Gnani VAD needs timing)
    # WHY real-time: burst sending confuses VAD into thinking speech is instant.
    # We chunk into 20ms windows (640 bytes at 16kHz) and sleep between sends.
    chunk_ms = 20
    chunk_bytes = int(sample_rate * 2 * chunk_ms / 1000)  # bytes per 20ms
    total_sent = 0
    t_audio_start = time.monotonic()

    print(f"Streaming {len(pcm_bytes)} bytes in {chunk_bytes}-byte chunks...")
    pos = 0
    while pos < len(pcm_bytes):
        chunk = pcm_bytes[pos : pos + chunk_bytes]
        await stt.send_audio(chunk)
        pos += chunk_bytes
        total_sent += len(chunk)

        # Sleep to maintain real-time pace
        elapsed = time.monotonic() - t_audio_start
        expected = (pos / (sample_rate * 2))  # seconds of audio sent so far
        sleep_time = expected - elapsed
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)

    print(f"Sent all audio ({total_sent} bytes). Sending commit...")
    t_commit = time.monotonic()
    await stt.flush_and_commit()

    # Collect events until transcript or timeout
    print(f"Waiting for transcript (timeout: {_TRANSCRIPT_TIMEOUT_S}s)...\n")

    transcript_text = None
    try:
        async with asyncio.timeout(_TRANSCRIPT_TIMEOUT_S):
            async for event in stt.listen():
                t_now = time.monotonic() - t_commit
                etype = event.get("type", "unknown")

                if etype == "connected":
                    print(f"[{t_now:+.2f}s] connected: {event}")

                elif etype == "speech_start":
                    print(f"[{t_now:+.2f}s] speech_start (VAD detected speech)")

                elif etype == "processing":
                    print(f"[{t_now:+.2f}s] processing (utterance ended, transcribing...)")

                elif etype == "transcript":
                    transcript_text = event.get("text", "")
                    latency_ms = event.get("latency", "?")
                    detected_lang = event.get("detected_language_code", "?")
                    print(f"[{t_now:+.2f}s] TRANSCRIPT: {transcript_text!r}")
                    print(f"           detected_language: {detected_lang}")
                    print(f"           gnani_latency_ms: {latency_ms}")
                    print(f"           commit→transcript: {t_now*1000:.0f}ms")
                    break  # got what we need

                elif etype == "error":
                    print(f"[{t_now:+.2f}s] ERROR from Gnani: {event}")
                    break

                else:
                    print(f"[{t_now:+.2f}s] event: {etype} → {event}")

    except TimeoutError:
        print(f"\nTIMEOUT: No transcript received after {_TRANSCRIPT_TIMEOUT_S}s after commit.")
        print("         Check: audio file has speech, VAD threshold, language_code header.")

    await stt.close()

    print("\n── Summary ──────────────────────────────────────────────")
    if transcript_text is not None:
        print(f"  OK  transcript received")
        print(f"  Text: {transcript_text!r}")
    else:
        print(f"  FAIL  no transcript received")
    print("─────────────────────────────────────────────────────────")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.smoke_stt <path/to/audio.wav>")
        print("")
        print("Example: python -m scripts.smoke_stt eval/audio/hi_01.wav")
        sys.exit(1)

    wav_path = sys.argv[1]
    asyncio.run(run_smoke(wav_path))


if __name__ == "__main__":
    main()
