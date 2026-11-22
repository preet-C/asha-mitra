import process from "node:process";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "ASHA_");
  const backend = env.ASHA_BACKEND_URL || "http://127.0.0.1:8000";
  const websocketBackend = backend.replace(/^http/, "ws");

  return {
    plugins: [react()],
    server: {
      host: true,
      allowedHosts: true,
      proxy: {
        "/api": backend,
        "/ws": { target: websocketBackend, ws: true },
      },
    },
  };
});
