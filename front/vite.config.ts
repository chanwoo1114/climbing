/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// 백엔드(호스트 8010)로의 프록시 대상. 컨테이너에서는 compose가 주입한다.
const PROXY_TARGET = process.env.VITE_PROXY_TARGET || 'http://localhost:8010'

// SPA 전용 — SSR/loader 패턴 사용 안 함 (CLAUDE.md 참고)
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  // 브라우저 없이 검증 — jsdom + @testing-library + msw (src/test/). `npm test`
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
  server: {
    host: true,
    port: 5180,
    // 컨테이너에서 볼륨 마운트로 돌릴 때 파일 변경 감지가 누락되는 걸 막는다.
    watch: process.env.VITE_USE_POLLING
      ? { usePolling: true, interval: 300 }
      : undefined,
    proxy: {
      // 브라우저는 항상 이 dev 서버(5170)와만 통신하고,
      // /api, /ws 는 여기서 백엔드로 넘긴다. 그래서 외부(공인IP)에서
      // 접속해도 포트 하나(5180)만 열면 된다.
      // 컨테이너로 돌릴 때는 VITE_PROXY_TARGET=http://host.docker.internal:8010
      '/api': { target: PROXY_TARGET, changeOrigin: true },
      '/ws': { target: PROXY_TARGET.replace(/^http/, 'ws'), ws: true },
      // Django admin 도 5180 을 통해 접근 (외부 개발용 — 포트 추가 개방 불필요).
      // changeOrigin 을 끄면 Host 가 보존되어 admin 의 CSRF same-origin 검사가 통과한다.
      '/admin': { target: PROXY_TARGET },
      '/static': { target: PROXY_TARGET },
    },
  },
})
