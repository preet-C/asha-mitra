# Free demo hosting

Use Cloudflare Pages for the React site and a Render Free web service for the
FastAPI backend. The backend handles the browser's `/ws/session` connection and
the outbound Gnani WebSocket connections.

## 1. Deploy the backend on Render

1. Sign in to Render and connect the GitHub repository `preet-C/asha-mitra`.
2. Choose **New > Blueprint**. Render reads the repository's `render.yaml` and
   creates the `asha-mitra-api` service on the Free plan.
3. Enter the Gnani key and voice in Render's environment setup. Add the LLM
   provider, model, and key if you want the full extraction path. Keep these
   values in Render; never commit them to GitHub.
4. Wait for the deploy to finish. The health check should return `{"ok":true}`
   at `https://<render-service>.onrender.com/api/health`.

The demo uses synthetic in-memory records. Saved visits can be lost if the
free service restarts or spins down.

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
Free web services have ephemeral filesystems, so this setup is for a synthetic
demo rather than durable visit storage.
