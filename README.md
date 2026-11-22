# ASHA Mitra

> Gnani Voice Hackathon · PS1 Healthcare  
> Voice field register for ASHA health workers.

## What it does

An ASHA worker speaks home-visit notes aloud (Hindi / Kannada / English).  
The agent structures the data, reads it back, asks the worker to correct mistakes by voice, flags danger signs, and saves the visit record.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, PostgreSQL (Neon/Supabase) |
| Speech | Gnani Prisma v3 (STT) + Timbre v3 (TTS) over WebSocket |
| LLM | Swappable — bake-off at event H1–5 (D9) |
| Frontend | React + Vite (JavaScript) |

## Quick start

The app has two modes. **Demo preview** uses scripted, synthetic records and
does not open the microphone or call a speech provider. **Live voice** uses the
Gnani STT/TTS credentials stored only in `backend/.env`.

### 1. Start the backend (Windows PowerShell)

```bash
Set-Location backend
if (-not (Test-Path .venv)) { py -3.11 -m venv .venv }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Open `backend/.env` in a text editor and set `GNANI_API_KEY` and `TTS_VOICE`
for live speech. Set `LLM_API_KEY` and choose `LLM_PROVIDER` / `LLM_MODEL` for
structured multilingual extraction; without an LLM key the backend falls back
to a limited parser. Keep all keys in this file; never paste them into the
browser or commit the file. Leave `DATABASE_URL` empty for the in-memory
synthetic demo. If using PostgreSQL, also set `TRANSCRIPT_KEY` to a valid
Fernet key. To force an isolated in-memory run when an existing `.env` has a
database URL, set `$env:DATABASE_URL = "memory"` in the backend terminal before
starting Uvicorn.

Start the backend:

```powershell
\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Health check: `http://127.0.0.1:8000/api/health` should return `{"ok":true}`.

### 2. Start the frontend

In a second terminal, from the project root:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`). Select
**Demo preview** to walk through the scripted experience without a microphone.
For a real visit, choose **Live voice**, select a language, allow microphone
access, and hold the talk button while speaking.

Use the included synthetic beneficiary ID `1001` for a live walkthrough. If
the backend reports `HTTP 401` or `403`, the key reached Gnani but the account
may not have the requested STT or TTS access. A rejected voice name is shown as
a TTS error. If LLM credentials are missing, voice can connect but extraction
uses a limited fallback parser.

If the backend uses another port, set `ASHA_BACKEND_URL` before starting Vite.
For example, if the backend is on port 8001:

```powershell
$env:ASHA_BACKEND_URL = "http://127.0.0.1:8001"
npm run dev -- --port 5174
```

### Tests

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend checks:

```powershell
Set-Location frontend
npm run lint
npm run build
```

## Repo layout

`backend/app` contains the FastAPI routes, visit dialogue, repositories, speech
clients, and locked speech templates. `frontend/src` contains the worker UI,
audio capture/playback, and scripted demo preview.

## Docs

- [`docs/guideline_sources.md`](docs/guideline_sources.md) — danger sign sources (for judges)
- [`docs/DEPLOY_FREE.md`](docs/DEPLOY_FREE.md) — free Render + Cloudflare Pages demo deployment

## Safety

- No diagnosis, treatment, or dosage advice. Ever.
- Safety speech uses fixed templates. Generative speech is disabled by default.
- Raw audio is not saved. PostgreSQL transcripts are encrypted with Fernet.
- The included beneficiary records and preview visits are synthetic.
