# backend/scripts/smoke_tts.py
# P10 — Smoke test for Gnani Timbre v3.0 TTS.
#
# WHY this script exists: Run after smoke_stt.py confirms the key works.
# Use this to:
#   1. Pick TTS_VOICE: run with 3 different voice names, listen to output WAV.
#   2. Run the D6 listening test: same read-back sentence 3 ways per language
#      (native words, English words, raw digits) → set style: in number_words.yaml.
#   3. Verify the audio config (sample_rate, container=raw) decodes correctly.
#
# Usage:
#   cd backend
#   python -m scripts.smoke_tts "नमस्ते, मैं एआई सहायक हूँ" hi-IN out_hi.wav
#   python -m scripts.smoke_tts "Hello I am an AI assistant" en-IN out_en.wav
#   python -m scripts.smoke_tts "ನಮಸ್ಕಾರ, ನಾನು ಎಐ ಸಹಾಯಕಿ" kn-IN out_kn.wav
#
# Then listen: start out_hi.wav (or use VS Code audio player extension).
#
# Requires in .env:
#   GNANI_API_KEY=<your_key>
#   TTS_VOICE=<voice_name>   e.g. Shivani  (pick from Gnani voice catalog)
#
# Output:
#   Connecting to Gnani TTS...
#   Synthesis complete.
#   Bytes received: 48320
#   Duration estimate: 1.01s
#   Saved to: out_hi.wav

import asyncio
import os
import sys
import pathlib
import wave
import struct

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Load backend/.env into os.environ so GNANI_API_KEY and TTS_VOICE are visible.
# WHY dotenv here: pydantic-settings populates its own model, not os.environ.
# Smoke scripts read os.environ directly, so we need dotenv to bridge the gap.
from dotenv import load_dotenv
load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

from app.voice.gnani_tts import GnaniTTS

# TTS audio config — must match what GnaniTTS requests from Gnani
_SAMPLE_RATE = 24000   # Hz — Timbre v3.0 outputs 24000 Hz (from PLAN.md)
_SAMPLE_WIDTH = 2      # bytes = PCM16
_N_CHANNELS = 1        # mono


async def run_smoke(text: str, lang: str, out_path: str) -> None:
    api_key = os.environ.get("GNANI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: No GNANI_API_KEY in env.")
        print("       Set it in backend/.env or export GNANI_API_KEY=<key>")
        sys.exit(1)

    voice = os.environ.get("TTS_VOICE", "").strip()
    if not voice:
        print("ERROR: No TTS_VOICE in env.")
        print("       Set TTS_VOICE=<voice_name> in backend/.env")
        print("       Voice catalog: https://docs.gnani.ai/api/TTS/available-voices")
        sys.exit(1)

    print(f"Text:    {text!r}")
    print(f"Lang:    {lang}")
    print(f"Voice:   {voice}")
    print(f"Output:  {out_path}")
    print()

    tts = GnaniTTS(api_key=api_key, voice=voice)

    print("Connecting to Gnani TTS...")
    all_pcm = bytearray()

    try:
        async for pcm_chunk in tts.synthesize(text, lang, speed=1.0):
            all_pcm.extend(pcm_chunk)
    except Exception as exc:
        print(f"ERROR: TTS synthesis failed: {exc}")
        await tts.close()
        sys.exit(1)

    await tts.close()

    if not all_pcm:
        print("ERROR: No audio bytes received from Gnani TTS.")
        print("       Check TTS_VOICE name, GNANI_API_KEY, and network.")
        sys.exit(1)

    # Wrap raw PCM16 in a WAV container so any player can open it.
    # WHY WAV wrapper: the .pcm bytes from Gnani are raw (no header).
    # Wrapping makes it easy to play and inspect with any audio tool.
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(_N_CHANNELS)
        wf.setsampwidth(_SAMPLE_WIDTH)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(bytes(all_pcm))

    duration_s = len(all_pcm) / (_SAMPLE_RATE * _SAMPLE_WIDTH * _N_CHANNELS)

    print("Synthesis complete.")
    print(f"Bytes received:    {len(all_pcm)}")
    print(f"Duration estimate: {duration_s:.2f}s")
    print(f"Saved to:          {out_path}")
    print()
    print("── D6 Listening test hint ───────────────────────────────────")
    print("  Run 3 versions of the same read-back sentence:")
    print("  1. Native number words  (do kilo aath sau gram)")
    print("  2. English number words (two kilo eight hundred gram)")
    print("  3. Raw digits           (2 kilo 800 gram)")
    print("  Pick the clearest one → set style: in number_words.yaml")
    print("────────────────────────────────────────────────────────────")


def main():
    if len(sys.argv) < 4:
        print("Usage: python -m scripts.smoke_tts \"<text>\" <lang> <out.wav>")
        print()
        print("Examples:")
        print('  python -m scripts.smoke_tts "नमस्ते" hi-IN out_hi.wav')
        print('  python -m scripts.smoke_tts "Hello" en-IN out_en.wav')
        print('  python -m scripts.smoke_tts "ನಮಸ್ಕಾರ" kn-IN out_kn.wav')
        sys.exit(1)

    text = sys.argv[1]
    lang = sys.argv[2]
    out_path = sys.argv[3]

    asyncio.run(run_smoke(text, lang, out_path))


if __name__ == "__main__":
    main()
