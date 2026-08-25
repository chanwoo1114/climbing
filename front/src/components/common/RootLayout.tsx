import { Link, Outlet } from 'react-router'

import { useLogout, useMe } from '@/hooks/useAuth'

export default function RootLayout() {
  const { data: me } = useMe()
  const logout = useLogout()

  return (
    <div className="min-h-full bg-chalk-100">
      <header className="border-b border-chalk-300 bg-white">
        <div className="mx-auto flex w-full max-w-screen-sm items-center justify-between px-4 py-3 md:max-w-screen-lg">
          <Link to="/" className="text-lg font-semibold text-ink-700">
            🧗 Climbing
          </Link>
          {me ? (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-ink-500">{me.nickname}</span>
              <button
                type="button"
                onClick={() => logout.mutate()}
                className="text-ink-400 hover:text-ink-600"
              >
                로그아웃
              </button>
            </div>
          ) : (
            <Link to="/login" className="text-sm font-medium text-ink-500 hover:text-ink-700">
              로그인
            </Link>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-screen-sm px-4 py-6 md:max-w-screen-lg">
        <Outlet />
      </main>
    </div>
  )
}
