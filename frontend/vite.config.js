import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = env.BACKEND_PORT || 8000
  const frontendPort = env.FRONTEND_PORT || 3000

  return {
    plugins: [react()],
    server: {
      port: Number(frontendPort),
      proxy: {
        '/api': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on('proxyRes', (proxyRes, req, res) => {
              const setCookie = proxyRes.headers['set-cookie']
              if (setCookie) {
                proxyRes.headers['set-cookie'] = setCookie.map(c =>
                  c.replace(/; Secure/g, '').replace(/; SameSite=\w+/g, '; SameSite=Lax')
                )
              }
            })
          },
        },
      },
    },
  }
})
