import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true,            // 0.0.0.0 바인딩 — 터널/외부 기기 접속 허용
    allowedHosts: true,    // 터널 도메인(*.trycloudflare.com 등) Host 헤더 허용
    proxy: {
      // 개발 중 /api 요청을 Django로 프록시 (CORS 회피)
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
