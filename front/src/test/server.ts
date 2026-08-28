/**
 * msw 서버 — 테스트에서 /api/v1 응답을 가짜로 만든다 (백엔드·브라우저 없이).
 *
 * 사용법 (테스트 파일):
 *   server.use(
 *     http.get(API('/users/1/'), () => ok({ id: 1, nickname: 'me', ... })),
 *     http.post(API('/auth/password/change/'), () => fail(400, 'invalid', '...', { current_password: ['틀림'] })),
 *   )
 *
 * 응답 본문은 백엔드 스키마(snake_case) 그대로 적는다 — axios 인터셉터가 camelCase 로 바꾼다.
 */
import { HttpResponse, http } from 'msw'
import { setupServer } from 'msw/node'

/** axios baseURL('/api/v1') 이 jsdom origin 기준으로 풀리므로 같은 origin 을 쓴다 */
export const API_BASE = `${globalThis.location?.origin ?? 'http://localhost:3000'}/api/v1`

/** '/users/1/' → 'http://localhost/api/v1/users/1/' (msw 는 절대 URL 로 매칭한다) */
export const API = (path: string) => `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`

/** 성공 응답 래퍼 { success: true, data } */
export function ok<T>(data: T, status = 200) {
  return HttpResponse.json({ success: true, data, error: null }, { status })
}

/** 오류 응답 래퍼 { success: false, error: { code, message, fields? } } */
export function fail(
  status: number,
  code: string,
  message: string,
  fields?: Record<string, string[]>,
) {
  return HttpResponse.json(
    { success: false, data: null, error: { code, message, ...(fields ? { fields } : {}) } },
    { status },
  )
}

/**
 * 커서 페이지 { results, next_cursor }. 서버의 next_cursor 는 다음 페이지 전체 URL 이고
 * 프론트(cursorFromLink)가 거기서 cursor 값만 뽑는다 — 여기선 cursor 값만 넘기면 URL 을 만들어 준다.
 */
export function page<T>(results: T[], nextCursor: string | null = null) {
  const next = nextCursor ? `${API_BASE}/?cursor=${encodeURIComponent(nextCursor)}` : null
  return ok({ results, next_cursor: next })
}

export const server = setupServer()
export { http, HttpResponse }
