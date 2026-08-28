import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'

import * as authApi from '@/api/auth'
import { safeReturnPath, saveKakaoRoundTrip } from '@/lib/kakaoLogin'
import { getRefreshToken, useAuthStore } from '@/stores/authStore'
import { useToastStore } from '@/stores/toastStore'

export function useLogin() {
  const setSession = useAuthStore((s) => s.setSession)
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      authApi.login(email, password),
    onSuccess: (tokens) => {
      setSession(tokens.access, tokens.refresh)
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })
}

export function useRegister() {
  return useMutation({
    mutationFn: (input: { email: string; nickname: string; password: string }) =>
      authApi.register(input.email, input.nickname, input.password),
  })
}

export function useMe() {
  const accessToken = useAuthStore((s) => s.accessToken)
  return useQuery({
    queryKey: ['me'],
    queryFn: authApi.fetchMe,
    enabled: !!accessToken,
  })
}

export function useUpdateMe() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: authApi.MeUpdate) => authApi.updateMe(input),
    // 서버가 돌려준 최신값으로 캐시를 바로 바꾼다 — 헤더 닉네임도 즉시 반영
    onSuccess: (me) => queryClient.setQueryData(['me'], me),
  })
}

export function useLogout() {
  const clear = useAuthStore((s) => s.clear)
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const refresh = getRefreshToken()
      if (refresh) await authApi.logout(refresh).catch(() => undefined)
    },
    onSettled: () => {
      clear()
      queryClient.removeQueries({ queryKey: ['me'] })
    },
  })
}

// --- 이메일 인증 ---

/**
 * 링크의 토큰으로 인증. mutation 이 아니라 query 인 이유:
 * StrictMode(dev)가 마운트 직후 컴포넌트를 가짜로 언마운트/리마운트하는데, 그 사이에
 * useEffect 에서 부른 mutate() 의 관찰자가 떨어져 나가 결과가 화면에 반영되지 않는다
 * ("인증 확인 중…" 에서 멈춤). query 는 결과가 캐시에 남아 리마운트에도 안전하고,
 * 같은 토큰으로 두 번 마운트돼도 요청은 한 번만 나간다.
 */
export function useVerifyEmail(token: string) {
  return useQuery({
    queryKey: ['verify-email', token],
    queryFn: () => authApi.verifyEmail(token),
    enabled: !!token,
    retry: false, // 위조·만료 토큰은 재시도해도 같다
    staleTime: Infinity,
  })
}

export function useResendVerification() {
  return useMutation({
    mutationFn: (email: string) => authApi.resendVerification(email),
  })
}

// --- 비밀번호 재설정 ---

export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: (email: string) => authApi.requestPasswordReset(email),
  })
}

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: (input: { uid: string; token: string; password: string }) =>
      authApi.confirmPasswordReset(input.uid, input.token, input.password),
  })
}

// --- 소셜 로그인 (카카오) ---

/**
 * 카카오 로그인 시작: 인가 URL 을 받아 state 와 돌아갈 경로를 sessionStorage 에 맡기고 이동한다.
 * 이동 뒤 SPA 가 통째로 사라지므로 mutation 은 pending 인 채로 끝난다 (버튼 로딩 표시용).
 */
export function useKakaoStart() {
  return useMutation({
    mutationFn: async (from: string) => {
      const { authorizeUrl, state } = await authApi.fetchKakaoAuthorize()
      saveKakaoRoundTrip({ state, from: safeReturnPath(from) })
      window.location.assign(authorizeUrl)
    },
  })
}

/**
 * 콜백의 code 를 우리 토큰으로 교환. useVerifyEmail 과 같은 이유로 mutation 이 아니라 query —
 * StrictMode 리마운트에도 요청은 한 번만 나가고 결과가 캐시에 남는다.
 * 인가 코드는 일회용이라 재시도해도 같은 실패가 돌아온다.
 */
export function useKakaoCallback(code: string, state: string) {
  const setSession = useAuthStore((s) => s.setSession)
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: ['kakao-callback', code, state],
    queryFn: async () => {
      const tokens = await authApi.kakaoCallback(code, state)
      setSession(tokens.access, tokens.refresh)
      queryClient.invalidateQueries({ queryKey: ['me'] })
      return tokens
    },
    enabled: !!code && !!state,
    retry: false,
    staleTime: Infinity,
  })
}

export function useSocialAccounts() {
  const accessToken = useAuthStore((s) => s.accessToken)
  return useQuery({
    queryKey: ['social-accounts'],
    queryFn: authApi.fetchSocialAccounts,
    enabled: !!accessToken,
  })
}

export function useUnlinkSocial() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (provider: authApi.SocialProvider) => authApi.unlinkSocial(provider),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['social-accounts'] }),
  })
}

// --- 계정 설정 (pages/Settings) ---

/** 비밀번호 변경 — 새 토큰 쌍으로의 세션 교체는 authApi.changePassword 가 한다 */
export function useChangePassword() {
  return useMutation({
    mutationFn: (input: { currentPassword: string; newPassword: string }) =>
      authApi.changePassword(input.currentPassword, input.newPassword),
  })
}

/**
 * 회원 탈퇴. 성공하면 홈으로 보낸 뒤 세션을 지운다 — 순서가 반대면 RequireAuth 가
 * /settings 에서 anonymous 를 보고 /login 으로 먼저 보내 버린다 (같은 콜백 안이라 한 번에 반영된다).
 */
export function useWithdraw() {
  const clear = useAuthStore((s) => s.clear)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const pushToast = useToastStore((s) => s.push)
  return useMutation({
    mutationFn: (password: string) => authApi.withdrawAccount(password),
    onSuccess: () => {
      navigate('/', { replace: true })
      clear()
      queryClient.removeQueries({ queryKey: ['me'] })
      pushToast({ title: '탈퇴가 완료되었습니다.', description: '그동안 함께해 주셔서 고마워요.' })
    },
  })
}
