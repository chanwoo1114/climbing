import { Navigate, Outlet, useLocation } from 'react-router'

import { useAuthStore } from '@/stores/authStore'

/**
 * 로그인이 필요한 라우트의 부모. routes.tsx 에서 children 으로 감싼다.
 * - booting: 새로고침 직후 세션 복원 중 — 리다이렉트하지 않고 잠깐 기다린다.
 * - anonymous: /login 으로 보내고, 로그인 후 돌아올 경로를 state.from 에 담는다.
 */
export default function RequireAuth() {
  const status = useAuthStore((s) => s.status)
  const location = useLocation()

  if (status === 'booting') {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (status === 'anonymous') {
    return (
      <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
    )
  }
  return <Outlet />
}
