import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // The single .env lives in the project root, not in frontend/. Vite's default
  // loadEnv reads frontend/.env, so the dev proxy ignored BACKEND_PORT and
  // always pointed at 8000 even when start.sh launched uvicorn on another port.
  const rootEnv = loadEnv(mode, path.resolve(process.cwd(), '..'), '')
  const backendPort = process.env.BACKEND_PORT || rootEnv.BACKEND_PORT || 8000
  const frontendPort = process.env.FRONTEND_PORT || rootEnv.FRONTEND_PORT || 3000

  return {
    plugins: [react()],
    server: {
      port: Number(frontendPort),
      watch: {
        usePolling: true,
        interval: 300,
      },
      proxy: {
        '/api': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on('proxyRes', (proxyRes) => {
              const setCookie = proxyRes.headers['set-cookie']
              if (setCookie) {
                const cookies = Array.isArray(setCookie) ? setCookie : [setCookie]
                proxyRes.headers['set-cookie'] = cookies.map((c) =>
                  c.replace(/; Secure/g, '').replace(/; SameSite=\w+/g, '; SameSite=Lax'),
                )
              }
            })
          },
        },
      },
    },
  }
})
