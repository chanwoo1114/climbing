import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as authApi from '@/api/auth'
import { getRefreshToken, useAuthStore } from '@/stores/authStore'

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
