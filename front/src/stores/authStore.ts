import axios from 'axios'
import { create } from 'zustand'

/**
 * 토큰 저장 전략
 * - access : 메모리(이 store)에만 보관. XSS로 새어나가도 새로고침 시 사라진다.
 * - refresh: localStorage. 서버가 httpOnly 쿠키로 내려주도록 바꾸면
 *            아래 REFRESH_STORAGE_KEY 관련 코드를 통째로 걷어내면 된다.
 * 변경 시 이 주석을 함께 갱신할 것.
 *
 * 세션 수명
 * - 앱 시작(bootstrap): refresh 토큰이 있으면 access 를 재발급받아 로그인 상태를 복원한다.
 *   그동안 status 는 'booting' — 가드와 헤더는 이 상태를 "아직 모름"으로 취급한다.
 * - 401 재시도: client.ts 인터셉터가 refresh() 를 부른다. 서버가 refresh 토큰을 회전하고
 *   이전 토큰을 블랙리스트에 넣으므로, 동시에 여러 요청이 401 을 받아도 refresh 호출은
 *   반드시 한 번이어야 한다 (single-flight). 두 번째 호출은 이미 폐기된 토큰이라 실패한다.
 */
const REFRESH_STORAGE_KEY = 'climbing.refresh'
const AUTH_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

/** 저장된 refresh 토큰. 키 문자열을 밖에서 직접 쓰지 않도록 여기서만 읽는다. */
export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_STORAGE_KEY)
  } catch {
    return null
  }
}

function storeRefreshToken(token: string | null) {
  try {
    if (token) localStorage.setItem(REFRESH_STORAGE_KEY, token)
    else localStorage.removeItem(REFRESH_STORAGE_KEY)
  } catch {
    // 시크릿 모드 등 저장소가 막힌 환경 — 이번 세션만 로그인 유지된다.
  }
}

export type AuthStatus = 'booting' | 'authenticated' | 'anonymous'

interface AuthUser {
  id: number
  email: string
  nickname: string
}

interface AuthState {
  status: AuthStatus
  accessToken: string | null
  user: AuthUser | null
  setSession: (accessToken: string, refreshToken?: string, user?: AuthUser) => void
  /** access 재발급. 성공이면 true. 서버가 거부하면 세션을 지우고 false. */
  refresh: () => Promise<boolean>
  /** 앱 시작 시 한 번 — 저장된 refresh 토큰으로 로그인 상태 복원 */
  bootstrap: () => Promise<void>
  clear: () => void
}

// 진행 중인 refresh 요청. 있으면 새로 보내지 않고 같은 Promise 를 돌려준다.
let inflight: Promise<boolean> | null = null

export const useAuthStore = create<AuthState>((set, get) => ({
  status: getRefreshToken() ? 'booting' : 'anonymous',
  accessToken: null,
  user: null,

  setSession: (accessToken, refreshToken, user) => {
    if (refreshToken) storeRefreshToken(refreshToken)
    set((state) => ({ accessToken, status: 'authenticated', user: user ?? state.user }))
  },

  refresh: () => {
    if (inflight) return inflight
    inflight = (async () => {
      const refreshToken = getRefreshToken()
      if (!refreshToken) {
        set({ accessToken: null, status: 'anonymous' })
        return false
      }
      try {
        // 인터셉터 재귀를 피하려고 기본 axios를 쓴다.
        const { data } = await axios.post(`${AUTH_BASE}/auth/refresh/`, {
          refresh: refreshToken,
        })
        const payload = data?.data ?? data
        if (!payload?.access) throw new Error('refresh 응답에 access 가 없음')
        if (payload.refresh) storeRefreshToken(payload.refresh)
        set({ accessToken: payload.access, status: 'authenticated' })
        return true
      } catch (error) {
        if (axios.isAxiosError(error) && error.response) {
          // 서버가 명시적으로 거부(만료·블랙리스트) → 세션 종료
          get().clear()
        } else {
          // 네트워크 문제 — 토큰은 남겨두고 이번엔 비로그인으로 취급, 다음 401 때 재시도
          set({ accessToken: null, status: 'anonymous' })
        }
        return false
      }
    })().finally(() => {
      inflight = null
    })
    return inflight
  },

  bootstrap: async () => {
    if (!getRefreshToken()) {
      set({ status: 'anonymous' })
      return
    }
    await get().refresh()
  },

  clear: () => {
    storeRefreshToken(null)
    set({ accessToken: null, user: null, status: 'anonymous' })
  },
}))
