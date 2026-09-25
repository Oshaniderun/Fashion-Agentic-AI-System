import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Agent 2 (retrieval) rules MUST precede the generic '/api' rule so its
      // versioned endpoints and health check reach port 8002, not Agent 1.
      '/api/v1': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
      '/budget': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
        // Browser navigation to SPA pages like /budget/<request-id> must render
        // the app, not hit the backend. API calls (axios) send JSON Accept headers
        // and are still proxied.
        bypass: (req) =>
          req.headers.accept?.includes('text/html') ? '/index.html' : undefined,
      },
      '/health': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      }
    }
  }
})
