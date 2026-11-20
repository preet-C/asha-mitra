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

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # then fill in keys
uvicorn app.main:app --reload --port 8000
```

Health check: `http://localhost:8000/api/health` → `{"ok":true}`

### Frontend

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

### Tests

```bash
cd backend
pytest -q
```

## Repo layout

See `docs/PLAN.md` section 3 for the full layout.

## Docs

- [`docs/PLAN.md`](docs/PLAN.md) — full build plan
- [`docs/guideline_sources.md`](docs/guideline_sources.md) — danger sign sources (for judges)
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — late-binding decisions log
- [`AGENTS.md`](AGENTS.md) — AI primer (paste at start of every AI session)

## Safety

- No diagnosis, treatment, or dosage advice. Ever.
- All safety lines are code-locked templates — never LLM-generated.
- No raw audio saved. Transcripts encrypted (Fernet) + purge script.
- Synthetic data only in this repo.
