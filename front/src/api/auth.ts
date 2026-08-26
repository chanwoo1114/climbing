import { api } from '@/api/client'

export interface TokenPair {
  access: string
  refresh: string
}

export interface Me {
  id: number
  email: string
  nickname: string
  bio: string
  image: string
  /** 인증 메일 링크를 확인한 시각. null 이면 미인증 */
  emailVerifiedAt: string | null
  createdAt: string
}

export async function login(email: string, password: string): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>('/auth/login/', { email, password })
  return data
}

export async function register(email: string, nickname: string, password: string) {
  const { data } = await api.post('/auth/register/', { email, nickname, password })
  return data
}

export async function logout(refresh: string) {
  await api.post('/auth/logout/', { refresh })
}

export async function fetchMe(): Promise<Me> {
  const { data } = await api.get<Me>('/users/me/')
  return data
}

// --- 이메일 인증 ---

export async function verifyEmail(token: string) {
  const { data } = await api.post<{ email: string }>('/auth/verify-email/', { token })
  return data
}

/** 계정 유무와 무관하게 항상 성공한다 (계정 열거 방지) */
export async function resendVerification(email: string) {
  await api.post('/auth/verify-email/resend/', { email })
}

// --- 비밀번호 재설정 ---

/** 계정 유무와 무관하게 항상 성공한다 (계정 열거 방지) */
export async function requestPasswordReset(email: string) {
  await api.post('/auth/password-reset/', { email })
}

export async function confirmPasswordReset(uid: string, token: string, password: string) {
  await api.post('/auth/password-reset/confirm/', { uid, token, password })
}
