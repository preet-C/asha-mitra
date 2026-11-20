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