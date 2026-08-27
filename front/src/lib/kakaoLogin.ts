/**
 * 카카오 로그인 왕복(round trip) 동안 살아남아야 하는 값.
 *
 * authorize → 카카오 → /auth/kakao/callback 으로 돌아오는 사이 SPA 는 완전히 새로 뜨므로
 * 메모리 상태는 모두 사라진다. 그래서 서버가 준 state(CSRF 검증용)와 로그인 뒤 돌아갈 경로를
 * sessionStorage 에 잠깐 맡긴다. 탭 단위 저장소라 다른 탭의 로그인 시도와 섞이지 않는다.
 */
const STORAGE_KEY = 'climbing.kakao'

export interface KakaoRoundTrip {
  /** GET auth/kakao/authorize/ 가 발급한 state — 콜백의 ?state= 와 같아야 한다 */
  state: string
  /** 로그인 성공 후 돌아갈 앱 내부 경로 */
  from: string
}

export function saveKakaoRoundTrip(trip: KakaoRoundTrip) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(trip))
  } catch {
    // 저장소가 막힌 환경 — 콜백에서 state 불일치로 처리돼 다시 시도하게 된다
  }
}

export function readKakaoRoundTrip(): KakaoRoundTrip | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    const { state, from } = parsed as Partial<KakaoRoundTrip>
    if (typeof state !== 'string' || !state) return null
    return { state, from: safeReturnPath(from) }
  } catch {
    return null
  }
}

export function clearKakaoRoundTrip() {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // 무시
  }
}

/**
 * 돌아갈 경로는 앱 내부 절대 경로('/...')만 허용한다.
 * '//evil.com' 같은 프로토콜 상대 URL 이나 외부 주소가 섞여 들어와도 홈으로 보낸다.
 */
export function safeReturnPath(path: unknown): string {
  if (typeof path !== 'string') return '/'
  if (!path.startsWith('/') || path.startsWith('//')) return '/'
  return path
}
