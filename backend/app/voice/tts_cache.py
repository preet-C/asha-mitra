"""Cache fixed speech lines so the first response does not wait for synthesis."""

import logging
import pathlib

from app.config import get_settings

log = logging.getLogger(__name__)
_CACHE_DIR = pathlib.Path(__file__).resolve().parents[3] / "backend" / ".cache" / "tts"
_STATIC_KEYS = ["disclosure", "cannot_advise", "not_understood", "ack", "goodbye"]


def _pcm_path(key: str, lang: str) -> pathlib.Path:
    """Return the filesystem path for a cached PCM file."""
    return _CACHE_DIR / lang / f"{key}.pcm"


def get_cached(key: str, lang: str) -> bytes | None:
    """Return raw PCM16 bytes for a cached TTS line, or None if not cached yet.

    WHY return None instead of raising: gateway falls back to live TTS on
    cache miss. A missing cache file is not a fatal error — it means
    build_cache() hasn't run yet with a valid GNANI_API_KEY.
    """
    path = _pcm_path(key, lang)
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()

    # Cache miss — log a warning but don't crash
    log.warning("TTS cache miss: key=%r lang=%r — will use live TTS", key, lang)
    return None


async def build_cache(
    langs: list[str] | None = None,
    api_key: str | None = None,
    voice: str | None = None,
) -> None:
    """Synthesise all static Tier A lines and save to .cache/tts/<lang>/<key>.pcm.

    WHY save as .pcm: raw PCM16 bytes at 24000 Hz. No header needed — gateway
    sends these bytes directly in the binary WebSocket stream after tts_start.

    Skips any file that already exists and is non-zero (saves Gnani credits
    on every server restart).

    Call this once after getting GNANI_API_KEY:
        python -m scripts.build_tts_cache

    Args:
        langs:   list of BCP-47 language codes to cache. Default: Tier 1 (hi, kn, en).
        api_key: Gnani API key. Defaults to GNANI_API_KEY env var.
        voice:   Gnani voice name. Defaults to TTS_VOICE env var.
    """
    if langs is None:
        langs = ["hi-IN", "kn-IN", "en-IN"]

    settings = get_settings()
    if api_key is None:
        api_key = settings.GNANI_API_KEY.strip()
    if voice is None:
        voice = settings.TTS_VOICE.strip()

    if not api_key:
        log.error("TTS cache build failed: GNANI_API_KEY not set")
        return
    if not voice:
        log.error("TTS cache build failed: TTS_VOICE not set")
        return

    # Import here (not at module top) so the module can be imported even
    # before the voice package is fully set up.
    from app.voice.gnani_tts import GnaniTTS
    from app.brain.speak import speak
    from app.brain.dialogue import new_session

    # Load danger sign IDs for refer_phc_<id> cache entries
    danger_sign_ids = _load_danger_sign_ids()

    tts = GnaniTTS(api_key=api_key, voice=voice)

    for lang in langs:
        lang_dir = _CACHE_DIR / lang
        lang_dir.mkdir(parents=True, exist_ok=True)

        # Build a minimal session so speak() can resolve vars
        session = new_session(lang)

        # ── Static keys ──────────────────────────────────────────────────────
        for key in _STATIC_KEYS:
            out_path = _pcm_path(key, lang)
            if out_path.exists() and out_path.stat().st_size > 0:
                log.info("TTS cache: skip %s/%s (already cached)", lang, key)
                continue

            # Get the spoken text from speak() so it goes through the locked
            # template path (Tier A rules enforced there, not here).
            text = _get_text_for_key(key, lang, session)
            if not text:
                log.warning("TTS cache: no text for key=%r lang=%r — skipping", key, lang)
                continue

            log.info("TTS cache: synthesising %s/%s ...", lang, key)
            pcm = await _synthesise_once(tts, text, lang)
            if pcm:
                out_path.write_bytes(pcm)
                log.info("TTS cache: saved %s (%d bytes)", out_path.name, len(pcm))
            else:
                log.warning("TTS cache: got no audio for %s/%s", lang, key)

        # ── refer_phc per danger sign ─────────────────────────────────────────
        # WHY one file per sign: danger alert plays the specific sign labels.
        # Caching per-sign avoids live TTS during a danger emergency.
        for sign_id in danger_sign_ids:
            cache_key = f"refer_phc_{sign_id}"
            out_path = _pcm_path(cache_key, lang)
            if out_path.exists() and out_path.stat().st_size > 0:
                log.info("TTS cache: skip %s/%s (already cached)", lang, cache_key)
                continue

            action = {"type": "say", "key": "refer_phc", "vars": {"signs": [sign_id]}}
            text = speak(action, session)
            if not text:
                continue

            log.info("TTS cache: synthesising %s/%s ...", lang, cache_key)
            pcm = await _synthesise_once(tts, text, lang)
            if pcm:
                out_path.write_bytes(pcm)
                log.info("TTS cache: saved %s (%d bytes)", out_path.name, len(pcm))

    await tts.close()
    log.info("TTS cache build complete.")


async def _synthesise_once(tts, text: str, lang: str) -> bytes | None:
    """Synthesise one text string and return raw PCM16 bytes.

    Returns None on any error so callers can skip/log and continue.
    """
    all_pcm = bytearray()
    try:
        async for chunk in tts.synthesize(text, lang, speed=1.0):
            all_pcm.extend(chunk)
    except Exception as exc:
        log.warning("TTS cache: synthesis error: %s", exc)
        return None
    return bytes(all_pcm) if all_pcm else None


def _get_text_for_key(key: str, lang: str, session: dict) -> str:
    """Get the spoken text through the session's normal template path."""
    from app.brain.speak import speak
    action = {"type": "say", "key": key, "vars": {}}
    return speak(action, session)


def _load_danger_sign_ids() -> list[str]:
    """Load danger sign IDs from danger_signs.yaml.

    WHY from YAML: the closed list lives there (AGENTS.md rule 3).
    We only need the IDs to know which refer_phc_<id>.pcm files to build.
    """
    yaml_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "app" / "data" / "danger_signs.yaml"
    )
    try:
        import yaml
        with open(yaml_path, encoding="utf-8") as f:
            signs = yaml.safe_load(f)
        return [s["id"] for s in signs if s.get("id")]
    except Exception as exc:
        log.warning("TTS cache: could not load danger_signs.yaml: %s", exc)
        return []
