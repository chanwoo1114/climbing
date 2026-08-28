/**
 * vitest 전역 셋업 (vite.config.ts test.setupFiles).
 *
 * - jest-dom matcher (toBeInTheDocument 등)
 * - msw: 테스트마다 핸들러를 초기화하고, 정의되지 않은 요청은 오류로 잡는다
 *   (실수로 실제 API 를 치는 테스트를 막는다)
 * - 각 테스트 뒤 DOM 정리 + authStore 초기화
 */
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { server } from '@/test/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  server.resetHandlers()
  cleanup()
  // authStore 는 여기서 정적 import 하지 않는다 — 테스트 파일의 vi.mock(axios) 보다 먼저
  // 모듈이 평가되어 실제 axios 가 잡히는 문제가 있다. 테스트가 만든 인스턴스를 뒤늦게 가져와 비운다.
  const { useAuthStore } = await import('@/stores/authStore')
  useAuthStore.getState().clear()
  window.localStorage.clear()
})
afterAll(() => server.close())

// jsdom 에 없는 브라우저 API — dialog(ConfirmDialog) / matchMedia(reduced-motion)
if (typeof HTMLDialogElement !== 'undefined') {
  HTMLDialogElement.prototype.showModal ??= function showModal(this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close ??= function close(this: HTMLDialogElement) {
    this.removeAttribute('open')
  }
}
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}
