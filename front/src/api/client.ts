import axios, { AxiosError, type AxiosRequestConfig } from 'axios'

import { keysToCamel, keysToSnake } from '@/api/case'
import { useAuthStore } from '@/stores/authStore'

/** 백엔드 공통 응답 래퍼: { success, data, error } */
export interface ApiEnvelope<T> {
  success: boolean
  data: T | null
  error: ApiErrorBody | null
}

export interface ApiErrorBody {
  code: string
  message: string
  /** 필드 검증 실패 시에만 존재 — { email: ["이미 사용 중입니다."] } */
  fields?: Record<string, string[]>
}

/** 인터셉터가 reject 하는 에러 형태 */
export interface ApiError extends Error {
  code: string
  fields: Record<string, string[]> | null
}

export function getFieldError(error: unknown, field: string): string | undefined {
  const fields = (error as ApiError | undefined)?.fields
  return fields?.[field]?.[0]
}

/** 서버 error.code — 'email_not_verified', 'invalid_token', 'throttled' 등 */
export function getErrorCode(error: unknown): string | undefined {
  return (error as ApiError | undefined)?.code
}

/** 사용자에게 보여줄 메시지. 서버 메시지가 없으면 fallback */
export function getErrorMessage(error: unknown, fallback: string): string {
  const message = (error as Error | undefined)?.message
  return message || fallback
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  withCredentials: true,
  timeout: 15_000,
})

// 요청: access 토큰 첨부 + camelCase → snake_case
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (config.data && !(config.data instanceof FormData)) {
    config.data = keysToSnake(config.data)
  }
  if (config.params) config.params = keysToSnake(config.params)
  return config
})

// 응답: 래퍼 해제 + snake_case → camelCase, 401이면 refresh 1회 재시도.
// 동시에 여러 요청이 401 을 받아도 authStore.refresh() 가 single-flight 라 재발급은 한 번만 나간다.
// refresh 가 거부되면 store 가 세션을 지우고, 보호 라우트는 RequireAuth 가 /login 으로 보낸다.
api.interceptors.response.use(
  (response) => {
    const envelope = response.data as ApiEnvelope<unknown>
    if (envelope && typeof envelope === 'object' && 'success' in envelope) {
      response.data = keysToCamel(envelope.data)
    } else {
      response.data = keysToCamel(response.data)
    }
    return response
  },
  async (error: AxiosError<ApiEnvelope<unknown>>) => {
    const original = error.config as AxiosRequestConfig & { _retried?: boolean }

    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true
      const refreshed = await useAuthStore.getState().refresh()
      if (refreshed) return api(original)
    } else if (error.response?.status === 401 && original?._retried) {
      // 재발급까지 했는데도 401 — 토큰의 주인이 사라진(탈퇴 등) 경우다.
      // 공개 API 까지 이 토큰 때문에 막히지 않게 세션을 버린다 (다음 요청은 비로그인으로 나간다).
      useAuthStore.getState().clear()
    }

    const apiError = error.response?.data?.error
    if (!apiError) return Promise.reject(error)

    // 필드 검증 실패는 error.fields 에 필드별 메시지가 담겨 온다.
    // 폼에서 해당 입력칸 아래에 빨간 메시지로 띄우기 위해 그대로 전달한다.
    return Promise.reject(
      Object.assign(new Error(apiError.message), {
        code: apiError.code,
        fields: apiError.fields ?? null,
      }),
    )
  },
)
