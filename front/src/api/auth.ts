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
  /** 홈짐(주로 다니는 암장) pk. 없으면 null */
  homeGym: number | null
  /** 표시용 — 서버가 homeGym 에 맞춰 내려준다 (읽기 전용) */
  homeGymName: string | null
  /** 대표 크루 {id, name}. 없으면 null (쓰기는 MeUpdate.mainCrew 에 pk) */
  mainCrew: { id: number; name: string } | null
  /** 인증 메일 링크를 확인한 시각. null 이면 미인증 */
  emailVerifiedAt: string | null
  createdAt: string
}

/** PATCH /users/me/ — 보낸 필드만 바뀐다. image 는 presigned 업로드(M2) 전까지 폼에서 안 다룬다 */
export type MeUpdate = Partial<Pick<Me, 'nickname' | 'bio' | 'image' | 'homeGym'>> & {
  /** 대표 크루 pk — 내가 활동 중인 크루만. null 이면 해제 */
  mainCrew?: number | null
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

export async function updateMe(input: MeUpdate): Promise<Me> {
  const { data } = await api.patch<Me>('/users/me/', input)
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

// --- 소셜 로그인 (카카오) ---
// 흐름은 backend accounts/views.py 의 "소셜 로그인" 주석과 lib/kakaoLogin.ts 참고

export type SocialProvider = 'kakao'

export interface KakaoAuthorize {
  /** 카카오 인가 페이지 — window.location 으로 이동한다 */
  authorizeUrl: string
  /** 서명된 CSRF 토큰. 콜백의 ?state= 와 대조한 뒤 서버에 되돌려 보낸다 */
  state: string
}

/** 소셜 로그인 성공 응답 — 일반 로그인 토큰 쌍 + 신규 가입 여부(201) */
export interface SocialTokenPair extends TokenPair {
  isNew: boolean
}

export interface SocialAccount {
  provider: SocialProvider
  connectedAt: string
  /** 카카오가 알려준 이메일. 동의하지 않았으면 빈 값 */
  emailAtProvider: string | null
}

export async function fetchKakaoAuthorize(): Promise<KakaoAuthorize> {
  const { data } = await api.get<KakaoAuthorize>('/auth/kakao/authorize/')
  return data
}

export async function kakaoCallback(code: string, state: string): Promise<SocialTokenPair> {
  const { data } = await api.post<SocialTokenPair>('/auth/kakao/callback/', { code, state })
  return data
}

export async function fetchSocialAccounts(): Promise<SocialAccount[]> {
  const { data } = await api.get<SocialAccount[]>('/auth/social/')
  return data
}

/** 204. 비밀번호 없는 계정의 마지막 연결이면 400 last_login_method */
export async function unlinkSocial(provider: SocialProvider) {
  await api.delete(`/auth/social/${provider}/`)
}
