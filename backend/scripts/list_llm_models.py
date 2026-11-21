# backend/scripts/list_llm_models.py
# Quick diagnostic: lists models available to your current LLM_PROVIDER + LLM_API_KEY.
# Run: python -m scripts.list_llm_models
# WHY: Different Groq account tiers have different model access.

import httpx
import sys
import os

# Load .env manually (pydantic-settings not needed for this quick script)
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
env = {}
with open(env_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

provider = env.get("LLM_PROVIDER", "groq").lower()
api_key  = env.get("LLM_API_KEY", "")

if not api_key or "PASTE" in api_key:
    print("ERROR: LLM_API_KEY is not set in backend/.env")
    sys.exit(1)

if provider == "groq":
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = httpx.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        print(f"ERROR {resp.status_code}: {resp.text[:300]}")
        sys.exit(1)
    models = sorted(m["id"] for m in resp.json().get("data", []))
    print(f"\nAvailable Groq models ({len(models)} total):\n")
    for m in models:
        print(f"  {m}")

elif provider == "gemini":
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    resp = httpx.get(url, params={"key": api_key}, timeout=10)
    if resp.status_code != 200:
        print(f"ERROR {resp.status_code}: {resp.text[:300]}")
        sys.exit(1)
    models = sorted(
        m["name"].replace("models/", "")
        for m in resp.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    )
    print(f"\nAvailable Gemini models ({len(models)} total):\n")
    for m in models:
        print(f"  {m}")

else:
    print(f"Provider '{provider}' not supported by this script. Check provider manually.")
