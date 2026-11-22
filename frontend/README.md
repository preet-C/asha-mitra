# ASHA Mitra frontend

This React + Vite client talks to the FastAPI backend through the Vite `/api`
and `/ws` proxies. It never contains speech-provider credentials.

From this directory, install dependencies and start the dev server:

```powershell
npm install
npm run dev
```

The backend defaults to `http://127.0.0.1:8000`. To use another backend,
set `ASHA_BACKEND_URL` before starting Vite, for example:

```powershell
$env:ASHA_BACKEND_URL = "http://127.0.0.1:8001"
npm run dev -- --port 5174
```

Use **Demo preview** to explore the scripted flow. It uses synthetic records
and does not request microphone access or call the speech provider. **Live
voice** requires the backend to be running and configured with `GNANI_API_KEY`
and `TTS_VOICE` in `backend/.env`.

Run the frontend checks with `npm run lint` and `npm run build`.
