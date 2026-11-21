# backend/scripts/build_tts_cache.py
# P10 — Convenience script to pre-render TTS cache for all Tier A lines.
#
# WHY: Run this once after getting GNANI_API_KEY and picking TTS_VOICE.
# It synthesises disclosure, cannot_advise, not_understood, ack, goodbye,
# and refer_phc for every danger sign in all three languages.
# After this, gateway.py plays those lines from disk with zero TTS latency.
#
# Usage:
#   cd backend
#   python -m scripts.build_tts_cache
#
# Requires in .env:
#   GNANI_API_KEY=<your_key>
#   TTS_VOICE=<voice_name>
#
# Cache is saved to: backend/.cache/tts/<lang>/<key>.pcm
# Skips files that already exist (safe to re-run after adding a new sign).

import asyncio
import pathlib
import sys

# Allow running as: python -m scripts.build_tts_cache (from backend/ folder)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Load .env so GNANI_API_KEY and TTS_VOICE are available
from app.config import get_settings
_ = get_settings()  # triggers .env load via pydantic-settings

from app.voice.tts_cache import build_cache


async def main():
    print("Building TTS cache for hi-IN, kn-IN, en-IN...")
    print("Skipping files that already exist.\n")
    await build_cache(langs=["hi-IN", "kn-IN", "en-IN"])
    print("\nDone. Cache is at backend/.cache/tts/")


if __name__ == "__main__":
    asyncio.run(main())
