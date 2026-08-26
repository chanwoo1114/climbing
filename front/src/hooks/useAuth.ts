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

export function useVerifyEmail() {
  return useMutation({
    mutationFn: (token: string) => authApi.verifyEmail(token),
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
