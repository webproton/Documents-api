import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Empty prefix: also read non-VITE_ variables (they are NOT exposed to the browser)
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env }
  // Django backend for the dev-server proxy (http://app:8000 inside docker-compose)
  const apiTarget = env.API_PROXY_TARGET ?? 'http://localhost:8000'
  // changeOrigin: false keeps the browser's Host ("localhost:5173"):
  // it is already in DJANGO_ALLOWED_HOSTS, and DRF builds absolute /media/
  // URLs from it, so file links also go through this proxy.
  const proxyOptions = { target: apiTarget, changeOrigin: false }

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      // Same-origin requests from the browser: no CORS needed in development
      proxy: {
        '/api': proxyOptions,
        '/media': proxyOptions,
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: true,
    },
  }
})
