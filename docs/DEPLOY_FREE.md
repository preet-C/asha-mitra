# Free demo hosting

Use Cloudflare Pages for the React site and a Render Free web service for the
FastAPI backend. The backend handles the browser's `/ws/session` connection and
the outbound Gnani WebSocket connections.

## 1. Deploy the backend on Render

1. Create a free PostgreSQL project on [Neon](https://neon.com/). In its
   connection details, select **Pooled connection** and copy the connection
   string. Do not paste it into chat or commit it to GitHub.
2. Sign in to Render and connect the GitHub repository `preet-C/asha-mitra`.
3. Choose **New > Blueprint**. Render reads the repository's `render.yaml` and
   creates the `asha-mitra-api` service on the Free plan.
4. When Render asks for environment values, set `DATABASE_URL` to the Neon
   pooled connection string and `TRANSCRIPT_KEY` to a newly generated Fernet
   key. In PowerShell, run this from the `backend` directory to generate the
   key locally:

   ```powershell
   .\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Copy that output directly into Render's secret field. Keep it private and
   save a backup somewhere secure; changing it later prevents decrypting
   transcripts already stored with the old key.
5. Enter the Gnani key and voice in Render's environment setup. Add the LLM
   provider, model, and key if you want the full extraction path. Keep these
   values in Render; never commit them to GitHub.
6. Wait for the deploy to finish. Startup creates the tables and inserts the
   app's synthetic demo beneficiaries if they are missing. The health check
   should return `{"ok":true}` at
   `https://<render-service>.onrender.com/api/health`.

The app stores visits in PostgreSQL. The sample beneficiary records are
synthetic. Neon Free currently includes 1 GB per project; its compute can
scale to zero while idle, so the first database request after a quiet period
may take longer. Check Neon’s current [Free plan details](https://neon.com/blog/neon-free-plan-1-gb-per-project).

## 2. Deploy the frontend on Cloudflare Pages

1. In Cloudflare, choose **Workers & Pages > Create > Pages > Connect to Git**
   and select this repository and the `master` branch.
2. Set the root directory to `frontend`, the build command to `npm run build`,
   and the output directory to `dist`.
3. Add the build environment variable `VITE_API_BASE_URL` with the Render
   service origin, for example `https://asha-mitra-api.onrender.com`.
4. Deploy and copy the resulting `https://<project>.pages.dev` origin.

## 3. Allow the Pages site to call the backend

In Render, open the backend service's **Environment** settings and set
`CORS_ORIGINS` to the exact Pages origin, including `https://` and no path.
Save and redeploy the backend.

The frontend uses this same backend origin for HTTP API requests and secure
WebSockets. No speech-provider key belongs in the Pages settings.

## Before the demo

Render Free services spin down after 15 minutes without traffic and can take
about a minute to wake up. Open the backend health URL shortly before the demo.
The database is separate from Render's ephemeral service filesystem, so saved
visits remain in Neon across backend restarts. Use synthetic data for demos.
