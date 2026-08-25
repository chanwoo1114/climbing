import axios from 'axios'
import { create } from 'zustand'

/**
 * 토큰 저장 전략
 * - access : 메모리(이 store)에만 보관. XSS로 새어나가도 새로고침 시 사라진다.
 * - refresh: localStorage. 서버가 httpOnly 쿠키로 내려주도록 바꾸면
 *            아래 REFRESH_STORAGE_KEY 관련 코드를 통째로 걷어내면 된다.
 * 변경 시 이 주석을 함께 갱신할 것.
 */
const REFRESH_STORAGE_KEY = 'climbing.refresh'
const AUTH_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

interface AuthUser {
  id: number
  email: string
  nickname: string
}

interface AuthState {
  accessToken: string | null
  user: AuthUser | null
  setSession: (accessToken: string, refreshToken?: string, user?: AuthUser) => void
  refresh: () => Promise<boolean>
  clear: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,

  setSession: (accessToken, refreshToken, user) => {
    if (refreshToken) localStorage.setItem(REFRESH_STORAGE_KEY, refreshToken)
    set((state) => ({ accessToken, user: user ?? state.user }))
  },

  refresh: async () => {
    const refreshToken = localStorage.getItem(REFRESH_STORAGE_KEY)
    if (!refreshToken) return false
    try {
      // 인터셉터 재귀를 피하려고 기본 axios를 쓴다.
      const { data } = await axios.post(`${AUTH_BASE}/auth/refresh/`, {
        refresh: refreshToken,
      })
      const payload = data?.data ?? data
      if (!payload?.access) return false
      if (payload.refresh) localStorage.setItem(REFRESH_STORAGE_KEY, payload.refresh)
      set({ accessToken: payload.access })
      return true
    } catch {
      return false
    }
  },

  clear: () => {
    localStorage.removeItem(REFRESH_STORAGE_KEY)
    set({ accessToken: null, user: null })
  },
}))
