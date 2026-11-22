# backend/app/brain/llm.py
# P4 — LLM JSON caller
#
# WHY this file exists: Every brain function that needs language understanding calls
# llm_json(). Keeping all provider code here means we can swap the LLM without
# touching extract.py or any other caller.
#
# Contract: llm_json(system, user) -> dict
#   system = task instructions (the prompt)
#   user   = the data to process (the transcript)
#   Returns a parsed Python dict. Raises ValueError if it cannot.

import json
import logging

import httpx

log = logging.getLogger(__name__)

def llm_json(system: str, user: str) -> dict:
    """
    Call the configured LLM provider and return the response as a parsed dict.

    Provider is set by LLM_PROVIDER in backend/.env.
    Supported: 'gemini', 'anthropic', 'huggingface'

    WHY raise ValueError: Callers (extract.py) catch this and fall back to
    regex helpers. We never want an uncaught exception reaching the voice loop.
    """
    # Lazy import so tests can patch get_settings() before this runs
    from app.config import get_settings
    s = get_settings()

    provider = (s.LLM_PROVIDER or "gemini").lower().strip()

    # Never log transcript text; even synthetic demos can contain sensitive notes.
    log.debug("llm_json provider=%s model=%s", provider, s.LLM_MODEL)

    if provider == "gemini":
        return _call_gemini(system, user, s)
    elif provider == "anthropic":
        return _call_anthropic(system, user, s)
    elif provider == "huggingface":
        return _call_huggingface(system, user, s)
    elif provider == "groq":
        return _call_groq(system, user, s)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. "
            "Set to 'gemini', 'anthropic', 'huggingface', or 'groq' in backend/.env"
        )


# ─── Gemini (Google AI Studio REST API) ───────────────────────────────────────

def _call_gemini(system: str, user: str, s) -> dict:
    """
    Call Gemini via the generateContent REST endpoint.

    WHY REST not SDK: httpx is already in requirements. No new library needed.
    WHY response_mime_type=application/json: Forces structured JSON output from
    Gemini so we don't have to strip markdown fences as often.
    """
    model = s.LLM_MODEL or "gemini-3.8-flash"
    api_key = s.LLM_API_KEY
    if not api_key:
        raise ValueError("LLM_API_KEY is empty. Add your Gemini key to backend/.env")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    payload = {
        # system_instruction is the separate system prompt slot in Gemini's API
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": 0,                        # deterministic output
            "response_mime_type": "application/json",  # ask for raw JSON
        },
    }

    return _post_with_retry(
        url, payload,
        params={"key": api_key},
        extractor=_extract_gemini_text,
    )


def _extract_gemini_text(resp_json: dict) -> str:
    """Pull the text string out of Gemini's response envelope."""
    return resp_json["candidates"][0]["content"]["parts"][0]["text"]


# ─── Anthropic (Claude) ───────────────────────────────────────────────────────

def _call_anthropic(system: str, user: str, s) -> dict:
    """
    Call Anthropic Claude via the /v1/messages endpoint.
    WHY: claude-haiku-class is fast and cheap — good backup if Gemini is down.
    """
    model = s.LLM_MODEL or "claude-haiku-20240307"
    api_key = s.LLM_API_KEY
    if not api_key:
        raise ValueError("LLM_API_KEY is empty. Add your Anthropic key to backend/.env")

    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    return _post_with_retry(url, payload, headers=headers, extractor=_extract_anthropic_text)


def _extract_anthropic_text(resp_json: dict) -> str:
    return resp_json["content"][0]["text"]


# ─── Groq (OpenAI-compatible, very fast free tier) ────────────────────────────

def _call_groq(system: str, user: str, s) -> dict:
    """
    Call Groq via its OpenAI-compatible endpoint.
    WHY Groq: Custom inference chips → p50 often 300–600 ms, far faster than
    hosted Gemini. Free tier: no credit card, ~14k req/day, 30 RPM.
    Get a key at console.groq.com → API Keys.

    Good models for JSON extraction from Indian-language text:
      llama-3.3-70b-versatile   (best quality, free tier)
      llama-3.1-8b-instant      (fastest, lower quality)
    """
    model = s.LLM_MODEL or "llama-3.3-70b-versatile"
    api_key = s.LLM_API_KEY
    if not api_key:
        raise ValueError("LLM_API_KEY is empty. Add your Groq key (gsk_...) to backend/.env")

    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 1024,
        "temperature": 0,
        "response_format": {"type": "json_object"},  # Groq supports JSON mode
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return _post_with_retry(url, payload, headers=headers, extractor=_extract_openai_text)


# ─── Hugging Face (OpenAI-compatible endpoint) ────────────────────────────────

def _call_huggingface(system: str, user: str, s) -> dict:
    """
    Call Hugging Face Inference Providers via the OpenAI-compatible chat endpoint.
    WHY: Some open models are free-tier — hackathon backup option.
    Set LLM_MODEL to e.g. 'mistralai/Mistral-7B-Instruct-v0.3'
    """
    model = s.LLM_MODEL or "mistralai/Mistral-7B-Instruct-v0.3"
    api_key = s.LLM_API_KEY
    if not api_key:
        raise ValueError("LLM_API_KEY is empty. Add your HuggingFace token to backend/.env")

    url = "https://api-inference.huggingface.co/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 1024,
        "temperature": 0,
        # json_object mode only works on some HF models — extractor strips fences anyway
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return _post_with_retry(url, payload, headers=headers, extractor=_extract_openai_text)


def _extract_openai_text(resp_json: dict) -> str:
    return resp_json["choices"][0]["message"]["content"]


# ─── Shared retry logic ───────────────────────────────────────────────────────

def _post_with_retry(
    url: str,
    payload: dict,
    extractor,
    params: dict = None,
    headers: dict = None,
) -> dict:
    """
    POST to `url`, extract the text string with `extractor`, parse as JSON.
    Retries once on network timeout or JSON parse error.

    WHY one retry: Hackathon WiFi is flaky. One retry doubles our chance of
    success without meaningfully increasing latency for the common case.
    WHY 8s timeout: Gnani TTS can't wait longer before the user hears dead air.
    """
    last_error = None

    for attempt in range(2):
        try:
            resp = httpx.post(
                url,
                params=params,
                headers=headers,
                json=payload,
                timeout=8.0,
            )
            resp.raise_for_status()
            raw_text = extractor(resp.json())
            return _strip_and_parse(raw_text)

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            last_error = e
            if attempt == 0:
                log.warning("LLM attempt 1 JSON parse failed (%s), retrying", e)
            else:
                raise ValueError(
                    f"LLM returned unparseable JSON after 2 attempts: {last_error}"
                ) from e

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            # 503 / 429 are transient overload — retry once.
            # 4xx (except 429) won't fix themselves — fail fast.
            if status in (429, 503) and attempt == 0:
                log.warning("LLM attempt 1 HTTP %s (transient), retrying", status)
                last_error = e
                continue
            raise ValueError(
                f"LLM provider returned HTTP {status}. Check provider, model, and API-key access."
            ) from e

        except httpx.TimeoutException as e:
            last_error = e
            if attempt == 0:
                log.warning("LLM attempt 1 timed out (8s), retrying")
            else:
                raise ValueError("LLM timed out after 2 attempts (8s each)") from e

        except httpx.RequestError as e:
            last_error = e
            if attempt == 0:
                log.warning("LLM attempt 1 request failed (%s), retrying", type(e).__name__)
            else:
                raise ValueError(
                    f"LLM request failed after 2 attempts ({type(e).__name__})."
                ) from e

    # Should not reach here, but just in case
    raise ValueError(f"LLM failed after 2 attempts: {last_error}")


def _strip_and_parse(text: str) -> dict:
    """
    Parse text as JSON. Strip markdown fences if present.

    WHY: Some models return ```json ... ``` even when asked for raw JSON.
    We strip the fences before parsing so we don't fail on format alone.
    """
    text = text.strip()

    # Handle ```json ... ``` or ``` ... ``` wrappers
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the opening fence line
        lines = lines[1:]
        # Drop the closing fence line if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)
