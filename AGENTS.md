PROJECT: ASHA Mitra. Hackathon voice agent (Gnani Voice Hackathon, PS1).
ASHA health worker speaks home-visit notes. Languages: Hindi / Kannada / English, code-mixed.
Agent: speech -> structured record -> read back aloud -> worker corrects by voice -> flag danger signs -> save -> follow-up list.
STACK: Python 3.11+, FastAPI, SQLAlchemy 2, PostgreSQL. React + Vite (JavaScript, no TypeScript).
Speech: Gnani Prisma v3.0 (STT) + Timbre v3.0 (TTS) over WebSocket, called from backend only. LLM = swappable function llm_json().
USER LEVEL: beginners. Simple code. Small functions. Comment WHY. No clever abstractions. No new library without telling me first.
HARD RULES:
1. No diagnosis, treatment, dosage advice. Ever.
2. Speech has two kinds. LOCKED = safety lines + every number/name/date/vaccine/sign label: from code + templates only (backend/app/data/templates.yaml). WORDING around locked facts may be written by LLM ONLY through backend/app/brain/speech_guard.py (hard validator) with template fallback. LLM output never reaches user unvalidated. Medical-advice requests NEVER reach LLM speech. Kill switch: GENERATIVE_SPEECH=off (default).
3. Danger signs: closed list backend/app/data/danger_signs.yaml + Python rules. Never invent signs.
4. Three states: present / absent / not_mentioned. Never treat not_mentioned as absent.
5. Conflicting values: never pick silently. Ask worker.
6. Secrets only in backend/.env. Never in frontend. Never commit .env. Never print keys.
7. Synthetic data only. Never save raw audio.
8. Edit ONLY files named in my part. Need change elsewhere? Tell me. Do not do it.
9. Write tests for logic. Run them. Show me output.
10. Gnani code: read official docs first. Do not guess fields:
    https://docs.gnani.ai/api/STT/stt-websocket.md
    https://docs.gnani.ai/api/TTS/tts-websocket.md
    https://docs.gnani.ai/api/TTS/tts-input-formating.md
11. All agent speech goes through speak() in backend/app/brain/speak.py (contract 4.7). Never send raw LLM text to TTS.
FOLDERS + DATA CONTRACTS + SPEECH DESIGN: read docs/PLAN.md sections 3, 4 and 12.
