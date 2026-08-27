import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, NavLink, Outlet, useLocation } from 'react-router'

import ToastRegion from '@/components/common/Toast'
import { useLogout, useMe } from '@/hooks/useAuth'
import { useRooms } from '@/hooks/useChat'
import {
  prependNotification,
  targetPath,
  unreadCountKey,
  useUnreadCount,
} from '@/hooks/useNotifications'
import { useNotificationSocket } from '@/hooks/useNotificationSocket'
import { useAuthStore } from '@/stores/authStore'
import { useToastStore } from '@/stores/toastStore'

const countFormat = new Intl.NumberFormat('ko-KR')

// 헤더의 텍스트 링크/버튼은 글자가 작아도 44px 높이의 터치 영역을 갖는다.
const HEADER_ACTION =
  'inline-flex min-h-11 items-center px-2 text-sm font-medium transition-colors duration-150'

// 로그인 후 주요 이동 경로. hold 배경 CTA 는 각 페이지의 몫이라 여기선 텍스트 링크만 쓴다.
// '지도'는 브랜드 아이콘(🧗 → /)이 같은 곳으로 가므로 360px 폭에선 숨긴다.
const NAV: { to: string; label: string; end?: boolean; className?: string }[] = [
  { to: '/', label: '지도', end: true, className: 'hidden sm:inline-flex' },
  { to: '/feed', label: '피드' },
  // '게시판'은 360px 폭에서 텍스트 링크 3개+아이콘 2개가 넘치므로 sm 미만에선 계정 메뉴로 접는다.
  { to: '/posts', label: '게시판', className: 'hidden sm:inline-flex' },
  { to: '/logs/new', label: '기록하기' },
]

const navClass = ({ isActive }: { isActive: boolean }) =>
  `${HEADER_ACTION} ${isActive ? 'text-ink-700' : 'text-ink-500 hover:text-ink-700'}`

function SearchIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.8-3.8" />
    </svg>
  )
}

function ChatIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12a8 8 0 0 1-8 8H8l-4.5 3 .8-4.4A8 8 0 1 1 21 12Z" />
    </svg>
  )
}

/** 헤더의 채팅 아이콘 링크 — 안 읽은 방이 있으면 점을 띄운다 (첫 페이지 기준).
 *  방 밖에서는 소켓이 없으므로 1분마다 가볍게 다시 받는다. */
function ChatNavLink() {
  const rooms = useRooms({ refetchInterval: 60_000 })
  const hasUnread = rooms.data?.pages[0]?.results.some((room) => room.unreadCount > 0) ?? false
  return (
    <NavLink
      to="/chat"
      aria-label={hasUnread ? '채팅 (안 읽은 메시지 있음)' : '채팅'}
      className={({ isActive }) =>
        `relative inline-flex size-11 shrink-0 items-center justify-center rounded-xl transition-colors duration-150 ${
          isActive ? 'text-ink-700' : 'text-ink-500 hover:text-ink-700'
        }`
      }
    >
      <ChatIcon />
      {hasUnread && (
        <span
          aria-hidden
          className="absolute top-2.5 right-2.5 size-2 rounded-full bg-hold-500 ring-2 ring-white"
        />
      )}
    </NavLink>
  )
}

function BellIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </svg>
  )
}

/** 헤더의 알림 아이콘 링크 — 안 읽은 수를 배지로. 소켓이 캐시를 갱신하고 REST 가 포커스 때 보정한다 */
function NotificationNavLink() {
  const { data } = useUnreadCount()
  const unread = data ?? 0
  return (
    <NavLink
      to="/notifications"
      aria-label={unread > 0 ? `알림, 안 읽은 알림 ${countFormat.format(unread)}개` : '알림'}
      className={({ isActive }) =>
        `relative inline-flex size-11 shrink-0 items-center justify-center rounded-xl transition-colors duration-150 ${
          isActive ? 'text-ink-700' : 'text-ink-500 hover:text-ink-700'
        }`
      }
    >
      <BellIcon />
      {unread > 0 && (
        // 배지는 CTA 가 아니지만 눈에 띄어야 해서 hold 색을 쓴다 (채팅 목록의 배지와 같은 규칙)
        <span
          aria-hidden
          className="absolute top-1 right-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-hold-500 px-1 text-[10px] leading-none font-semibold text-white ring-2 ring-white tabular-nums"
        >
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </NavLink>
  )
}

/**
 * 알림 소켓을 앱 전체에서 한 번만 붙이는 머리 없는 컴포넌트 (로그인 상태일 때만 마운트).
 * - unread_count → 배지 캐시 교체
 * - notification → 열려 있는 목록 캐시 맨 앞에 넣고 배지 +1, 알림 페이지 밖이면 토스트
 */
function NotificationSocketBridge() {
  const queryClient = useQueryClient()
  const push = useToastStore((s) => s.push)
  const { pathname } = useLocation()
  useNotificationSocket(true, {
    onUnreadCount: (count) => queryClient.setQueryData(unreadCountKey, count),
    onNotification: (notification) => {
      prependNotification(queryClient, notification)
      if (pathname !== '/notifications') {
        push({ title: notification.message, href: targetPath(notification) })
      }
    },
  })
  return null
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className={`size-4 shrink-0 transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  )
}

export default function RootLayout() {
  const { data: me } = useMe()
  const status = useAuthStore((s) => s.status)
  const booting = status === 'booting'

  return (
    <div className="min-h-full bg-chalk-100">
      {status === 'authenticated' && <NotificationSocketBridge />}
      {/* 키보드 사용자용 — 포커스될 때만 보인다 */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-10 focus:rounded-xl focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:text-ink-700"
      >
        본문으로 건너뛰기
      </a>
      <header className="border-b border-chalk-300 bg-white">
        <div className="mx-auto flex w-full max-w-screen-sm items-center justify-between gap-2 px-4 md:max-w-screen-lg">
          <Link
            to="/"
            className="inline-flex min-h-11 shrink-0 items-center text-lg font-semibold text-ink-700"
          >
            <span aria-hidden className="mr-1.5">
              🧗
            </span>
            <span className="hidden sm:inline">Climbing</span>
            <span className="sr-only sm:hidden">Climbing 홈</span>
          </Link>
          {me ? (
            <nav aria-label="주요 메뉴" className="flex min-w-0 items-center">
              {NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={(state) => `${navClass(state)} ${item.className ?? ''}`}
                >
                  {item.label}
                </NavLink>
              ))}
              {/* 360px 폭에선 아이콘 3개(검색·채팅·알림)가 넘쳐 닉네임이 다 잘린다.
                  실시간 배지가 붙는 채팅·알림을 남기고 검색은 sm 미만에서 계정 메뉴로 접는다. */}
              <NavLink
                to="/users/search"
                aria-label="클라이머 검색"
                className={({ isActive }) =>
                  `hidden size-11 shrink-0 items-center justify-center rounded-xl transition-colors duration-150 sm:inline-flex ${
                    isActive ? 'text-ink-700' : 'text-ink-500 hover:text-ink-700'
                  }`
                }
              >
                <SearchIcon />
              </NavLink>
              <ChatNavLink />
              <NotificationNavLink />
              <AccountMenu nickname={me.nickname} />
            </nav>
          ) : booting ? (
            // 새로고침 직후 세션 복원 중 — '로그인'이 잠깐 떴다 사라지지 않게 자리만 비워둔다
            <span aria-hidden className="min-h-11 w-14" />
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
      <ToastRegion />
    </div>
  )
}

const MENU_ITEM =
  'flex min-h-11 w-full items-center rounded-lg px-3 text-left text-sm font-medium transition-colors duration-150'

/**
 * 닉네임 → 프로필 · 내 기록 · 로그아웃.
 * 텍스트 링크를 하나씩 더 늘리면 360px 폭에서 헤더가 넘쳐서 계정 관련 항목은 메뉴로 접는다.
 * 바깥 클릭·Esc·경로 이동에 닫히고, 화살표 키로 항목을 오간다.
 */
function AccountMenu({ nickname }: { nickname: string }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuId = useId()
  const logout = useLogout()
  const { pathname } = useLocation()

  // 경로가 바뀌면(메뉴 항목을 눌렀으면) 닫는다
  useEffect(() => setOpen(false), [pathname])

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      buttonRef.current?.focus()
      return
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    event.preventDefault()
    if (!open) {
      setOpen(true)
      return
    }
    const items = Array.from(
      rootRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [],
      // 폭에 따라 숨긴 항목(sm:hidden 게시판)은 화살표 이동에서 건너뛴다
    ).filter((item) => item.offsetParent !== null)
    if (items.length === 0) return
    const index = items.indexOf(document.activeElement as HTMLElement)
    const step = event.key === 'ArrowDown' ? 1 : -1
    items[(index + step + items.length) % items.length]?.focus()
  }

  return (
    <div ref={rootRef} onKeyDown={onKeyDown} className="relative ml-1 min-w-0">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
        className={`${HEADER_ACTION} -mr-2 max-w-40 gap-1 rounded-xl border-l border-chalk-300 pl-3 text-ink-500 hover:text-ink-700 md:max-w-56`}
      >
        <span className="min-w-0 truncate">{nickname}</span>
        <ChevronIcon open={open} />
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label="내 계정"
          className="absolute top-full right-0 z-20 mt-1 w-44 rounded-xl border border-chalk-300 bg-white p-1 shadow-sm"
        >
          {/* 헤더에서 숨긴 sm 미만 폭의 게시판·클라이머 검색 진입점 */}
          <NavLink
            to="/posts"
            role="menuitem"
            className={({ isActive }) =>
              `${MENU_ITEM} sm:hidden ${isActive ? 'bg-chalk-100 text-ink-700' : 'text-ink-600 hover:bg-chalk-100'}`
            }
          >
            게시판
          </NavLink>
          <NavLink
            to="/users/search"
            role="menuitem"
            className={({ isActive }) =>
              `${MENU_ITEM} sm:hidden ${isActive ? 'bg-chalk-100 text-ink-700' : 'text-ink-600 hover:bg-chalk-100'}`
            }
          >
            클라이머 검색
          </NavLink>
          <NavLink
            to="/profile"
            role="menuitem"
            className={({ isActive }) =>
              `${MENU_ITEM} ${isActive ? 'bg-chalk-100 text-ink-700' : 'text-ink-600 hover:bg-chalk-100'}`
            }
          >
            프로필
          </NavLink>
          <NavLink
            to="/logs"
            end
            role="menuitem"
            className={({ isActive }) =>
              `${MENU_ITEM} ${isActive ? 'bg-chalk-100 text-ink-700' : 'text-ink-600 hover:bg-chalk-100'}`
            }
          >
            내 기록
          </NavLink>
          {/* 헤더에 텍스트 링크를 더 두면 360px 폭에서 넘치므로 크루도 메뉴로 접는다 */}
          <NavLink
            to="/crews"
            role="menuitem"
            className={({ isActive }) =>
              `${MENU_ITEM} ${isActive ? 'bg-chalk-100 text-ink-700' : 'text-ink-600 hover:bg-chalk-100'}`
            }
          >
            크루
          </NavLink>
          <button
            type="button"
            role="menuitem"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
            className={`${MENU_ITEM} text-ink-500 hover:bg-chalk-100 hover:text-ink-700 disabled:opacity-50`}
          >
            {logout.isPending ? '로그아웃 중…' : '로그아웃'}
          </button>
        </div>
      )}
    </div>
  )
}
