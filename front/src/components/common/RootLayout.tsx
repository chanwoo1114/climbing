import { Link, Outlet } from 'react-router'

import { useLogout, useMe } from '@/hooks/useAuth'

// 헤더의 텍스트 링크/버튼은 글자가 작아도 44px 높이의 터치 영역을 갖는다.
const HEADER_ACTION =
  'inline-flex min-h-11 items-center px-2 text-sm font-medium transition-colors duration-150'

export default function RootLayout() {
  const { data: me } = useMe()
  const logout = useLogout()

  return (
    <div className="min-h-full bg-chalk-100">
      {/* 키보드 사용자용 — 포커스될 때만 보인다 */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-10 focus:rounded-xl focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:text-ink-700"
      >
        본문으로 건너뛰기
      </a>
      <header className="border-b border-chalk-300 bg-white">
        <div className="mx-auto flex w-full max-w-screen-sm items-center justify-between gap-3 px-4 md:max-w-screen-lg">
          <Link
            to="/"
            className="inline-flex min-h-11 items-center text-lg font-semibold text-ink-700"
          >
            <span aria-hidden className="mr-1.5">
              🧗
            </span>
            Climbing
          </Link>
          {me ? (
            <div className="flex min-w-0 items-center gap-1 text-sm">
              <span className="max-w-40 truncate text-ink-500">{me.nickname}</span>
              <button
                type="button"
                onClick={() => logout.mutate()}
                disabled={logout.isPending}
                className={`${HEADER_ACTION} -mr-2 text-ink-400 hover:text-ink-600 disabled:opacity-50`}
              >
                {logout.isPending ? '로그아웃 중…' : '로그아웃'}
              </button>
            </div>
          ) : (
            <Link to="/login" className={`${HEADER_ACTION} -mr-2 text-ink-500 hover:text-ink-700`}>
              로그인
            </Link>
          )}
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-screen-sm px-4 py-6 md:max-w-screen-lg">
        <Outlet />
      </main>
    </div>
  )
}
