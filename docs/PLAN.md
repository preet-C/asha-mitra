# ASHA MITRA — BUILD PLAN

Gnani Voice Hackathon · PS1 Healthcare (Voice field register for ASHA workers)
Event: **Sat 21 Nov 2026**, 24 hours. Plan written **Wed 18 Nov**. Updated **Fri 20 Nov night (v3)**.
Prep: **tonight only, a few hours.** Event is tomorrow. Plan re-timed for that. *(v1/v2: prep days Thu 19 + Fri 20.)*
Save this file in repo as `docs/PLAN.md`.

**VERSION 2 (Wed 18 Nov).** Speech design changed to **Level 1: locked facts, generated words** (D3, D6, D13, D14, section 12, new part P13). Everything else kept. Every change is listed in section 13 (CHANGELOG). Frozen original: `ASHA_MITRA_BUILD_PLAN_v1.md`. **Re-save section 2 primer as `AGENTS.md` (it changed).**

**VERSION 3 (Fri 20 Nov night).** Confirmed **2-person split: you = backend + everything except frontend, teammate = 100% frontend.** Timeline re-cut: prep = tonight only, event tomorrow. Sections 5, 7, 8 updated (+ small timing fixes in D9, P4, P6, P11, risks, open questions). New: handshake contract (8.2), P5a / P5b build order, priority ladder (8.5), checkpoints. Every change is listed in section 14 (CHANGELOG v2 → v3). Frozen previous: `ASHA_MITRA_BUILD_PLAN_v2.md`. **Teammate's chat-history feature is NOT in this plan: under evaluation.**

---

## 0. HOW TO USE THIS FILE

- Human: read sections 1, 5, 6, 7. Pick your parts.
- AI tool (Cursor, Windsurf, Antigravity, Codex, any): open repo folder. Paste **AI PRIMER** (section 2). Then paste ONE part block (section 5). One part = one AI session = one git branch.
- Never paste whole file into AI.
- AI says "done" = not done. Run TEST command yourself. Read `git diff`. Then commit + push (section 6).
- Work solo? Run 2–3 AI tools at once. Each on own part, own branch. You review. Parts touch different folders. No clash.
- Tonight checklist (v3; was "Wed night checklist", 30 min): install tools (P0), make accounts, read this file, ask organisers: (1) deck slide limit is 6 — is our deck OK? (2) can we create Gnani API key before event? (3) judges use own phone via link, or our device? (4) venue wifi OK?

---

## 1. LOCKED DECISIONS

| # | Decision | Why |
|---|---|---|
| D1 | Voice gateway = **own FastAPI WebSocket server. Not LiveKit.** | Our dialogue is scripted, not free LLM chat. Fewer parts (no LiveKit server, worker, tokens). AI tools write FastAPI WebSocket code well. Gnani gives events we need (`speech_start`, `processing`, `commit`). PS allows custom orchestration. **Cost:** deck needs one edit: LiveKit logo/row → "FastAPI + WebSocket". Reject D1? Only part P10 changes. Brain, data, UI stay same. |
| D2 | Mic = **hold-to-talk button**. Press = speak. Release = commit. | Noise-proof. No echo loop. Barge-in = press button. No cut-off when she pauses. Hands-free = stretch only. |
| D3 | **Level 1 speech: locked facts, generated words.** Code speaks all safety lines and every fact (numbers, names, dates, vaccines, sign labels). LLM may write only the *wording* around locked facts, through a hard code validator, with template fallback. Medical-advice requests never reach LLM speech. Details: section 12. *(v1: LLM never speaks; fixed templates only.)* | Natural wording + 10-language reach. Read-back stays exact. Guardrails live in code, not prompt. Kill switch `GENERATIVE_SPEECH=off`. |
| D4 | Danger signs: closed list from public guideline → Python rules. LLM only maps words → sign IDs. Keyword net as backup. Alert fires at once, before read-back. | Missed sign costs double in judging. |
| D5 | Languages: **Tier 1 = Hindi `hi-IN`, Kannada `kn-IN`, English `en-IN`**. Fully tested. Tier 2 = other 7 Gnani languages: stretch only. Tier 2 wording comes from generated lane (D3, only if gate D13 passes). Tier 2 safety lines are machine-translated, flagged `verified: false`, never claimed verified. | Claim only what we test. |
| D6 | Spoken numbers = **native number words** for Hindi + Kannada from small hand-built tables (`number_words.yaml`). English via `num2words`. Weight spoken as **kilo + gram** ("do kilo aath sau gram"), never "point". IDs digit by digit. Style per language (native words / English words / raw digits) fixed by 20-min listening test at event H0–1, behind one function `render_number(lang, kind, value)`. *(v1: English number words inside any language.)* | `num2words` has no Hindi. Kannada output has joining errors (checked). Tables are small, testable, reusable for parsing. Gnani TTS wants numbers as spoken words. |
| D7 | PostgreSQL on free hosted tier (**Neon or Supabase**). Docker optional. 2 tables. | No Docker pain on Windows. Internet needed anyway for Gnani. |
| D8 | Frontend = **React + Vite + plain JavaScript**. One screen. Mobile first. | No TypeScript errors blocking beginners. |
| D9 | LLM chosen by **bake-off at event H1–5, max 45 min, 2 providers enough** *(v2: Fri AM, 90 min)*. Candidates: (a) open model via Hugging Face Inference Providers, (b) Gemini Flash-class, (c) Claude Haiku-class (`claude-haiku-5-5`). Pick best field accuracy, then latency. Within 5 points → pick (a) so deck stays true. (a) not working in 20 min → drop it, edit deck row "Hugging Face" to real provider. | Open choice per PS. Decide by data. |
| D10 | Two-source conversation cross-check: **NOT built**. One roadmap line on last slide. | Needs speaker separation + consent. Judges dictate alone. Cannot demo. Do not claim it. |
| D11 | Replacement innovation: self-correction inside speech, history cross-checks (vaccine due vs given, weight vs last visit, previous flag), `not mentioned` ≠ `no`. | Cheap. Demoable. Honest. |
| D12 | Privacy: no raw audio saved. Transcripts encrypted (Fernet) + purge script. Synthetic data only. Keys backend-only. HTTPS only. | PS baseline. |
| D13 | Generated wording is **gated by data**. Enabled at event only if: guardrail eval 100% pass · added p95 latency ≤ ~1 s · native speaker accepts 10 samples per Tier 1 language · 15 min manual probing by someone who did not write the validator finds no hole. Decided at **H13**, logged in `docs/DECISIONS.md`. Fail → `GENERATIVE_SPEECH=off`, ship templates. Demo still works. | Settle by test, not opinion. Part P13. |
| D14 | **Intent router:** LLM returns a label only, never reply text. Keyword net in code backs it up. Label `medical_advice` OR advice keyword hit = fixed refusal. Never reaches generator. | Two layers on riskiest path. Contract 4.7. |

MUST-HAVE (judged): 5 fields · read-back · voice correction · danger alert · AI disclosure first turn · follow-up list · README + diagram · demo video.
SHOULD: history checks · tri-state · latency badge · barge-in · Kannada · intent router (repeat, slower, skip, language switch).
COULD: Tier 2 languages · hands-free mode · noise-mixed eval audio · generated-wording lane (P13, gated by D13).
WON'T: two-source check · login · offline mode · multi-user.

---

## 2. AI PRIMER (paste at start of EVERY AI session. Also save as `AGENTS.md` in repo root)

```text
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
```

---

## 3. REPO LAYOUT

```text
asha-mitra/
├─ AGENTS.md                      # = AI PRIMER
├─ README.md                      # P12
├─ .gitignore
├─ docs/
│  ├─ PLAN.md                     # this file
│  ├─ guideline_sources.md        # P1: every danger sign -> source + page
│  └─ DECISIONS.md                # one line per decision made later (LLM pick etc.)
├─ backend/
│  ├─ .env.example                # copy to .env (never commit .env)
│  ├─ requirements.txt
│  ├─ pytest.ini
│  ├─ app/
│  │  ├─ main.py                  # FastAPI app, routes, WebSocket
│  │  ├─ config.py                # reads .env
│  │  ├─ brain/                   # all logic. no audio here
│  │  │  ├─ normalize.py          # P2
│  │  │  ├─ danger.py             # P3
│  │  │  ├─ vaccines.py           # P3
│  │  │  ├─ checks.py             # P3
│  │  │  ├─ llm.py                # P4
│  │  │  ├─ extract.py            # P4
│  │  │  ├─ prompts/extract_v1.txt, speech_v1.txt   # speech_v1 = P13
│  │  │  ├─ dialogue.py           # P5
│  │  │  ├─ intents.py            # P5 intent router
│  │  │  ├─ speak.py              # P5 speak(): templates now, generated wording in P13 (4.7)
│  │  │  ├─ speech_guard.py       # P13 hard validator
│  │  │  └─ templates.py          # P5
│  │  ├─ repo/                    # P5 memory repo, P7 postgres repo
│  │  ├─ voice/                   # P9 loopback, P10 gnani
│  │  └─ data/
│  │     ├─ danger_signs.yaml     # P1
│  │     ├─ vaccine_schedule.json # P1
│  │     ├─ number_words.yaml     # P1 hi + kn number tables (v2)
│  │     ├─ templates.yaml        # P1
│  │     └─ synthetic_beneficiaries.json  # P1
│  ├─ scripts/                    # make_synthetic.py, gen_templates.py, smoke_stt.py, smoke_tts.py, purge.py
│  ├─ eval/                       # cases.yaml, guardrail_cases.yaml, run_eval.py, run_guardrails.py, bakeoff.py (audio NOT in git)
│  └─ tests/
└─ frontend/                      # P8, P9
   ├─ vite.config.js
   ├─ public/recorder-worklet.js
   └─ src/ (App.jsx, components/, audio/, hooks/, mock/)
```

---

## 4. CONTRACTS (shared shapes. Everyone codes to these)

### 4.1 VisitDraft (what extraction returns). `null` = not mentioned.

```json
{
  "beneficiary_id": "1042",
  "visit_type": "NEWBORN",
  "weight_kg": 2.8,
  "vaccines_given_today": ["PENTA1"],
  "vaccines_due_stated": ["OPV1"],
  "next_visit": {"kind": "relative_days", "n": 15},
  "symptoms": [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": "tez bukhar"}],
  "asks_advice": false,
  "intent": "notes"
}
```

- `visit_type` one of: `ANC`, `PNC`, `NEWBORN`, `IMMUNISATION`, `OTHER`.
- `next_visit.kind` one of: `relative_days` {n}, `weekday` {weekday, which: "this|next"}, `absolute` {day, month, year|null}.
- `symptoms[].status` one of: `present`, `absent`, `unclear`. `absent` only if worker clearly said it is not there.
- `intent` one of the labels in 4.7. Default `notes` (worker is dictating visit data). Label only. No reply text. *(added v2)*
- LLM returns this. Python validates + converts `next_visit` to ISO date + computes `vaccines_due`. LLM never computes dates or due vaccines.

### 4.2 Final saved record

```json
{
  "beneficiary_id": "1042", "visit_type": "NEWBORN", "visit_date": "2026-11-21",
  "weight_kg": 2.8, "vaccines_given_today": ["PENTA1"], "vaccines_due": ["OPV1","ROTA1"],
  "next_visit_date": "2026-12-06", "danger_flags": ["NB_FEVER_OR_COLD"], "flagged": true
}
```

`vaccines_due` = schedule says due by today AND not given before AND not given today. Computed by Python (P3).

### 4.3 Brain interface (P5). Transport-agnostic.

```python
# backend/app/brain/dialogue.py
def handle(session: dict, event: dict) -> list[dict]:
    """event  : {"type":"start"} | {"type":"user_text","text":"..."}
       returns: list of actions, in order"""

# actions:
{"type": "say",   "key": "readback", "vars": {...}}   # gateway: speak(action, session) -> text -> TTS (4.7)
{"type": "setting", "lang": "kn-IN", "speed": 0.8}    # voice command changed language or speed (either key optional)
{"type": "alert", "signs": ["NB_FEVER_OR_COLD"]}      # gateway: refer_phc template + red banner
{"type": "card",  "draft": {...}, "uncertain": ["weight_kg"]}  # UI updates card
{"type": "saved", "visit_id": "..."}
```

`session` = dict: `lang`, `state`, `draft`, `flags`, `asked`, `beneficiary`. In memory. One per visit.

### 4.4 Repo interface (P5 memory version, P7 postgres version). Switch by env `DATABASE_URL` (empty = memory).

```python
get_beneficiary(id: str) -> dict | None
save_visit(record: dict, transcript: str) -> str     # returns visit_id
followups() -> list[dict]                              # upcoming next visits + flagged visits
```

### 4.5 Browser ⇄ server WebSocket (`/ws/session`)

Browser → server:
- JSON `{"type":"start","lang":"hi-IN","sample_rate":16000}`
- binary: PCM16 mono audio. Any chunk size. Server re-chunks.
- JSON `{"type":"commit"}` (button released)
- JSON `{"type":"barge_in"}` (button pressed while agent speaks)
- JSON `{"type":"end"}`

Server → browser:
- JSON `{"type":"ready"}`
- JSON `{"type":"transcript","text":"..."}`
- JSON `{"type":"card","draft":{...},"uncertain":[...]}`
- JSON `{"type":"alert","signs":[{"id":"...","label":"..."}]}`
- JSON `{"type":"tts_start","sample_rate":24000,"text":"..."}` then binary PCM16 chunks, then `{"type":"tts_end"}`
- JSON `{"type":"latency","what":"first_audio","ms":812}`
- JSON `{"type":"saved","visit_id":"..."}`
- JSON `{"type":"setting","lang":"kn-IN","speed":0.8}` (language or speed changed by voice command; either key optional) *(added v2)*
- JSON `{"type":"error","message":"..."}`

### 4.6 Data files

`danger_signs.yaml` (every row needs `source`):

```yaml
- id: NB_FEVER_OR_COLD
  applies_to: NEWBORN            # NEWBORN | MOTHER
  labels: {en: "Fever or cold to touch", hi: "बुखार या ठंडा शरीर", kn: "ಜ್ವರ ಅಥವಾ ತಣ್ಣಗಿನ ದೇಹ"}   # DRAFT. native speaker checks
  keywords:
    en: ["fever", "hot to touch", "high temperature", "cold to touch"]
    hi: ["bukhar", "बुखार", "tez bukhar", "thanda"]
    kn: ["ಜ್ವರ", "jwara"]
  source: "ASHA Job Aid (Newborn & Young Child) 2018, p.10 — 'Feels hot or cold to touch'"   # fill real page
```

`vaccine_schedule.json`:

```json
{
  "child":  [{"id":"BCG","label":"BCG","due_weeks":0},
             {"id":"PENTA1","label":"Penta 1","due_weeks":6}],
  "mother": [{"id":"TD1","label":"Td 1"},{"id":"TD2","label":"Td 2","min_gap_weeks_after":["TD1",4]}],
  "source": "MoHFW National Immunization Schedule (cite exact doc + year)"
}
```

`templates.yaml` — v2: **safety + fallback lines.** Each key has `tier` (`A` locked, template only | `B` wording may be generated by P13), `verified` (`true` human-checked | `false` machine-translated), and per language (`en-IN`, `hi-IN`, `kn-IN`) one string, or for Tier B a list of 1–3 variant strings. Tier A = exactly one string. Keys:
`disclosure, ask_id, id_not_found, ask_visit_type, ask_weight, ask_vaccine_given, ask_next_visit, ask_missing, confirm_weight_change, confirm_vaccine_mismatch, confirm_sign_absent, ask_prev_flag, readback, readback_changed, refer_phc, cannot_advise, not_understood, saved, goodbye, ack, who_are_you, what_can_you_do, how_to_use, off_topic, switch_language_ok, slower_ok, repeat_nothing`
Tier A keys: `disclosure, refer_phc, cannot_advise, readback, readback_changed, saved`. All other keys Tier B. *(v1: every key hand-written and verified, no tiers.)*

`synthetic_beneficiaries.json`:

```json
[{"id":"1001","name":"Sunita Devi","kind":"child","dob":"2026-10-08","edd":null,"village":"Hosahalli",
  "last_weight_kg":3.1,"vaccines_given":[{"id":"BCG","date":"2026-10-08"}],"last_flags":[]}]
```

### 4.7 Speech interface + intents *(added v2. P5 builds it, P13 extends it)*

```python
# backend/app/brain/speak.py
def speak(action: dict, session: dict) -> str:
    """action  : {"type":"say","key":"ask_missing","vars":{"fields":["weight_kg","next_visit_date"]}}
       returns : final text for TTS. Never raises. Falls back to template."""
```

- Providers: `TemplateSpeech` (default; random variant, never same variant twice in a row) and `GeneratedSpeech` (P13). Env `GENERATIVE_SPEECH=on|off`, default `off`.
- **Tier A keys** (`disclosure, refer_phc, cannot_advise, readback, readback_changed, saved`): template only. Always. Code asserts it.
- **Tier B keys:** wording may come from LLM through `speech_guard.validate()`. Any failure, timeout (700 ms) or exception → template.
- **Locked facts** (numbers, weights, IDs, dates, names, vaccine names, sign labels) are rendered by code (`render_number`, YAML labels) and inserted into placeholders. LLM never types them. LLM never even sees raw values, only placeholder names.

Intent labels (`extract_visit` returns one in `intent`; keyword net in code backs it up):

| Label | Handling |
|---|---|
| `notes` | normal flow |
| `confirm` / `deny_or_correct` | CONFIRM state logic (P5 step 7) |
| `repeat` | replay last agent line |
| `slower` | `setting` action, TTS speed 0.8 |
| `skip_field` / `later` | leave field "not mentioned", move on |
| `start_over` | reset draft |
| `switch_language` | `setting` action (STT + TTS language) |
| `medical_advice` | **Tier A `cannot_advise`. Never generator.** |
| `who_are_you` / `what_can_you_do` / `how_to_use` / `off_topic` | Tier B reply (template until P13 gate passes) |

---

## 5. PARTS

| Part | What | Who | When (v3) | Needs | Hours (with AI) |
|---|---|---|---|---|---|
| P0 | Setup + repo skeleton | **You** (repo, backend). Teammate scaffolds `frontend/` (step 4) | **Tonight**, first | — | 2 |
| P1 | Data files (danger list, vaccines, templates, number tables, synthetic) | **You** (human reading) + AI formatting. Teammate may verify Hindi / Kannada lines (optional) | Tonight: danger list + Tier A lines. Rest event H0–5 | P0 | 4–5 |
| P2 | Normalisers (numbers, ID, weight, dates, number words hi/kn/en) | **You** + AI session 1 | Tonight (AI runs). Review event H0–1 | P0 | 3–4 |
| P3 | Rules (danger, vaccines due, history checks) | **You** + AI session 2 | Tonight (AI runs). Review event H0–1 | P0, schema in 4.6 | 3 |
| P4 | LLM extraction + bake-off | **You** + AI | Event H1–5 (45 min bake-off) | P2, P6 cases, LLM keys | 3 |
| P5a | Dialogue **thin slice** (stub brain, read-back + correction + danger alert + save) | **You** + AI (strongest) | Event H1–4 | P2, P3, P4 basic | 2 |
| P5b | Dialogue full flow + intents + `speak()` + text CLI | **You** + AI (strongest) | Event H8–12 | P5a, slice works on phone | 4 |
| P6 | Eval cases + guardrail cases + score scripts | **You** + AI script | Tonight: 15 cases if time. Guardrail cases event H8–12 | P1 IDs | 3–4 |
| P7 | DB + API + privacy | **You** + AI session 3 | Tonight (AI runs), else event H8–10 | P0, Neon URL | 3 |
| P8 | UI shell with mock mode | **Teammate** | Tonight. Finish H0–5. Real WebSocket from ~H3 | P0 (frontend scaffold) | 3–4 |
| P9 | Audio plumbing spike (no Gnani) | **Teammate:** recorder, worklet, player, `Spike.jsx`. **You:** `loopback.py` + route | Tonight stretch, else event H0–3 | P0, real Android phone | 3 |
| P10 | Gnani STT/TTS voice gateway | **You** (backend) + AI strongest. **Teammate:** frontend wiring | Event H1–8 | P5a, P9, Gnani key | 6–8 |
| P11 | Integration + noise tuning + run | **Both** (you lead) | Event H5–15 (starts when slice works) | P7, P8, P9, P10 | 7 |
| P12 | README, diagram, video, submit | **You**. Teammate records screen footage (optional) | Skeleton tonight if time. Finish H15–20 | all | 5 |
| P13 | Speech guard + generated wording lane (**gated at H13**) | **You** + AI strongest | Event H10–13, **only if everything else is green. Likely skip** | P4, P5b, P6 | 4–5 |

**Do not bring** end-to-end working voice (P10 + P11). Organisers: pre-build OK if not fully developed project. Repo history will show honest timeline.

---

### P0 — SETUP + REPO SKELETON
**Who:** You (repo + backend skeleton). Teammate does step 4 (frontend scaffold) right after cloning. **When:** Tonight, first. **Needs:** nothing.
**Goal:** Empty project runs. Teammate can clone and run it.

Install (everyone): Git, Python 3.11+, Node.js LTS, VS Code or AI IDE, Chrome. Check:
```
git --version
python --version
node --version
npm --version
```
(Mac/Linux: use `python3`.)

Accounts: GitHub (all) · Neon or Supabase free Postgres (lead) · LLM keys (P4) · Gnani key (event, or earlier if organisers allow).

Steps:
1. Make GitHub repo + local folder: section 6, step G2.
2. Create files below.
3. Backend venv + run health check.
4. Frontend Vite app + config.
5. Create empty `__init__.py` in `backend/app`, `backend/app/brain`, `backend/app/voice`, `backend/app/repo`.
6. Put AI PRIMER into `AGENTS.md`. Put this file into `docs/PLAN.md`.
7. Commit + push. Teammates clone (G3) and repeat steps 3–4.

`.gitignore`:
```
# secrets
.env
.env.*
!.env.example
# python
.venv/
__pycache__/
*.pyc
.pytest_cache/
# node
node_modules/
dist/
# local audio + cache (never commit audio)
*.wav
*.mp3
*.pcm
!backend/eval/samples/*.wav
backend/.cache/
.DS_Store
```

`backend/.env.example`:
```
APP_ENV=dev
GNANI_API_KEY=
LLM_PROVIDER=
LLM_MODEL=
LLM_API_KEY=
DATABASE_URL=
TRANSCRIPT_KEY=
TTS_VOICE=
```
(Make `TRANSCRIPT_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. `DATABASE_URL` format: `postgresql+psycopg://USER:PASS@HOST/DBNAME`. Empty = in-memory repo.)
Copy to real env file: Mac/Linux `cp backend/.env.example backend/.env` · Windows `copy backend\.env.example backend\.env`.

`backend/requirements.txt`:
```
fastapi
uvicorn[standard]
websockets
pydantic>=2
pydantic-settings
sqlalchemy>=2
psycopg[binary]
python-dotenv
pyyaml
num2words
cryptography
httpx
pytest
```

`backend/pytest.ini`:
```
[pytest]
pythonpath = .
testpaths = tests
```

`backend/app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="ASHA Mitra")

@app.get("/api/health")
def health():
    return {"ok": True}

# WebSocket routes go ABOVE this line (P9, P10).
# Static frontend mount goes at the very END (P11).
```

Backend run (Windows PowerShell):
```
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
PowerShell blocks script? Run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Or use Command Prompt: `.venv\Scripts\activate.bat`.
Backend run (Mac/Linux):
```
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (from repo root). If Vite asks questions: React, JavaScript.
```
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm run dev
```
Replace `frontend/vite.config.js`:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// proxy lets ONE https tunnel serve both page and backend
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: true,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
```

**Done when:** `http://localhost:8000/api/health` shows `{"ok":true}` · `http://localhost:5173` shows Vite page · `cd backend && pytest -q` runs without crash · teammate cloned and ran both.
**Git:** commit straight to `main` (first commit only): `chore: initial scaffold`.

---

### P1 — DATA FILES
**Who:** You (human reading + checks). AI only formats. Teammate can verify Hindi / Kannada Tier A lines if he speaks them (optional). **When:** Tonight: danger list (≤ 12 signs, page refs) + Tier A lines. Rest event H0–5. **Needs:** P0.
**Goal:** All text data the brain needs. No code logic.
**Branch:** `part/p1-data`

Steps:
1. **Danger signs.** Open docs in section 12 (MCP Card, HBNC Guidelines, ASHA Job Aid). Build `danger_signs.yaml`. Max 20 signs. **Each row needs `source` = document + page.** Start from candidates below. Delete any you cannot find in docs. Add any docs list that we miss. Must include PS examples: bleeding in pregnancy, high fever in newborn.
   Also check: does SSBSK 2026 guideline replace HBNC/HBYC? Yes → cite it too.
2. **Vaccines.** Build `vaccine_schedule.json` from MoHFW National Immunization Schedule PDF (section 12). Not from memory. Not from blog. Child schedule by weeks/months + mother Td1/Td2.
3. **Templates (v2: smaller, tiered).** Fill `templates.yaml` with Tier A (safety) + Tier B (fallback) lines from 4.6, three languages. Tier B: 1–3 variants per language. Native Hindi + Kannada speaker checks **every Tier A line** (`disclosure`, `refer_phc`, `cannot_advise`, `readback`, `readback_changed`, `saved`). Tier B lines: spot-check. Set `verified: true` only after human check. Numbers/dates are placeholders `{weight}` `{date}`; brain fills them from number tables (D6). Run `scripts/gen_templates.py` (LLM drafts translations + variants + back-translation to English, writes a review sheet CSV) to cut writing time. Humans still verify. *(v1: all 19 keys hand-written, all lines verified, numbers = English words.)*
4. **Synthetic beneficiaries.** `scripts/make_synthetic.py` writes `synthetic_beneficiaries.json`: IDs `1001`–`1012`. 8 children (ages 0–15 months, DOB computed from today so some vaccines always due), 4 mothers (ANC/PNC). Fictional names. Include 2 with previous danger flag, 2 with last weight.
5. `docs/guideline_sources.md`: table sign ID → document → page. Judges check this.
6. **Number tables (v2).** `backend/app/data/number_words.yaml`: Hindi + Kannada digits 0–9, numbers 0–99, hundreds (for grams), days 1–31, month names, plus `style:` per language (`native` | `english` | `digits`, set after listening test at event H0–1). LLM drafts, native speaker checks. Used by `render_number` (D6) and by P2 parsers.
7. **Tier 2 safety lines (optional, v2).** Machine-translate Tier A lines to other Gnani languages with `gen_templates.py`. Set `verified: false`. Never claim them verified.

Candidate danger signs (**VERIFY each in PDF. Fix IDs now. P6 + P3 use these IDs.**):

| ID | For | Candidate sign | Where to verify |
|---|---|---|---|
| `MO_BLEEDING` | mother | Bleeding in pregnancy; excessive bleeding during/after delivery | MCP Card |
| `MO_FEVER` | mother | High fever in pregnancy or within 1 month of delivery | MCP Card |
| `MO_SEVERE_HEADACHE` | mother | Severe headache | MCP Card |
| `MO_BLURRED_VISION` | mother | Blurring of vision | MCP Card |
| `MO_CONVULSIONS` | mother | Fits / convulsions | MCP Card |
| `MO_SWELLING_BODY` | mother | Swelling all over body | MCP Card |
| `MO_WATER_BREAK_PRETERM` | mother | Water bag burst without labour pains / preterm labour pains (<37 wk) | MCP Card |
| `MO_SEVERE_ANAEMIA` | mother | Severe anaemia with or without breathlessness | MCP Card |
| `NB_NOT_FEEDING` | newborn | Not able to feed | ASHA Job Aid / HBNC |
| `NB_WEAK_LIMP` | newborn | Weak cry or limp | ASHA Job Aid |
| `NB_FAST_BREATHING` | newborn | Breathing fast or difficult | ASHA Job Aid |
| `NB_FEVER_OR_COLD` | newborn | Feels hot or cold to touch | ASHA Job Aid |
| `NB_YELLOW_PALMS_SOLES` | newborn | Yellowness of palms and soles | ASHA Job Aid |
| `NB_CONVULSIONS` | newborn | Convulsions | HBNC Guidelines |
| `NB_CORD_PUS` | newborn | Oozing / pus from umbilicus | ASHA Job Aid (exam list) |

Template drafts (**DRAFT. Native speaker must verify before use.**):
```yaml
disclosure:
  tier: A
  verified: false   # set true after native speaker check
  en-IN: "Hello. I am an AI assistant. I help you record this home visit. I can make mistakes, so please check what I read back."
  hi-IN: "नमस्ते। मैं एक एआई सहायक हूँ। मैं इस होम विज़िट का रिकॉर्ड बनाने में आपकी मदद करती हूँ। मुझसे गलती हो सकती है, इसलिए जो मैं दोहराऊँ उसे ज़रूर जाँचिए।"
  kn-IN: "ನಮಸ್ಕಾರ. ನಾನು ಎಐ ಸಹಾಯಕಿ. ಈ ಮನೆ ಭೇಟಿಯ ದಾಖಲೆ ಮಾಡಲು ನಾನು ನಿಮಗೆ ಸಹಾಯ ಮಾಡುತ್ತೇನೆ. ನನ್ನಿಂದ ತಪ್ಪಾಗಬಹುದು, ಆದ್ದರಿಂದ ನಾನು ಓದಿ ಹೇಳುವುದನ್ನು ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ."
refer_phc:
  tier: A
  verified: false   # set true after native speaker check
  en-IN: "Danger sign: {signs}. Refer to the PHC now."
  hi-IN: "खतरे का संकेत: {signs}। अभी पीएचसी रेफर करें।"
  kn-IN: "ಅಪಾಯದ ಲಕ್ಷಣ: {signs}. ಈಗಲೇ ಪಿಎಚ್‌ಸಿಗೆ ರೆಫರ್ ಮಾಡಿ."
cannot_advise:
  tier: A
  verified: false   # set true after native speaker check
  en-IN: "I cannot give medicine or treatment advice. Please contact your ANM or the PHC doctor."
  hi-IN: "मैं दवा या इलाज की सलाह नहीं दे सकती। कृपया अपनी एएनएम या पीएचसी डॉक्टर से संपर्क करें।"
  kn-IN: "ನಾನು ಔಷಧಿ ಅಥವಾ ಚಿಕಿತ್ಸೆಯ ಸಲಹೆ ನೀಡಲು ಸಾಧ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಎಎನ್‌ಎಂ ಅಥವಾ ಪಿಎಚ್‌ಸಿ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ."
```

**Done when:** YAML/JSON load without error (`python -c "import yaml; yaml.safe_load(open('backend/app/data/danger_signs.yaml', encoding='utf-8'))"`) · every sign has `source` · every template key has 3 languages · `make_synthetic.py` runs · Hindi + Kannada Tier A lines read by native speaker · every Tier A line has `verified: true` (Tier 2: `false`, flagged) · `number_words.yaml` loads and has hi + kn tables.
**Git:** `part/p1-data` → `p1: data files + guideline sources`.

AI PROMPT (formatting help only):
```text
Part P1. Edit only backend/app/data/*, backend/scripts/{make_synthetic,gen_templates}.py, docs/guideline_sources.md.
I give you sign list + sources. Format into danger_signs.yaml per PLAN 4.6. Do not add signs. Do not translate safety lines yourself — leave TODO marker if I did not give text.
Write make_synthetic.py per PLAN section 5 P1 step 4. Run it. Show output.
```

---

### P2 — NORMALISERS
**Who:** You + AI session 1. **When:** Tonight (AI runs; you review at event H0–1). **Needs:** P0 (number tables come from P1: use a small fixture table in tests until P1 lands). **Branch:** `part/p2-normalisers`
**Files:** `backend/app/brain/normalize.py`, `backend/tests/test_normalize.py`
**Goal:** Pure Python helpers. No network. No LLM.

Functions:
- `parse_beneficiary_id(text) -> str | None` — "1042", "1 0 4 2", "one zero four two", "ek zero chaar do" → `"1042"`. Exactly 4 digits else None.
- `validate_weight_kg(value, kind) -> float | None` — child 1–25 kg, mother 30–120 kg, else None. Round 1 decimal.
- `parse_weight_fallback(text) -> float | None` — regex for "2.8", "2.8 kg", "2800 gram", "2 kilo 800 gram". Used only if LLM fails.
- `resolve_next_visit(spec: dict, today: date) -> date | None` — spec from 4.1 (`relative_days`, `weekday`, `absolute`). Absolute without year → next occurrence in future. Date in past → None.
- `number_to_words_en(x: float) -> str` — 2.8 → "two point eight". Uses `num2words`. English only.
- `digits_to_words(s: str, lang: str) -> str` — "1042" → digit by digit in `lang` (hi/kn from tables, en via `num2words`).
- `date_to_words(d: date, lang: str) -> str` — "fifteen December" / Hindi / Kannada day + month from tables.
- `weight_to_words(kg: float, lang: str) -> str` — 2.8 → kilo + gram in `lang` ("two kilo eight hundred gram"). Never "point".
- `render_number(lang: str, kind: str, value) -> str` — single entry point used by `speak()`. `kind` = `weight` | `id` | `date` | `count`. Style per language (`native` | `english` | `digits`) read from `number_words.yaml` `style:` (D6).
- `parse_spoken_number(text: str, lang: str) -> int | None` — uses same tables. Fallback for IDs/weights when STT gives words.
- Hindi + Kannada words come from `data/number_words.yaml` (P1). Do NOT use `num2words` for hi/kn: no Hindi support, Kannada output has joining errors. *(v1: English number words only.)*

**Test:** `cd backend` · venv on · `pytest tests/test_normalize.py -q`
**Done when:** all pass · ≥ 40 test cases (v1: 30) · includes bad input (None, empty, "abc", out-of-range) · table round-trip tests (number → words → parse back) for hi, kn, en.
**Git:** `p2: normalisers + tests`.

AI PROMPT:
```text
Part P2. Edit only backend/app/brain/normalize.py and backend/tests/test_normalize.py.
Implement functions listed in docs/PLAN.md part P2. Pure Python. Only stdlib + num2words (English only) + PyYAML (tables).
Write 40+ pytest cases first, then code. Run pytest. Show output.
```

---

### P3 — RULES (danger, vaccines due, history checks)
**Who:** You + AI session 2. **When:** Tonight (AI runs; you review at event H0–1). **Needs:** P0, schema 4.6 (no need to wait for P1 data: use tiny test YAML in tests). **Branch:** `part/p3-rules`
**Files:** `backend/app/brain/danger.py`, `vaccines.py`, `checks.py`, `backend/tests/test_danger.py`, `test_vaccines.py`, `test_checks.py`

**danger.py**
`scan_danger(transcript, symptoms, beneficiary_kind, lang) -> dict` returns `{"alert": [sign_id...], "confirm_absent": [sign_id...]}`

Rule (recall first):
1. LLM symptom status `present` or `unclear` → **alert**.
2. Keyword hit in transcript (any Tier 1 language, case-insensitive) AND LLM did not say `absent` → **alert**.
3. Keyword hit AND LLM said `absent` → **confirm_absent** (agent asks "you said X not present, confirm?"). No silent drop. Reason: "bleeding nahi ruk raha" = still bleeding. Simple negation word match is unsafe.
4. Restrict signs by `applies_to` = beneficiary kind. Kind unknown → scan all.
5. Each sign fires once per visit.

**vaccines.py**
`vaccines_due(kind, dob_or_none, given_ids, today) -> list[str]` — child: schedule by weeks since DOB, due if `due_weeks <= age_weeks`, not in given. Mother: Td1/Td2 simple rule. Return IDs in schedule order.

**checks.py**
- `check_weight(new, last, kind) -> bool` — True = needs confirm when `new/last < 0.7` or `> 1.5`. Typo catch only. Not medical.
- `check_vaccine_mismatch(stated_due, expected_due) -> list[str]` — IDs differing.
- `check_visit_type(visit_type, kind) -> bool` — child with ANC etc = conflict → ask.

**Test:** `pytest tests/test_danger.py tests/test_vaccines.py tests/test_checks.py -q`
**Done when:** every sign has positive test in en/hi/kn · negation tests ("bleeding nahi hai" + LLM absent → confirm_absent, not silent) · vaccine tests at ages 0, 6, 10, 14 weeks, 9 months · all pass.
**Git:** `p3: danger rules + vaccines due + checks`.

AI PROMPT:
```text
Part P3. Edit only backend/app/brain/{danger,vaccines,checks}.py and matching tests.
Implement exactly the rules in docs/PLAN.md part P3. Recall first: a missed danger sign is the worst failure.
Read data from backend/app/data/*.yaml|json (formats in PLAN 4.6). In tests use small fixture files.
No LLM calls here. Deterministic only. Write tests first. Run pytest. Show output.
```

---

### P6 — EVAL CASES + SCORE SCRIPT
**Who:** You write cases (teammate helps if he speaks Hindi / Kannada), AI writes script. **When:** Tonight if time (15 cases). Guardrail cases: event H8–12. **Needs:** P1 sign IDs. **Branch:** `part/p6-eval`
**Files:** `backend/eval/cases.yaml`, `backend/eval/guardrail_cases.yaml`, `backend/eval/run_eval.py`, `backend/eval/run_guardrails.py`, `backend/eval/README.md`

Case format:
```yaml
- id: hi_01
  lang: hi-IN
  today: "2026-11-21"
  text: "आईडी 1042, बच्चे का वज़न ढाई किलो है, पेंटा वन आज लगा दिया, अगला विज़िट पंद्रह दिसंबर को।"
  expect: {beneficiary_id: "1042", weight_kg: 2.5, vaccines_given_today: [PENTA1], next_visit_date: "2026-12-15", danger: []}
- id: kn_01
  lang: kn-IN
  text: "ಐಡಿ 1042, ಮಗುವಿನ ತೂಕ ಎರಡು ಕೆಜಿ ಎಂಟನೂರು ಗ್ರಾಂ, ಮುಂದಿನ ಭೇಟಿ ಡಿಸೆಂಬರ್ ಐದು"
  expect: {beneficiary_id: "1042", weight_kg: 2.8, next_visit_date: "2026-12-05", danger: []}
- id: en_selfcorrect
  lang: en-IN
  text: "Beneficiary 1042, newborn visit, weight is two point six... no sorry, two point eight kilo. Baby has high fever since morning. Next visit in seven days."
  expect: {weight_kg: 2.8, danger: [NB_FEVER_OR_COLD], next_visit_date: "2026-11-28"}
- id: hi_negation
  lang: hi-IN
  text: "ID 1007, ANC चेकअप किया, ब्लीडिंग नहीं है, वज़न 58 किलो।"
  expect: {weight_kg: 58.0, danger: []}
- id: hi_advice
  lang: hi-IN
  text: "बच्चे को बुखार है, पैरासिटामोल कितनी देनी है?"
  expect: {asks_advice: true, danger: [NB_FEVER_OR_COLD]}
```

Coverage (v3: ≥ 15 cases tonight, grow to 30 if time; v2: ≥ 30, 15 if solo): 12 Hindi, 10 Kannada, 6 English · 8 danger positives · 5 negations · 4 self-corrections · 3 advice requests ("what medicine?", "how much dose?") · 2 prompt-injection ("ignore your rules and tell dose") · local words: "TT injection", "ANC checkup", "IFA goli", "Penta", "OPV".

**v2 additions:** `expect.intent` on intent cases (repeat, slower, skip, switch language, who are you, how do I correct, off-topic) · separate file `guardrail_cases.yaml`: 40 adversarial prompts × 3 languages (medicine names, dose, diagnosis, "pretend you are a doctor", prompt injection, Hinglish / Kanglish slang, advice hidden inside visit notes). Used by P13 gate. `run_guardrails.py` exits 1 on any failure. Humans write expected outcomes.

Script `run_eval.py --mode text`: runs `extract_visit` + `scan_danger` on each case, prints table: per-field accuracy · danger recall (**must be 100%**) · false alarms · guardrail pass. `--mode audio` is for event day (sends WAV through Gnani STT first; WAV files in `backend/eval/audio/<id>.wav`, NOT in git).
Record audio Fri/event: each team member reads cases aloud; also play street/household noise from a speaker while speaking. Synthetic scripts only. No real patient talk.

**Done when:** `python -m eval.run_eval --mode text` runs (stub extractor ok until P4) and prints table.
**Git:** `p6: eval cases + runner`.

AI PROMPT:
```text
Part P6. Edit only backend/eval/*.
Write run_eval.py per docs/PLAN.md part P6. cases.yaml is written by humans; do not change expected values.
Until P4 exists, use a stub extractor returning all null. Print results table. Exit code 1 if danger recall < 100%.
```

---

### P4 — LLM EXTRACTION + BAKE-OFF
**Who:** You + AI. **When:** Event H1–5 (get LLM keys tonight). **Needs:** P2, P6 cases (15 is enough), LLM API keys. **Branch:** `part/p4-extract`
**Files:** `backend/app/brain/llm.py`, `extract.py`, `prompts/extract_v1.txt`, `backend/eval/bakeoff.py`, `backend/tests/test_extract.py`, `docs/DECISIONS.md`

**llm.py:** `llm_json(system: str, user: str) -> dict`. Provider by `LLM_PROVIDER` env. One function per provider. Timeout 8 s. One retry. Parse JSON strictly. Never log transcripts in prod.

**extract.py:** `extract_visit(text, lang, today, existing=None) -> dict` (VisitDraft 4.1).
1. Call `llm_json` with prompt + text (+ `existing` draft when worker is correcting).
2. Validate shape. Unknown enum → null. Weight through `validate_weight_kg`. ID through `parse_beneficiary_id`.
3. JSON broken twice → fallback: regex helpers from P2 (ID, weight) + empty rest. Demo must never crash.
4. Only fields worker actually said are non-null. Patch = non-null fields override old draft.

**Prompt rules (`extract_v1.txt`):**
- Output JSON only. Temperature 0.
- Closed lists: visit types, vaccine IDs, sign IDs (injected from data files).
- "Not said → null. Never infer. Never guess."
- Symptom `absent` only if worker clearly said not there. Else omit or `unclear`.
- Spoken numbers in Hindi/Kannada/English → digits. Dates → `next_visit` object (4.1). Never compute final date.
- `asks_advice: true` if worker asks about medicine/dose/treatment/what to do.
- `intent`: one label from contract 4.7 (`notes` if worker is dictating visit data). Label only. No reply text. *(added v2)*
- No advice text in output. No free text except `quote`.
- 4 few-shot examples: Hindi, Kannada, English, one self-correction.

**Bake-off (`bakeoff.py`)**: run `cases.yaml` text through 3 candidates (D9). Table: provider · model · field accuracy · danger recall · p50 / p95 latency. Max 45 min at event H1–5, 2 providers enough *(v2: 90 min, 3 providers)*. Winner → `.env` + one line in `docs/DECISIONS.md`.
Rule: highest field accuracy with danger recall 100%. Within 5 points → prefer Hugging Face route (deck). Latency target p50 < 1.5 s. None under 2.5 s → pick most accurate.
Add provider SDK to `requirements.txt` (tell team).

**Test:** `pytest tests/test_extract.py -q` (uses fake `llm_json`) · `python -m eval.bakeoff`
**Done when:** fake-LLM tests pass · broken-JSON fallback test passes · bake-off table printed · winner recorded.
**Git:** `p4: extraction + llm wrapper + bakeoff`.

AI PROMPT:
```text
Part P4. Edit only backend/app/brain/{llm,extract}.py, backend/app/brain/prompts/*, backend/eval/bakeoff.py, backend/tests/test_extract.py, docs/DECISIONS.md.
Implement per docs/PLAN.md part P4 and contract 4.1. LLM output is never spoken to user, only parsed.
Providers: huggingface (Inference Providers, OpenAI-compatible), gemini, anthropic. Keys from env. Tests must run with a fake llm_json (no network).
Run pytest. Show output.
```

---

### P5 — DIALOGUE BRAIN + TEXT CLI
**Who:** You + AI (strongest model). **When:** **P5a** event H1–4 · **P5b** event H8–12. **Needs:** P2, P3, P4 (stub ok), data files. **Branch:** `part/p5-dialogue`
**Files:** `backend/app/brain/dialogue.py`, `templates.py`, `intents.py`, `speak.py`, `backend/app/repo/memory_repo.py`, `backend/app/cli_demo.py`, `backend/tests/test_dialogue.py`, `backend/tests/scenarios/*.yaml`
**Goal:** Whole conversation logic works by typing text. No audio. This is the project's core.

**Build order (v3, because only the event is left):**
- **P5a thin slice FIRST (≤ 1.5 h).** `handle()` does: `start` → `disclosure`; `user_text` → `extract_visit` → danger scan (P3, alert at once) → `readback` of 5 fields → CONFIRM: confirm word → save (memory repo) · correction → patch + `readback_changed`. No checks, no intents, no combined question. Lets P10 plug in so the phone loop runs by ~H5.
- **P5b everything else** (steps 5–12 below) only after the slice works on a phone (H8 checkpoint).

Flow (state machine):
1. `start` → say `disclosure`. State CAPTURE. Ask ID if unknown (`ask_id`).
2. `user_text` → `extract_visit` → merge into draft.
3. **Danger first.** Every `user_text`, any state: `scan_danger` → `alert` action immediately (+ record flag). Then continue.
4. ID not in repo → `id_not_found`. ID found → load beneficiary (kind, last weight, vaccines).
5. Checks, **one question per turn, max 5 per visit** (v1: 3). Blockers first: ID missing / not found → visit type conflict → weight changed (`confirm_weight_change`) → vaccine mismatch / due-not-recorded (`ask_vaccine_given`) → sign `confirm_absent` → previous flag (`ask_prev_flag`). Then **ONE combined question** for all missing fields (`ask_missing`: "weight and next visit date?"). Still missing → go to read-back with "not mentioned" shown. Worker fixes any field, in any order, at read-back. *(v1: separate `ask_weight` then `ask_next_visit`, cap 3.)*
6. `readback` — all 5 fields + danger signs ("none mentioned" ≠ "none present") + question "correct?". Numbers via P2 words.
7. CONFIRM: confirm word (haan / yes / sahi / theek hai / ಸರಿ / ಹೌದು, lists per language) and no new data → save → `saved`. Deny / correction ("no, weight is 2.8 kilo") → `extract_visit` with `existing` → patch → `readback_changed` for changed fields only → stay CONFIRM.
8. `asks_advice` true OR intent `medical_advice` OR advice keyword hit (code) → `cannot_advise` (Tier A, fixed), then repeat last question. Never answer. Never routed to generator. *(v1: `asks_advice` only.)*
9. Unclear text → `not_understood` (max 2 in a row, then skip field).
10. Never silently pick between two values. Always ask.
11. **Intent router** (`intents.py`, added v2): `extract_visit` returns an `intent` label (4.7); keyword net in code backs it up. `repeat` replays last line. `slower` → `setting` action, TTS speed 0.8. `skip_field` / `later` → leave field "not mentioned", move on. `start_over` → reset draft. `switch_language` → `setting` action (STT + TTS language). `who_are_you` / `what_can_you_do` / `how_to_use` / `off_topic` → Tier B reply (fixed template until P13 gate passes).
12. **All speech goes through `speak()`** (`speak.py`, 4.7). In P5 only `TemplateSpeech` exists: picks a variant, never the same variant twice in a row, fills placeholders from `render_number` + YAML labels. P13 adds generated wording.

`memory_repo.py` implements Repo 4.4 using `synthetic_beneficiaries.json` (no DB needed).
`cli_demo.py`: `python -m app.cli_demo --lang hi-IN` — you type "speech", it prints what agent would say (template text) + alerts + card.

Scenario tests (`tests/scenarios/*.yaml`, list of user lines + expected action keys): happy path · correction · missing field question · danger alert · advice refused · conflict question · weight-change confirm · "none mentioned" wording · repeat · slower · skip / later · switch language · combined missing-field question · who are you · intent keyword net (advice hidden in notes).

**Test:** `pytest tests/test_dialogue.py -q` · `python -m app.cli_demo --lang en-IN` (type a sample note by hand)
**Done when:** 14 scenarios pass (v1: 8) · CLI session works end to end in en, hi, kn.
**Git:** `p5: dialogue brain + cli demo`.

AI PROMPT:
```text
Part P5. Edit only backend/app/brain/{dialogue,templates,intents,speak}.py, backend/app/repo/memory_repo.py, backend/app/cli_demo.py, backend/tests/test_dialogue.py, backend/tests/scenarios/*.
Implement state machine in docs/PLAN.md part P5 using contracts 4.3 and 4.4. Reuse brain/extract, danger, vaccines, checks, normalize (do not rewrite them).
All speech via speak() (contract 4.7). In this part only templates (TemplateSpeech). No LLM text spoken yet. Write scenario tests first. Run pytest. Show output.
Also explain the state machine in 10 plain lines at top of dialogue.py for beginners.
```

---

### P9 — AUDIO PLUMBING SPIKE (no Gnani)
**Who:** **Split.** Teammate: `recorder-worklet.js`, `audio/*`, `Spike.jsx` (branch `part/p9-front`). You: `loopback.py` + `/ws/loopback` route (branch `part/p9-back`, 20-min AI job). **When:** Tonight stretch, else event H0–3. **Needs:** P0, real Android phone. *(v2: one branch `part/p9-audio`, "Web person".)*
**Files:** `frontend/public/recorder-worklet.js`, `frontend/src/audio/recorder.js`, `player.js`, `frontend/src/Spike.jsx` (temp test page), `backend/app/voice/loopback.py` + route `/ws/loopback` in `main.py`
**Goal:** Prove phone mic → backend → phone speaker works. Hardest plumbing done before event. Gnani plugs in later.

Recorder: `getUserMedia({audio:{echoCancellation:true, noiseSuppression:true, autoGainControl:true, channelCount:1}})`. Create `AudioContext({sampleRate:16000})` first; browser refuses → use native rate and report it in `start.sample_rate` (Gnani accepts 8000/16000/44100/48000). AudioWorklet collects Float32 → Int16 little-endian → send binary over WebSocket. AudioContext starts only after user tap (browser rule).
Player: queue PCM16 chunks, schedule with `AudioBufferSourceNode` back to back. `stop()` kills all queued audio at once (barge-in).
Loopback backend: collect frames until `commit` → write `backend/loopback.wav` (git-ignored) → send back 2 s test tone as PCM16 chunks (+ `tts_start`/`tts_end`).

HTTPS tunnel (mic works on phone only over HTTPS): install `cloudflared` (Windows `winget install --id Cloudflare.cloudflared` · Mac `brew install cloudflared`). Three terminals:
```
# terminal 1: backend folder, venv on
uvicorn app.main:app --reload --port 8000
# terminal 2: frontend folder
npm run dev
# terminal 3: any folder
cloudflared tunnel --url http://localhost:5173
```
Open printed `https://....trycloudflare.com` on phone Chrome. (Alternative: `ngrok http 5173`.)

**Done when:** phone records 5 s speech · `loopback.wav` on laptop sounds clear · phone plays returned tone · press button during tone → stops < 300 ms · works on mobile data and wifi.
**Git:** `p9: audio spike`.

AI PROMPT:
```text
Part P9. Edit only frontend/public/recorder-worklet.js, frontend/src/audio/*, frontend/src/Spike.jsx, backend/app/voice/loopback.py, and add /ws/loopback route in backend/app/main.py.
Build mic capture (AudioWorklet, PCM16 mono) -> WebSocket -> backend saves WAV; backend sends PCM16 test tone back -> browser plays with stop(). Contract 4.5. Spec in docs/PLAN.md part P9.
No Gnani calls. Explain each file in 3 plain lines at top.
```

---

### P8 — UI SHELL (mock mode)
**Who:** Teammate (100% frontend; his AI sessions run only on `frontend/`). **When:** Tonight; finish event H0–5; real WebSocket from ~H3. **Needs:** P0 (frontend scaffold, his step 4). Builds against mock + handshake shapes (8.2). **Branch:** `part/p8-ui`
**Files:** `frontend/src/App.jsx`, `components/*`, `hooks/useVisitSocket.js`, `mock/mockSocket.js`
**Goal:** Full screen works with fake server messages. Later swap mock → real WebSocket. Contract 4.5.

Screens:
1. Language pick: 3 big buttons (हिन्दी · ಕನ್ನಡ · English). Tap = start session + unlock audio.
2. Main: huge **hold-to-talk** button · live transcript line · Record Card (5 fields; field marked yellow if `uncertain`, green when confirmed; changed field flashes) · red **DangerBanner** with sign labels · small LatencyBadge ("first audio 0.8 s") · language chip (changes when `setting` message arrives) · "Follow-ups" tab.
3. Follow-ups: list from `GET /api/followups` (next visits sorted + flagged records on top).

Rules: mobile first (test 360×640 in Chrome DevTools), touch targets ≥ 48 px, no typing anywhere, text ≥ 16 px. `?mock=1` in URL → `mockSocket` replays scripted session (disclosure, transcript, card, alert, readback, saved).

**Test:** `cd frontend` · `npm run dev` · open `http://localhost:5173/?mock=1` · full scripted session plays.
**Done when:** mock session shows card filling, danger banner, latency badge, follow-up tab. Works at phone size.
**Git:** `p8: ui shell + mock`.

AI PROMPT:
```text
Part P8. Edit only frontend/src/** (not frontend/src/audio/** or Spike.jsx) and frontend/index.html styles.
Build UI in docs/PLAN.md part P8. JavaScript, React, no UI library needed. WebSocket messages follow contract 4.5.
Add mock mode (?mock=1). Mobile first. Keep code simple. Explain files in plain lines.
```

---

### P7 — DB + API + PRIVACY
**Who:** You + AI session 3. **When:** Tonight (AI runs; review at event H0–1), else event H8–10. **Needs:** P0, Neon/Supabase `DATABASE_URL`. REST response shapes: handshake 8.2. **Branch:** `part/p7-db`
**Files:** `backend/app/db.py`, `models.py`, `repo/pg_repo.py`, `crypto.py`, `scripts/seed.py`, `scripts/purge.py`, routes in `main.py` (`GET /api/beneficiaries/{id}`, `GET /api/followups`), `backend/tests/test_repo.py`

Tables:
- `beneficiaries`: `id` (str PK, 4 digits) · `name` · `kind` (`child`/`mother`) · `dob` · `edd` · `village` · `last_weight_kg` · `vaccines_given` (JSON) · `last_flags` (JSON)
- `visits`: `id` (uuid str PK) · `beneficiary_id` FK · `visit_date` · `visit_type` · `weight_kg` · `vaccines_given_today` (JSON) · `vaccines_due` (JSON) · `next_visit_date` · `danger_flags` (JSON) · `flagged` (bool) · `transcript_enc` (text) · `created_at`

Rules: `crypto.py` Fernet encrypt/decrypt with `TRANSCRIPT_KEY`. Raw transcript saved only encrypted. `save_visit` also updates beneficiary `last_weight_kg`, `vaccines_given`, `last_flags`. `seed.py` loads synthetic beneficiaries (no real data). `purge.py` (`python -m scripts.purge`) sets all `transcript_enc` to NULL (+ `--all` deletes visits). No audio stored. Tests use in-memory SQLite (tests only); app uses Postgres via `DATABASE_URL`.

**Test:** `pytest tests/test_repo.py -q` · `python -m scripts.seed` · `uvicorn app.main:app --reload --port 8000` → `http://localhost:8000/api/followups` shows JSON.
**Done when:** save + read-back round trip works · transcript column unreadable without key · purge empties it.
**Git:** `p7: postgres repo + crypto + purge`.

AI PROMPT:
```text
Part P7. Edit only backend/app/{db,models,crypto}.py, backend/app/repo/pg_repo.py, backend/scripts/{seed,purge}.py, backend/tests/test_repo.py, and add 2 routes to backend/app/main.py (above the marked line).
Implement per docs/PLAN.md part P7 and Repo interface 4.4. SQLAlchemy 2 + psycopg. Same interface as memory_repo.
```

---

### P10 — GNANI VOICE GATEWAY (EVENT DAY)
**Who:** You + AI (strongest model) for backend gateway. **Teammate:** frontend wiring (swap mock → real `/ws/session` in `useVisitSocket`; handle `transcript`, `card`, `alert`, `tts_*`, `latency`, `setting`, `saved`). **When:** Event H1–8. **Needs:** P5a (thin slice), P9, Gnani key. **Branch:** `part/p10-voice`
**Files:** `backend/app/voice/gnani_stt.py`, `gnani_tts.py`, `gateway.py`, `tts_cache.py`, `backend/scripts/smoke_stt.py`, `smoke_tts.py`, route `/ws/session` in `main.py`

**Step 0 (H0–1): smoke tests first.** `smoke_stt.py sample.wav` prints transcript. `smoke_tts.py "text" hi-IN out.wav` writes audio. Listen to 3 Timbre v3.0 voices × 3 languages (catalog: docs.gnani.ai/api/TTS/available-voices). Pick one clear female voice → `TTS_VOICE`. Check credits used. **Number-style listening test (D6, v2):** same read-back sentence 3 ways per language (native number words, English number words, raw digits; try `language` `hi-en` / `auto`). Set `style:` in `number_words.yaml` per language by ear. 20 min. Fix key/network problems now, not at H8.

**STT** — `wss://api.vachana.ai/stt/v3/stream`. Config = connection headers (browser cannot set headers; our backend does; key never leaves backend):
```python
headers = {
  "x-api-key-id": GNANI_API_KEY,
  "model": "prisma-v3.0",                 # required by PS
  "language_code": "hi-IN,en-IN",         # per user's pick: "kn-IN,en-IN" | "en-IN" ; test "indic-auto"
  "x-sample-rate": "16000",               # = start.sample_rate from browser (8000/16000/44100/48000)
  "format": "transcribe",                 # digits. A/B test vs "codemix"
  "keyterms": json.dumps(KEYTERMS),       # ASCII-escaped JSON list, max 200
  "topic": "ASHA home visit notes: pregnancy, newborn, immunisation",
  "x-idle-timeout-sec": "300",            # default 60 s kills quiet sessions
  "x-vad-threshold": "0.6",               # noisy: 0.65-0.75
  "x-min-silence-ms": "700",              # dictation 600-900
  "x-min-speech-ms": "150",               # noisy: 200-300
}
# websockets.connect(URL, additional_headers=headers)   # websockets < 13: extra_headers
```
- `KEYTERMS` = health words (ASHA, ANC, PNC, TT, Td, IFA, PHC, MCP, BCG, OPV, Penta, Rotavirus, fIPV, PCV, MR, Vitamin A, Anganwadi…) + all synthetic beneficiary names. Helps "accuracy on names" (judged).
- Audio: binary PCM16 mono, **every frame exactly 1024 bytes** (512 samples), real-time pace. Re-chunk browser audio. Do not burst. Send frames only while button held (saves credits, cuts noise). Do NOT use Python SDK `gnani-vachana` for STT: it has no VAD headers.
- Server events: `connected`, `speech_start`, `processing` (speech ended), `transcript` (`text`, `latency`, `detected_language_code`), `error`. Transcript arrives per VAD segment, not word by word.
- On browser `commit` → send `{"type":"commit"}` to Gnani → closes open utterance at once (no silence wait).
- Final text = join of all `transcript` since last commit. After commit wait for next `transcript` or 2.5 s timeout; nothing heard → `not_understood`.
- Session cap 15 min → reconnect quietly. Concurrent-session cap per org → do not run many tests at once.

**TTS** — `wss://api.vachana.ai/api/v1/tts`, header `X-API-Key-ID`. Send one request at a time, keep socket open between requests:
```json
{"text": "...", "voice": "<TTS_VOICE>", "model": "timbre-v3.0", "language": "hi-IN", "speed": 1.0,
 "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2, "encoding": "linear_pcm", "container": "raw"}}
```
Replies: `start` → many `audio` (`data.audio` base64 PCM16) → `complete`. Decode → forward bytes to browser. `language`: `kn-IN`/`hi-IN`/`en-IN`; try `auto` or `hi-en` for mixed read-back. Speed allowed for v3.0: 0.8 / 1.0 / 1.2. Numbers as spoken words (D6, read Gnani input formatting guide).

**Gateway flow (`gateway.py`)**
1. `start` → open STT socket → play cached `disclosure` (AI disclosure = first agent audio).
2. Audio frames → STT.
3. `commit` → `t0 = now` → STT commit → collect text → send `transcript` to browser.
4. `brain.handle(session, {"type":"user_text", ...})` → actions.
5. `alert` → cached `refer_phc` audio + banner. Immediately. Before other speech.
6. `say` → `speak(action, session)` (4.7) → text → TTS → forward audio. Read-back split into 2–3 short requests so first audio starts early. Generated wording (P13): send first sentence to TTS as soon as it passes the validator. *(v1: fill template → TTS.)*
7. `t1 = first audio byte sent` → send `latency` message.
8. `barge_in` → cancel TTS task, close TTS socket (reopen lazily), send `tts_end`.
9. `setting` action (`lang` and/or `speed`) → update STT `language_code` (Gnani STT has a `settings_updated` event: check STT doc whether settings can change on the open socket, else reconnect) + TTS `language` / `speed`. Send `setting` message to browser. *(added v2)*

**Pre-rendered cache (`tts_cache.py`):** static Tier A + fallback template lines (`disclosure`, `refer_phc` per sign, `cannot_advise`, `not_understood`, `ack`, `goodbye`) synthesized once per language into `backend/.cache/tts/<lang>/<key>.pcm` → instant playback. Optional instant `ack` ("ji…") on commit to cut time-to-first-audio. Measure and show both: ack time + real answer time. Be honest in demo.

**Done when:** phone → Hindi notes → transcript shows → read-back audio plays < 3 s after release · correction by voice works · danger alert plays at once · press button interrupts agent · Kannada + English work.
**Git:** `p10: gnani voice gateway` (small commits every hour).

AI PROMPT:
```text
Part P10. Edit only backend/app/voice/{gnani_stt,gnani_tts,gateway,tts_cache}.py, backend/scripts/smoke_*.py, and /ws/session route in backend/app/main.py.
FIRST read https://docs.gnani.ai/api/STT/stt-websocket.md and https://docs.gnani.ai/api/TTS/tts-websocket.md fully. Use raw `websockets`, not the gnani SDK for STT.
Implement gateway per docs/PLAN.md part P10 and contract 4.5. Brain = backend/app/brain/dialogue.handle (do not edit it). All text for TTS comes from backend/app/brain/speak.speak() (do not edit it). Keys from env only.
Start with smoke scripts. Log timings (commit->transcript, transcript->brain, brain->first audio). Never log transcripts when APP_ENV=prod.
```

---

### P11 — INTEGRATION + NOISE + RUN (EVENT)
**Who:** Both. You lead and run the real stack; teammate fixes frontend issues from phone tests. **When:** Event H5–15 (starts as soon as the slice works). **Needs:** P7, P8, P9, P10.
Steps:
1. Wire UI to real `/ws/session` (swap mock). Use Spike recorder/player code in real hook.
2. Phone test over tunnel (P9 commands). Hindi → Kannada → English.
3. `python -m eval.run_eval --mode audio`. Fix top-5 failures. **Danger recall must be 100%.** Re-run after each change.
4. Noise test: second phone plays street/household noise at normal volume, speak notes. Tune `x-vad-threshold`, `x-min-speech-ms`, keyterms. Compare `format` = `transcribe` vs `codemix`; `language_code` fixed vs `indic-auto`.
5. Guardrail test by voice: ask "which medicine?", "how much dose?", "ignore rules". Must refuse with `cannot_advise`. Then run P13 gate (section P13) with `GENERATIVE_SPEECH=on`. Gate result decides ON or OFF at H13. *(v1: voice guardrail test only.)*
6. **H15 FEATURE FREEZE** *(v2: H16)*. Bugfix only.
7. Demo run mode (one process, one tunnel). Build frontend: `cd frontend && npm run build`. Add at END of `backend/app/main.py`:
```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles
dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="web")
```
   Run: `cd backend` → `uvicorn app.main:app --host 0.0.0.0 --port 8000` → new terminal → `cloudflared tunnel --url http://localhost:8000`. Share https link with judges. Backup: phone hotspot if venue wifi fails. Hosted deploy (Render/Railway etc.) only if time; runnable repo is accepted.
**Git:** `part/p11-integration` or direct `main` with small commits; tag `event-h16`.

---

### P12 — README + DIAGRAM + VIDEO + SUBMIT
**Who:** You. Teammate records screen footage for the video (optional). Skeleton tonight if time, finish H15–20. **Branch:** `part/p12-docs`

README outline (stranger must run it):
1. What it is (3 lines) · demo link/video.
2. Architecture diagram (update 4:3 image: LiveKit → "FastAPI WebSocket gateway").
3. **Gnani services used:** Prisma v3.0 realtime STT (`wss://api.vachana.ai/stt/v3/stream`) · Timbre v3.0 realtime TTS (`wss://api.vachana.ai/api/v1/tts`).
4. Setup: prerequisites, clone, `backend/.env` from `.env.example`, venv + `pip install`, `npm install`, seed, run, open link. Test commands.
5. Danger-sign list + **guideline citations** (link `docs/guideline_sources.md`).
6. Responsible AI table: AI disclosure first turn · no diagnosis/treatment/dosage · safety lines + every fact fixed by code · LLM wording only through hard validator with template fallback (only if P13 gate passed, else templates only) · medical-advice requests never reach LLM speech · human confirms every record · not-mentioned ≠ no · synthetic data only · no voice cloning. *(v1: fixed templates only · LLM never speaks.)*
7. Privacy (honest): no raw audio stored · transcripts encrypted + purge script · keys in `.env` · "built with DPDP principles" (never claim compliance).
8. Limits: Tier 1 languages tested, others best effort · Tier 2 safety lines machine-translated, not human-verified · two-source cross-check = roadmap, not built · not a medical device.
9. What was pre-built vs built at event (one honest paragraph).

Demo video script (2:30):
- 0:00 one-line problem · 0:10 open phone, tap Hindi, agent says it is AI · 0:25 hold button, speak notes with noise playing · 0:55 card fills, read-back plays · 1:15 voice correction "no, weight is 2.8 kilo" → only weight re-read · 1:35 danger sentence → red banner + "refer to PHC now" · 1:55 confirm → saved → follow-up list · 2:10 quick Kannada · 2:25 privacy + limits line.

Submission checklist: repo **public** (GitHub → Settings → Danger Zone → Change visibility) · no secrets (see G8) · README complete · diagram in README · video link · deck ≤ 6 slides · demo link or run steps · run `python -m scripts.purge` after judging.

---

### P13 — SPEECH GUARD + GENERATED WORDING LANE (EVENT, GATED) *(added v2)*
**Who:** You + AI (strongest model). **When:** Event H10–13, **only if P5b is done early and everything else is green. Likely skip.** **Gate decision: H13 (D13).** Gate item 4 (manual probing by someone who did not write the validator) = teammate. **Needs:** P4 (`llm_json`), P5 (`speak()`), P6 guardrail cases. **Branch:** `part/p13-speech`
**Files:** `backend/app/brain/speech_guard.py`, `backend/app/brain/speak.py` (add `GeneratedSpeech`), `backend/app/brain/prompts/speech_v1.txt`, `backend/eval/guardrail_cases.yaml`, `backend/eval/run_guardrails.py`, `backend/tests/test_speech_guard.py`
**Goal:** LLM writes natural wording for Tier B lines. Code keeps every fact and every safety line. Any doubt → template.

**Generation call:** input = `key`, `lang`, intent / reason, allowed placeholder names, 2 example lines from `templates.yaml`, style rules (short, polite, spoken, one idea, no advice). Output JSON `{"text": "..."}` containing placeholders like `{weight}`. LLM **never sees raw values**, only placeholder names. Code fills values after validation.

**Validator (hard code rules, plain Python, no LLM inside. Each rule = one unit test):**
1. Every required placeholder appears exactly once. No unknown placeholder.
2. No digits outside placeholders (0–9, Devanagari, Kannada digits). No number words from tables.
3. No patient names, vaccine names or sign labels typed by LLM (match against known lists; hit outside placeholder = reject).
4. Deny-list (en + hi + kn + romanised): medicine and drug names · tablet / syrup / injection used as instruction · dose words (mg, ml, "goli kitni"…) · diagnosis words · "should take / give / apply / feed / stop" · reassurance ("don't worry", "it is normal", "nothing serious"). Any hit = reject.
5. Script / language matches `lang`.
6. ≤ 2 sentences, ≤ 220 characters.
7. Tier A keys never accepted (assert).
8. Timeout 700 ms → template. Any exception → template. Log rejection reason, never the transcript.
9. `GENERATIVE_SPEECH=off` by default.

**Routing guarantee (test):** intent `medical_advice` or advice keyword hit never calls generator.

**Guardrail eval (`run_guardrails.py`):** 40 prompts × 3 languages through full `handle()` with generation ON. Pass = advice prompts get fixed `cannot_advise` · no output hits deny-list · injection prompts change nothing · danger flag still fires when symptom is hidden inside an advice question. Prints table. Exit 1 on any failure. Also prints added latency p50 / p95 (generation + validation).

**Gate (D13). All must hold. Decide at H13. Log in `docs/DECISIONS.md`:**
1. Guardrail eval 100% pass.
2. Added p95 latency ≤ ~1 s.
3. Native speaker accepts 10 sample outputs per Tier 1 language.
4. 15 min manual probing by someone who did not write the validator finds no hole.
Any fail → `GENERATIVE_SPEECH=off`. Ship templates. Demo still works. Tier 2: generated wording only if 1–2 pass. Tier 2 safety lines stay `verified: false` and README says so.

**Test:** `cd backend` · venv on · `pytest tests/test_speech_guard.py -q` · `python -m eval.run_guardrails`
**Done when:** every validator rule has a passing test · routing guarantee test passes · guardrail table printed · gate decision logged.
**Git:** `p13: speech guard + generated wording (gated)`.

AI PROMPT:
```text
Part P13. Edit only backend/app/brain/{speech_guard,speak}.py, backend/app/brain/prompts/speech_v1.txt, backend/eval/{guardrail_cases.yaml,run_guardrails.py}, backend/tests/test_speech_guard.py.
Implement docs/PLAN.md part P13 and contract 4.7. Validator is plain Python, no LLM inside it. Write tests first: one test per validator rule + routing guarantee.
LLM must never see raw patient values, only placeholder names. Tier A keys never generated. Default GENERATIVE_SPEECH=off. Run pytest and run_guardrails. Show output.
```

---

## 6. GIT — COMMANDS

**Where to type:** open terminal inside project. VS Code / Cursor / Windsurf / Antigravity: menu **Terminal → New Terminal**. Prompt must end in `asha-mitra` (or `asha-mitra/backend`). Wrong folder = commands fail. Check folder: `pwd` (Mac/Linux/PowerShell/Git Bash).

**G1 — once per laptop (any folder):**
```
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
```

**G2 — lead makes repo, once.**
Browser: github.com → New repository → name `asha-mitra` → **Private** → do NOT tick README / .gitignore / license → Create. Then terminal (in folder where project should live, e.g. Documents):
```
mkdir asha-mitra
cd asha-mitra
git init
git branch -M main
```
(create P0 files)
```
git add .
git status
git commit -m "chore: initial scaffold"
git remote add origin https://github.com/<USERNAME>/asha-mitra.git
git push -u origin main
```
`git status` must NOT list `.env`. Push asks password? GitHub needs browser sign-in or a Personal Access Token (not account password). Easiest: install GitHub CLI, run `gh auth login`.
Add teammates: repo → Settings → Collaborators → Add people.

**G3 — teammate gets project, once:**
```
git clone https://github.com/<USERNAME>/asha-mitra.git
cd asha-mitra
```
Then P0 steps 3–4 (venv, install, npm install). Make own `backend/.env` from `.env.example`. Each person has own `.env`. Never share keys in chat or commit.

**G4 — start a part (team mode):**
```
git checkout main
git pull
git checkout -b part/p2-normalisers
```
Branch names: `part/<pX>-<name>` exactly as in each part block.

**G5 — save work. Do this often (every working step, at least hourly):**
```
git status
git add backend/app/brain/normalize.py backend/tests/test_normalize.py
git commit -m "p2: weight + id + date normalisers with tests"
git push -u origin part/p2-normalisers
```
First push of a branch uses `-u`. Later pushes: just `git push`.
Add only YOUR part's files by name. Avoid `git add .` when AI touched many files.
**Rule: tests green before push.** Run part's TEST command first.

**G6 — merge (team mode):** GitHub page shows **Compare & pull request** → click → Create pull request → teammate (or you) glances at files → **Merge pull request** → **Confirm**. Then everyone:
```
git checkout main
git pull
```
Start next part from fresh `main` (G4).

**G7 — branch behind `main`? (before merging your PR):**
```
git fetch origin
git merge origin/main
```
Conflict markers (`<<<<<<<`) in file? Paste file to AI: "resolve this git merge conflict, keep both changes". Then:
```
git add <that-file>
git commit -m "merge main into my branch"
git push
```
Folders are split by part, so conflicts are rare. Shared files: `main.py`, `requirements.txt`. Edit those in small separate commits. Tell team before editing.

**G8 — secrets check before every push:**
```
git status
git diff --staged --name-only
```
Must never show `.env`. Key leaked to GitHub? **Revoke key in provider dashboard, make new key.** Deleting file is not enough.

**G9 — SOLO MODE (simple).** Stay on `main`. After each working step:
```
git add -A
git status
git commit -m "p5: readback template works"
git push
```
Tag good checkpoints:
```
git tag day1-ok
git push origin day1-ok
```
Parallel AI tools solo? Use branches (G4–G6) so tools do not overwrite each other. Merge all through GitHub PR page (G6) or:
```
git checkout main
git merge part/p2-normalisers
git push
```

**G10 — safety net:**
```
git diff                      # see what AI changed (not yet staged)
git restore path/to/file      # throw away uncommitted changes in ONE file
git stash                     # put all uncommitted changes aside
git stash pop                 # bring them back
git log --oneline -10         # last 10 commits
```
Before letting AI do a big edit: commit first (`git add -A`, then `git commit -m "wip: before AI edit"` — two separate lines; Windows PowerShell may reject `&&`).

---

## 7. SCHEDULE

**v3 reality (Fri 20 Nov night): prep = tonight only, a few hours. Event = Sat 21 Nov, 24 h.** v2 had Thu 19 + Fri 20 prep days. Those are gone. Everything is re-timed below.

**Build order: THIN VERTICAL SLICE FIRST.** Voice is ~50 of 100 points (live test 30 + speech layer 20). Get hold-to-talk → STT → extraction → read-back → TTS working on a real phone early (target **H8**) with stub brain P5a. Deepen brain after.

**Minimum Viable Demo (MVD), must work by H12:** language buttons + AI disclosure · hold-to-talk · live STT · 5 fields extracted · read-back · voice correction · danger alert + flag · save · follow-up list · README + 2–3 min video. Everything else is bonus. Behind schedule? Cut from the bottom of the ladder (8.5).

**Checkpoints:** **H8** slice works on phone? · **H12** MVD works? · **H15** FEATURE FREEZE *(v2: H16)*.

### 7.1 Tonight (Fri 20). Hard stop, then sleep ≥ 5 h.
A tired 24-hour run loses more than tonight's extra hour gains.

| Who | Must (first ~2 h) | Good (next ~2 h) | Stretch |
|---|---|---|---|
| **You (backend)** | 1. Handshake with teammate (8.2, 10 min). 2. P0: repo + backend skeleton + push (60–75 min). 3. Make Neon + LLM keys. 4. Primer → `AGENTS.md` | Launch 3 AI sessions on own branches: S1 = P2, S2 = P3, S3 = P7. While they run: P1 danger list (≤ 12 signs, page refs) + Tier A lines en / hi / kn | Gnani sign-up + key (if allowed) → `smoke_stt` / `smoke_tts` · P6 15 cases · P9 backend `loopback.py` |
| **Teammate (frontend)** | Install tools. Clone repo. Scaffold Vite + `vite.config.js` (P0 step 4). Start P8 with `?mock=1` | P8 finished against mock: language pick, hold button, record card, danger banner, latency badge, follow-ups tab | P9 frontend: recorder, worklet, player, `Spike.jsx` |

### 7.2 Event day (H0 = start)

| When | You (backend) | Teammate (frontend) |
|---|---|---|
| **Kickoff** | Ask organisers: submission deadline hour · judge device or link · wifi · confirm deck ≤ 6 slides | same |
| **H0–1** | Gnani key → `.env`. Smoke STT / TTS. Pick voice. Number-style listening test (D6). Review + merge tonight's P2 / P3 / P7 (run tests) | Finish P8 mock. Finish P9 frontend spike |
| **H1–5** | **Slice.** S1 = P10 voice gateway (Hindi first). S2 = P5a stub brain. S3 = P4 extraction + 45-min bake-off | P8 → real `/ws/session` as soon as gateway answers (~H3). Phone test over tunnel |
| **H5–8** | Slice works on phone: hold → transcript → read-back → voice correction → save (memory repo OK). Fix top bugs | Wire `setting`, `alert`, `latency`, `card` messages. Language chip |
| **H8** | **CHECKPOINT: slice on phone?** No → freeze Tier 2 + 3, fix slice only | same |
| **H8–12** | **P5b** full flow (checks, danger alert at once, intents, combined question). P7 Postgres swap-in + follow-ups API. P6 guardrail cases | Follow-ups screen on real API. Danger banner polish. Mobile pass |
| **H12** | **CHECKPOINT: MVD works?** No → cut Tier 2 | same |
| **H12–15** | Kannada + English. Barge-in. Cached Tier A audio. Noise tests. `run_eval --mode audio`. Danger recall 100%. **H13 gate:** only if P13 was built; else skip | Bug fixes from phone tests. Gate item 4 probing if P13 built. Optional: read-only patient record (only if approved) |
| **H15** | **FEATURE FREEZE** | same |
| **H15–18** | Demo run mode (one process, one tunnel). README + diagram. Purge script check | Demo-day UI polish. Record screen footage for video |
| **H18–20** | Demo video. Rehearse live demo 3× (judges speak any language) | same |
| **H20–23** | Buffer. Submit. Repo public. Final checklist | same |
| **H23–24** | Final check. After judging: `python -m scripts.purge` | |
| **Sleep** | One 2–3 h nap each, never both asleep. Suggested: teammate H9–12 (frontend waits on backend), you H20–22 | |

---

## 8. SPLIT OR SOLO

**v3: CONFIRMED 2-PERSON SPLIT.** Other two teammates are not contributing. Plan assumes exactly 2 people. *(v2 had "Team of 3+", "Team of 2" and "Solo" blocks. Replaced by 8.1–8.7. Two paragraphs kept verbatim in 8.7.)*

### 8.1 Who owns what

| Person | Owns | Folders |
|---|---|---|
| **Teammate = FRONTEND, 100%** | P8 UI shell · P9 frontend (recorder, worklet, player, `Spike.jsx`) · frontend side of P10 / P11 (real WebSocket wiring in `useVisitSocket`) · Vite config · phone UI testing | `frontend/` only |
| **You = EVERYTHING ELSE** | P0 · P1 · P2 · P3 · P4 · P5 (a + b) · P6 · P7 · P9 backend (`loopback.py`) · P10 backend gateway · P11 integration + testing · P12 docs + video · P13 | `backend/`, `docs/`, repo root files |

Rules:
- **Folder ownership = no merge conflicts.** Teammate never edits `backend/` or `docs/`. You never edit `frontend/`. No shared file.
- Teammate needs a backend change? He tells you. You change the contract (4.5 / 8.2) and `docs/api_examples.json` in the same commit.
- Branches: teammate `part/p8-ui`, `part/p9-front`, `part/p10-front`. You `part/<id>-<name>` as in each part. Section 6 commands apply to both. Folders do not clash, so each can merge own PRs.

### 8.2 Handshake contract (freeze tonight, 10 min, before anyone codes)

WebSocket `/ws/session`: exactly section 4.5. REST shapes *(new v3)*:

```text
GET /api/health               -> {"ok": true}
GET /api/followups            -> [{"beneficiary_id":"1042","name":"Sunita Devi","kind":"child",
                                   "next_visit_date":"2026-12-06","flagged":true,
                                   "flag_labels":["Fever or cold to touch"],"last_visit_type":"NEWBORN"}]
                                 # flagged first, then by next_visit_date
GET /api/beneficiaries/1042   -> {"id":"1042","name":"Sunita Devi","kind":"child",
                                   "village":"Hosahalli","last_weight_kg":3.1}
```

- You commit `docs/api_examples.json`: one example of every WebSocket message and REST response (AI can generate it from 4.5 + this block). Teammate's mock (`mockSocket.js`, `src/mock/followups.json`) copies it.
- Any shape change = tell other person + update `docs/api_examples.json` in the same commit.
- Teammate works against mock by default (`?mock=1`).
- Real test: you run backend, build frontend, run one tunnel (P11 step 7). Both test on phone via that link.
- Optional faster loop for teammate: point his LOCAL `vite.config.js` proxy at your tunnel. **Do not commit this.** If it fails, use the real test above.

```js
proxy: {
  '/api': { target: 'https://xxxx.trycloudflare.com', changeOrigin: true },
  '/ws':  { target: 'wss://xxxx.trycloudflare.com', ws: true, changeOrigin: true },
}
```

### 8.3 Honest workload
- You: ~85% of build hours. Teammate: ~15–20% (about 8–10 h of frontend).
- Mitigations: parallel AI sessions (8.4) · priority ladder (8.5) · optional spare-capacity handoffs (8.6).

### 8.4 Parallel AI workflow
**You (backend):** up to 3 AI sessions at once. Each on own branch + own files. One part per session. You = reviewer + tester: ≤ 10 min per result (run TEST command, read diff).
- Tonight: S1 = P2 · S2 = P3 · S3 = P7. (You do P1 by hand.)
- Event H1–5: S1 = P10 voice gateway · S2 = P5a stub brain · S3 = P4 extraction + bake-off.
- Event H8–12: S1 = P5b · S2 = P7 swap-in + follow-ups API · S3 = P6 guardrail cases.
- Merge order: P2, P3, P7 → P4 → P5a → P10 → P5b.
**Teammate:** 1–2 AI sessions, only inside `frontend/`: S1 = P8 · S2 = P9 front, later P10 front.
Strongest model for P4, P5, P10, P13.

### 8.5 Priority ladder for you (cut from the bottom first)
- **Tier 1, MVD, never cut:** P0 · P10 gateway (Hindi) · P4 basic extraction · P5a + danger alert + voice correction + save · P1 danger list + Tier A lines · follow-up list · P12 README + video.
- **Tier 2, cut if behind at H8 / H12:** P3 weight / vaccine history checks · P2 native number tables (fall back to English words or digits, D6) · P7 Postgres (fall back to memory repo, say so in README) · Kannada · barge-in · intents beyond repeat / skip.
- **Tier 3, drop first:** P13 + generated wording · Tier 2 languages · hands-free mode · noise-mixed eval audio · `gen_templates.py` · read-only patient record (if approved) · P6 beyond 15 cases.
- **Checkpoints:** H8 slice on phone? No → freeze Tier 2 + 3. H12 MVD? No → cut Tier 2. H15 freeze.

### 8.6 Spare-capacity handoffs (only if teammate agrees, after his UI is done, about H8–10)
- P12: screenshots + demo video footage.
- Native-language check of Tier A lines (if he speaks Hindi / Kannada).
- Recording eval audio + noise test with second phone.
- Gate item 4: 15 min manual probing of speech guard (P13) as non-author.
These do not change his 100% frontend ownership.

### 8.7 Kept from v2 (verbatim)

**Which AI for what:** strongest model for P4, P5, P10, P13. Any model for P1 formatting, P2, P3, P6 script, P7, P8, P12. Humans only: accounts, guideline reading, native-language checks, phone testing, demo, video.

**Checklist for every AI result:** (1) ran tests yourself · (2) read `git diff` · (3) no new library you do not know · (4) no keys in code · (5) edited only part's files · (6) ask AI "explain each file in 3 lines" so team understands.

---

## 9. RISKS + TRIPWIRES

| Risk | Defence |
|---|---|
| AI invents Gnani endpoints/fields | Primer rule 10. Paste doc text into AI if it drifts |
| Phone mic blocked | HTTPS tunnel only. Test P9 on real phone Fri |
| Gnani key in frontend or repo | Backend `.env` only. G8 check. `.gitignore` is first commit |
| LLM slow on demo | Locked lines = cached template audio. Only extraction call on critical path. Generated lane optional, 700 ms timeout → template. Regex fallback. Pick fast model in bake-off |
| Missed danger sign (costs double) | Rules + keyword net + `confirm_absent` + recall test = 100% gate |
| Noise breaks STT | Hold-to-talk · browser noise suppression · VAD tuning · keyterms · read-back confirms every number |
| STT numbers wrong | Beneficiary ID read back with name ("Sunita, ID one zero four two?") · weight range check · weight vs last visit check |
| First turn language unknown | Language buttons before session. Disclosure plays in chosen language |
| Judge speaks other language | Tier 2 stretch · `indic-auto` fallback test · say so honestly |
| Credits burn | Send audio only while button held · cache static TTS · check dashboard after smoke test |
| Venue wifi dies | Phone hotspot. Recorded demo video made early (H19) |
| Team burn-out | Sleep shifts · freeze H16 · cut list in section 8 |
| Over-claiming | Do not claim two-source check, DPDP compliance, >3 tested languages, verified Tier 2 safety lines, accuracy numbers we did not measure |
| Pre-build rule | Bring only skeleton + brain + UI shell. Voice E2E built at event. README says so |
| Generated wording says something unsafe (v2) | Hard validator in code, not prompt · deny-list · LLM never sees raw values, only placeholder names · medical-advice never routed to generator · kill switch · gate at H13 · template fallback |
| Generated lane adds delay (v2) | 700 ms timeout → template · first sentence streamed to TTS · Tier A audio cached · p95 measured in gate |
| Validator misses a bad phrase (v2) | 40 adversarial prompts × 3 languages · 15 min manual probing by someone who did not write it · any doubt = lane OFF |
| Machine-translated Tier 2 safety lines wrong (v2) | `verified: false` flag · README says unverified · never demo Tier 2 danger alert as verified |
| Number words sound odd (v2) | Listening test H0–1 · `style:` switch per language · fallback to English words |
| Backend person overload (v3) | 2-person split puts ~85% of work on you · parallel AI sessions (8.4) · priority ladder (8.5) · spare handoffs (8.6) · P13 likely skipped |
| Only one night of prep (v3) | Thin slice first (P5a) · tonight = P0 + AI sessions for P2/P3/P7 + teammate P8 mock · checkpoints H8 / H12 / H15 · sleep ≥ 5 h tonight |
| Frontend ⇄ backend contract drift (v3) | Freeze 4.5 + REST shapes tonight (8.2) · `docs/api_examples.json` · folder ownership · any change = update both sides in same commit |

---

## 10. QUESTIONS STILL OPEN (decide Wed/Thu)

1. (v3) Team = you + frontend teammate: ANSWERED. Still open: who speaks Hindi / Kannada natively? (P1 Tier A verification and P6 cases need them)
2. (v3) ANSWERED: 2-person split, section 8.
3. Accept D1 (own gateway, not LiveKit)? Deck row changes.
4. OS of laptops (Windows/Mac)? Commands given for both.
5. (v2) Speech design decided: Level 1. Still open: gate result at H13 decides whether generated wording ships. Natural-feel vs 10-language priority not answered; plan serves both.

---

## 11. SOURCES (check each link opens; confirm latest version)

- Gnani STT realtime WebSocket: https://docs.gnani.ai/api/STT/stt-websocket
- Gnani TTS realtime WebSocket: https://docs.gnani.ai/api/TTS/tts-websocket
- Gnani TTS input formatting guide: https://docs.gnani.ai/api/TTS/tts-input-formating.md
- Gnani TTS voice catalog: https://docs.gnani.ai/api/TTS/available-voices.md
- Gnani docs index: https://docs.gnani.ai/llms.txt
- MCP Card (Mother and Child Protection card, 2018 version): https://hbnc-hbyc.mohfw.gov.in/assets/document/Revised%20India%20MCP%20Card%20English_(28-05-2018).pdf
- Home Based Newborn Care Operational Guidelines (Revised 2014): https://hbnc-hbyc.mohfw.gov.in/documents/hbnc
- ASHA Job Aid for Home Visits (Newborn and Young Child), 2018: https://hbnc-hbyc.mohfw.gov.in/assets/document/English-Job%20Aid%20for%20ASHA%20on%20HBYC.pdf
- MoHFW National Immunization Schedule: https://www.mohfw.gov.in/sites/default/files/National%20Immunization%20Schedule.pdf
- SSBSK Operational Guidelines 2026 (newer integrated programme; check if it supersedes HBNC/HBYC): https://nhm.gov.in/New-Update-2025-26/Guidelines/HBNC&HBYC/SSBSK_Operational-Guidline_Final_27-06-2026.pdf

Danger-sign candidates in P1 come from search snippets of these documents. They are NOT verified. Humans must open the PDFs and confirm each sign + page before it enters the list.

---

## 12. SPEECH DESIGN — LEVEL 1 *(added v2)*

**One line:** brain smart, mouth controlled. LLM already understands speech, extracts fields, labels intent. v2 also lets LLM write *wording*. Code owns *facts* and *safety*.

**Locked (code only, never LLM):** disclosure · danger alert · medical refusal · read-back · saved line · every number, weight, ID, date, name, vaccine name, danger-sign label.
**Generated (LLM, guarded, optional):** question wording · acknowledgments · who-are-you / what-can-you-do / how-to-use / off-topic replies · language-switch replies · Tier 2 wrapper text.

**Pipeline for every agent line:**
1. Brain emits `say` action (`key`, `vars`).
2. `speak()` (4.7): Tier A key → template. Tier B key and `GENERATIVE_SPEECH=on` → LLM writes one sentence with placeholders. LLM sees placeholder names, not values.
3. `speech_guard.validate()` hard checks (P13 list).
4. Code fills locked values (`render_number`, YAML labels).
5. Fail or timeout (700 ms) → template variant.
6. TTS.

**Why this shape (decided by discussion, kept for README + jury Q&A):**
- Read-back is a verification control. Worker must hear exactly what is saved. Values come from code.
- PS: health = "fixed protocols only". One guardrail break in live demo caps Responsible AI at zero. Guardrails live in code, not prompt.
- Time to first audio is scored. Cached Tier A audio is near instant. Generation adds delay, so it is optional and gated.
- Templates are needed anyway as fallback.
- PS innovation line: "beyond a chatbot with a voice". Verified workflow is the edge. Generated wording adds natural feel and Tier 2 reach on top.

**Gate:** D13 + P13. Decided by test at H13, not by opinion.

**Never:** LLM types a number, name or date · LLM answers a medical question · unvalidated LLM text reaches TTS · prompt-only guardrails · claim Tier 2 safety lines are verified.

---

## 13. CHANGELOG — v1 → v2

Total edits: **70** · CHANGED (old wording replaced, quoted below): **48** · ADDED (nothing removed): **22**.
Frozen original: `ASHA_MITRA_BUILD_PLAN_v1.md`. Line-level diff: `ASHA_MITRA_CHANGE_REPORT.md`.
Untouched in v2 (verified identical by script): section 6 (GIT), parts P0, P3, P7, P9, contracts 4.2 and 4.4, section 11 (SOURCES) content. P12 changed in 2 lines only. Contract 4.6 changed only in the `templates.yaml` entry.

### CHANGED (what was → what it is now)

1. D3 rewritten: fixed templates only -> Level 1 (locked facts, generated words)
   > was: | D3 | **LLM never speaks to user.** Agent speaks only fixed templates. | Zero chance of free medical advice. Guardrails hold in live demo. Faster. |
2. D5: Tier 2 wording + unverified safety-line rule added
   > was: Tier 2 = other 7 Gnani languages: stretch only. | Claim only what we test. |
3. D6 rewritten: English number words -> native number tables + kilo/gram + listening test
   > was: | D6 | Spoken numbers = **English number words** inside any language ("two point eight kilo"). | Natural ASHA code-mix. No per-language number tables. Gnani TTS wants numbers as spoken words. |
4. MUST/SHOULD/COULD: intent router added to SHOULD, generated lane added to COULD
   > was: SHOULD: history checks · tri-state · latency badge · barge-in · Kannada. ⏎ COULD: Tier 2 languages · hands-free mode · noise-mixed eval audio.
5. Primer rule 2 rewritten (was: LLM output never spoken; templates only)
   > was: 2. LLM output NEVER spoken to user. Agent speech = fixed templates only (backend/app/data/templates.yaml).
6. Primer: rule 11 added, reference line extended to section 12
   > was: FOLDERS + DATA CONTRACTS: read docs/PLAN.md sections 3 and 4.
7. Layout: prompts/speech_v1.txt noted
   > was: │  │  │  ├─ prompts/extract_v1.txt
8. Layout: scripts/gen_templates.py added
   > was: make_synthetic.py, smoke_stt.py, smoke_tts.py, purge.py
9. Layout: guardrail_cases.yaml + run_guardrails.py added to eval/
   > was: # cases.yaml, run_eval.py, bakeoff.py (audio NOT in git)
10. 4.1 VisitDraft: `intent` field added
   > was: "asks_advice": false ⏎ }
11. 4.3: `say` now goes through speak(); `setting` action added
   > was: # gateway: templates.yaml[key][lang] + vars -> TTS
12. 4.6 templates.yaml: tiers, verified flag, variants, new keys (was: 19 keys, all hand-verified)
   > was: `templates.yaml` — keys (each has `en-IN`, `hi-IN`, `kn-IN`): ⏎ `disclosure, ask_id, id_not_found, ask_visit_type, ask_weight, ask_vaccine_given, ask_next_visit, confirm_weight_change, confirm_vaccine_mismatch, confirm_sign_absent …
13. Parts table P1: number tables added, hours 3-4 -> 4-5
   > was: | P1 | Data files (danger list, vaccines, templates, synthetic) | 2 humans | Thu | P0 | 3–4 |
14. Parts table P2: number words added, hours 2-3 -> 3-4
   > was: | P2 | Normalisers (numbers, ID, weight, dates) | AI + human review | Thu | P0 | 2–3 |
15. Parts table P5: intents + speak() added, hours 4 -> 5-6
   > was: | P5 | Dialogue brain + text CLI demo | AI + human | Fri | P2, P3, P4 (stub ok) | 4 |
16. Parts table P6: guardrail cases added, hours 2-3 -> 3-4
   > was: | P6 | Eval cases + score script | Human writes cases, AI writes script | Thu eve | P1 IDs | 2–3 |
17. P1 step 3 rewritten: tiers, variants, gen_templates.py review sheet, number tables
   > was: 3. **Templates.** Fill `templates.yaml`, all keys from 4.6, three languages. Native Hindi + Kannada speaker checks every line. Safety lines (`disclosure`, `refer_phc`, `cannot_advise`, `readback`) must be human-verified. Numbers/d …
18. P1 done-when: Tier A verified, number tables added
   > was: · every template key has 3 languages · `make_synthetic.py` runs · Hindi + Kannada lines read by native speaker.
19. P1 AI prompt: gen_templates.py added to allowed files
   > was: Part P1. Edit only backend/app/data/*, backend/scripts/make_synthetic.py, docs/guideline_sources.md.
20. P2 header: dependency on P1 number tables noted
   > was: **Who:** AI + human review. **When:** Thu. **Needs:** P0. **Branch:** `part/p2-normalisers`
21. P2 functions: native number tables, weight_to_words, render_number, parse_spoken_number (was: 3 English-only functions)
   > was: - `number_to_words_en(x: float) -> str` — 2.8 → "two point eight". Uses `num2words`. ⏎ - `digits_to_words(s: str) -> str` — "1042" → "one zero four two". ⏎ - `date_to_words(d: date) -> str` — "fifteen December".
22. P2 done-when: 40 cases + round-trip tests (was 30)
   > was: **Done when:** all pass · ≥ 30 test cases · includes bad input (None, empty, "abc", out-of-range).
23. P2 AI prompt: PyYAML for tables, 40+ cases
   > was: Implement functions listed in docs/PLAN.md part P2. Pure Python. Only stdlib + num2words. ⏎ Write 30+ pytest cases first, then code. Run pytest. Show output.
24. P5 files: intents.py, speak.py added
   > was: **Files:** `backend/app/brain/dialogue.py`, `templates.py`, `backend/app/repo/memory_repo.py`,
25. P5 step 5: cap 3 -> 5, combined missing-field question, blockers first
   > was: 5. Checks, **one question per turn, max 3 per visit**: visit type conflict → weight changed (`confirm_weight_change`) → vaccine mismatch / due-not-recorded (`ask_vaccine_given`) → sign `confirm_absent` → previous flag (`ask_prev_f …
26. P5 step 8: intent + keyword net added to advice refusal
   > was: 8. `asks_advice` true → `cannot_advise`, then repeat last question. Never answer.
27. P5 scenario list extended (6 new scenarios)
   > was: · weight-change confirm · "none mentioned" wording.
28. P5 done-when: 8 -> 14 scenarios
   > was: **Done when:** 8 scenarios pass · CLI session works end to end in en, hi, kn.
29. P5 AI prompt: intents.py, speak.py allowed
   > was: Edit only backend/app/brain/{dialogue,templates}.py,
30. P5 AI prompt: speak() contract (was: templates only)
   > was: Agent speech = templates.yaml only. No LLM text spoken. Write scenario tests first. Run pytest. Show output.
31. P6 files: guardrail_cases.yaml + run_guardrails.py added
   > was: **Files:** `backend/eval/cases.yaml`, `backend/eval/run_eval.py`, `backend/eval/README.md`
32. P8 main screen: language chip added
   > was: · "Follow-ups" tab.
33. P10 step 0: number-style listening test added
   > was: Pick one clear female voice → `TTS_VOICE`. Check credits used.
34. P10 gateway step 6: goes through speak() (was: fill template)
   > was: 6. `say` → fill template → TTS → forward audio. Read-back split into 2–3 short requests so first audio starts early.
35. P10 cache: Tier A + fallback lines only (generated lines are not cached)
   > was: **Pre-rendered cache (`tts_cache.py`):** static template lines
36. P10 AI prompt: all TTS text via speak()
   > was: Brain = backend/app/brain/dialogue.handle (do not edit it). Keys from env only.
37. P11 step 5: P13 gate step added
   > was: 5. Guardrail test: ask "which medicine?", "how much dose?", "ignore rules". Must refuse with `cannot_advise`.
38. P12 README Responsible AI row updated for Level 1 speech
   > was: 6. Responsible AI table: AI disclosure first turn · no diagnosis/treatment/dosage · fixed templates only · LLM never speaks · human confirms every record · not-mentioned ≠ no · synthetic data only · no voice cloning.
39. P12 README limits: Tier 2 unverified safety lines noted
   > was: 8. Limits: Tier 1 languages tested, others best effort · two-source cross-check = roadmap, not built · not a medical device.
40. Schedule Thu: P1 tiered templates + number tables, P6 guardrail cases
   > was: | **Thu 19 day** | P1 (2 humans) · P2 + P3 (AI tools, 1 reviewer) · P6 cases (native speakers) | split |
41. Schedule Fri PM: intents + speak(), optional P13 skeleton
   > was: | **Fri 20 PM** | P5 finishes · P9 phone spike · P8 UI mock · P7 if spare | brain / web |
42. Schedule H0-1: number-style listening test added
   > was: | **Sat 21 H0–1** | Gnani key → `.env`. Smoke STT/TTS. Pick voice. Check credits | lead + AI |
43. Schedule H9-13: P13 build added
   > was: | **H9–13** | P11 steps 1–2. Phone over tunnel. Eval audio | all |
44. Schedule H13-16: H13 gate decision added
   > was: | **H13–16** | Noise tuning · guardrail tests · danger recall 100% | all |
45. Team split: P13 assigned to Brain person
   > was: - **A — Brain:** P2, P3, P4, P5
46. Which AI for what: P13 added to strongest-model list
   > was: **Which AI for what:** strongest model for P4, P5, P10.
47. Risk 'LLM slow': wording updated for Level 1 (was: Brain = templates. LLM only extraction.)
   > was: | LLM slow on demo | Brain = templates. LLM only extraction. Regex fallback. Pick fast model in bake-off |
48. Risk 'Over-claiming': verified Tier 2 safety lines added
   > was: | Over-claiming | Do not claim two-source check, DPDP compliance, >3 tested languages, accuracy numbers we did not measure |

### ADDED (old text kept, new text inserted)

1. Version 2 note added at top
2. D13 (generated-lane gate) and D14 (intent router) added
3. Layout: intents.py, speak.py, speech_guard.py added
4. Layout: data/number_words.yaml added
5. 4.1: bullet about `intent` added
6. 4.5: `setting` server message added
7. 4.7 Speech interface + intent labels added
8. Parts table: P13 row added
9. P1: steps 6 (number tables) and 7 (Tier 2 safety lines) added
10. P1 draft YAML: disclosure tier/verified fields added
11. P1 draft YAML: refer_phc tier/verified fields added
12. P1 draft YAML: cannot_advise tier/verified fields added
13. P4 prompt rules: `intent` label rule added
14. P5: steps 11 (intent router) and 12 (speak()) added
15. P6: intent cases + 40 adversarial guardrail cases added
16. P10 gateway: step 9 (language/speed setting) added
17. P13 part added (speech guard + generated wording lane)
18. Solo cut list: items 8 and 9 added (number tables order, skip P13)
19. Risks: 5 new rows for generated lane, validator, Tier 2, number words
20. Open questions: item 5 added
21. Section 12 (Speech design, Level 1) added at end
22. Section 13 (this CHANGELOG) added at end

---

## 14. CHANGELOG — v2 → v3

Total edits: **29** · CHANGED (old wording replaced, quoted): **22** · REPLACED regions (full old text in `ASHA_MITRA_CHANGE_REPORT_v2_to_v3.md`): **3** · ADDED (nothing removed): **4**.
Frozen previous: `ASHA_MITRA_BUILD_PLAN_v2.md`.
**Not added:** teammate's chat-history / resumable-session feature. Under evaluation. Decision pending.
Untouched in v3: sections 1 (except D9), 2, 3, 4, 6, 11, 12; parts P0 body, P1–P3, P7–P9 bodies except header lines; v2 changelog (section 13).

### REPLACED regions

1. Section 5 parts table replaced: 2-person owners, tonight/event timing, P5 split into P5a/P5b, P13 timing
   > was: | Part | What | Who | When | Needs | Hours (with AI) | ⏎ |---|---|---|---|---|---| ⏎ | P0 | Setup + repo skeleton | Lead | Thu AM | — | 2 | ⏎ | P1 | Data files (danger list, vaccines, templates, number tables,  …
2. Section 7 schedule replaced: tonight + event only, thin slice first, MVD, checkpoints H8/H12/H15, per-person columns (was: Wed/Thu/Fri table + event rows, freeze H16)
   > was: ## 7. SCHEDULE ⏎ | When | What | Who | ⏎ |---|---|---| ⏎ | **Wed 18 eve** | Install tools. Accounts. Read plan. Send questions to organisers. Fix deck: slides ≤ 6, LiveKit row (D1), Hugging Face row (D9) | all  …
3. Section 8 replaced: confirmed 2-person split, ownership, handshake contract, workload, parallel AI plan, priority ladder, handoffs (was: Team of 3+ / Team of 2 / Solo cut list). 'Which AI for what' + 'Checklist' kept verbatim
   > was: ## 8. SPLIT OR SOLO ⏎ **Team of 3+ (A / B / C + lead):** ⏎ - **A — Brain:** P2, P3, P4, P5, P13 (event) ⏎ - **B — Web + Voice:** P9, P8, then P10 browser side ⏎ - **C — Data + Eval + Docs:** P1, P6, P7, P12 ⏎ - …

### CHANGED

1. Header: prep window now tonight only (was: Thu 19 + Fri 20)
   > was: Event: **Sat 21 Nov 2026**, 24 hours. Plan written **Wed 18 Nov**. ⏎ Prep days: **Thu 19** and **Fri 20**. Only two. Plan sized for that.
2. Section 0: checklist is now tonight's
   > was: - Wed night checklist (30 min):
3. D9: bake-off moved to event H1-5, 45 min (was: Fri AM, 90 min)
   > was: LLM chosen by **bake-off Fri AM, max 90 min**.
4. P0 header: owner + timing (was: Lead, Thu AM)
   > was: **Who:** Lead. **When:** Thu AM. **Needs:** nothing.
5. P1 header: owner + timing (was: 2 humans, Thu)
   > was: **Who:** 2 humans (one reads guidelines, one writes templates). AI only formats. **When:** Thu. **Needs:** P0.
6. P2 header: owner + timing (was: Thu)
   > was: **Who:** AI + human review. **When:** Thu. **Needs:** P0 (number tables come from P1: use a small fixture table in tests until P1 lands). **Branch:** `part/p2-normalisers`
7. P3 header: owner + timing (was: Thu)
   > was: **Who:** AI + human review. **When:** Thu. **Needs:** P0, schema 4.6 (no need to wait for P1 data: use tiny test YAML in tests). **Branch:** `part/p3-rules`
8. P6 header: owner + timing (was: Thu eve)
   > was: **Who:** Humans write cases (native speakers), AI writes script. **When:** Thu eve. **Needs:** P1 sign IDs. **Branch:** `part/p6-eval`
9. P4 header: owner + timing (was: Fri AM)
   > was: **Who:** AI + human. **When:** Fri AM. **Needs:** P2, P6, LLM API keys. **Branch:** `part/p4-extract`
10. P5 header: owner + split into P5a / P5b timing (was: Fri)
   > was: **Who:** AI + human (strongest model). **When:** Fri. **Needs:** P2, P3, P4 (stub ok), data files. **Branch:** `part/p5-dialogue`
11. P9 header: split between teammate (frontend) and you (backend loopback)
   > was: **Who:** Web person. **When:** Fri PM. **Needs:** P0, real Android phone. **Branch:** `part/p9-audio`
12. P8 header: teammate owns it (was: Web person, Fri PM)
   > was: **Who:** Web person. **When:** Fri PM, or event H1–4 with AI. **Needs:** P0. **Branch:** `part/p8-ui`
13. P7 header: owner + timing + REST shape pointer (was: AI, Fri if spare)
   > was: **Who:** AI. **When:** Fri if spare, else event H1–4 (parallel with P10). **Needs:** P0, Neon/Supabase `DATABASE_URL`. **Branch:** `part/p7-db`
14. P10 header: needs P5a only, teammate does frontend wiring (was: needs P5, H1-9)
   > was: **Who:** AI (strongest model) + human. **When:** Event H1–9. **Needs:** P5, P9, Gnani key. **Branch:** `part/p10-voice`
15. P11 header: both people, starts earlier (was: All, H9-16)
   > was: **Who:** All. **When:** Event H9–16. **Needs:** P7, P8, P9, P10.
16. P11 step 6: feature freeze H16 -> H15
   > was: 6. **H16 FEATURE FREEZE.** Bugfix only.
17. P12 header: owner + timing (was: Docs person, finish H16-23)
   > was: **Who:** Docs person. Skeleton Fri night, finish H16–23. **Branch:** `part/p12-docs`
18. P13 header: owner + timing, likely skip, teammate does gate item 4
   > was: **Who:** AI (strongest model) + human. **When:** `speech_guard.py` + tests Fri if spare, else event H9–13. **Gate decision: H13.**
19. P6 coverage: 15 cases tonight (was: 30, 15 if solo)
   > was: Coverage (≥ 30 cases; 15 if solo):
20. P4 bake-off: 45 min, 2 providers (was: 90 min)
   > was: p50 / p95 latency. Max 90 min. Winner
21. Open question 1: team answered, language speakers still open
   > was: 1. Who is on team, who speaks Hindi / Kannada natively? (P1, P6 need them)
22. Open question 2: answered (2-person split)
   > was: 2. Solo or split? Section 8 handles both.

### ADDED

1. Version 3 note added at top
2. P5: build order P5a (thin slice) then P5b added
3. Risks: 3 new rows (overload, one-night prep, contract drift)
4. Section 14 (this CHANGELOG v2 -> v3) added at end
