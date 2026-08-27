import { useEffect, useRef } from 'react'
import { Link } from 'react-router'

import type { ChatRoom } from '@/api/chat'
import { getErrorMessage } from '@/api/client'
import Avatar from '@/components/common/Avatar'
import Button from '@/components/common/Button'
import { useMe } from '@/hooks/useAuth'
import { useRooms } from '@/hooks/useChat'

const relative = new Intl.RelativeTimeFormat('ko', { numeric: 'auto' })
const sameYear = new Intl.DateTimeFormat('ko-KR', { month: 'short', day: 'numeric' })
const otherYear = new Intl.DateTimeFormat('ko-KR', { year: '2-digit', month: 'short', day: 'numeric' })
const count = new Intl.NumberFormat('ko-KR')

/** 목록용 상대 시각 — 1시간 안은 분, 하루 안은 시간, 일주일 안은 일, 그 뒤는 날짜 */
function formatWhen(iso: string, now = Date.now()): string {
  const date = new Date(iso)
  const diffSec = Math.round((date.getTime() - now) / 1000)
  const abs = Math.abs(diffSec)
  if (abs < 60) return '방금'
  if (abs < 3600) return relative.format(Math.round(diffSec / 60), 'minute')
  if (abs < 86400) return relative.format(Math.round(diffSec / 3600), 'hour')
  if (abs < 7 * 86400) return relative.format(Math.round(diffSec / 86400), 'day')
  return (date.getFullYear() === new Date(now).getFullYear() ? sameYear : otherYear).format(date)
}

/** 방 이름 — 1:1 은 상대 닉네임, 그룹은 방 이름 */
export function roomTitle(room: Pick<ChatRoom, 'isGroup' | 'name' | 'peer'>): string {
  if (!room.isGroup && room.peer) return room.peer.nickname
  return room.name || (room.isGroup ? '그룹 채팅' : '알 수 없는 회원')
}

export function GroupIcon({ className = 'size-10' }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`${className} inline-flex shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500`}
    >
      <svg
        viewBox="0 0 24 24"
        className="size-1/2"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="9" cy="8" r="3.5" />
        <path d="M2.5 20v-1.5a5 5 0 0 1 5-5h3a5 5 0 0 1 5 5V20" />
        <circle cx="17" cy="9" r="2.5" />
        <path d="M21.5 19v-1a4 4 0 0 0-3-3.9" />
      </svg>
    </span>
  )
}

export default function ChatRooms() {
  const { data: me } = useMe()
  const rooms = useRooms({ enabled: !!me })
  const items = rooms.data?.pages.flatMap((page) => page.results) ?? []

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = rooms
  const sentinelRef = useRef<HTMLDivElement>(null)

  // 끝에 가까워지면 다음 페이지 — 관찰자가 없는 환경은 아래 "더 보기" 버튼이 대신한다
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel || !hasNextPage || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting) && !isFetchingNextPage) {
          fetchNextPage()
        }
      },
      { rootMargin: '400px 0px' },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-4 text-2xl font-semibold text-ink-700">채팅</h1>

      {(rooms.isPending || !me) && (
        <p role="status" className="py-10 text-center text-sm text-ink-400">
          대화를 불러오는 중…
        </p>
      )}

      {rooms.isError && (
        <div role="alert" className="py-10 text-center">
          <p className="text-sm text-pretty text-danger-500">
            {getErrorMessage(rooms.error, '대화 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => rooms.refetch()}>
            다시 시도
          </Button>
        </div>
      )}

      {rooms.data && items.length === 0 && (
        <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
          <p className="text-sm font-medium text-ink-600">아직 대화가 없어요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">
            프로필에서 메시지를 보내보세요.
          </p>
          <Link
            to="/users/search"
            className="mt-3 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
          >
            클라이머 찾기
          </Link>
        </div>
      )}

      {items.length > 0 && me && (
        <ul className="divide-y divide-chalk-200 overflow-hidden rounded-card border border-chalk-300 bg-white">
          {items.map((room) => (
            <li key={room.id}>
              <RoomRow room={room} meId={me.id} />
            </li>
          ))}
        </ul>
      )}

      <div ref={sentinelRef} aria-hidden className="h-px" />

      {hasNextPage && (
        <div className="mt-3">
          <Button
            variant="secondary"
            full
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? '불러오는 중…' : '더 보기'}
          </Button>
        </div>
      )}
      {isFetchingNextPage && (
        <p role="status" className="sr-only">
          다음 대화를 불러오는 중
        </p>
      )}
    </div>
  )
}

function RoomRow({ room, meId }: { room: ChatRoom; meId: number }) {
  const last = room.lastMessage
  const unread = room.unreadCount > 0
  const title = roomTitle(room)

  let preview: string
  if (!last) preview = '대화를 시작해 보세요'
  else if (last.type === 'system') preview = last.content
  else if (last.sender?.id === meId) preview = `나: ${last.content}`
  else if (room.isGroup && last.sender) preview = `${last.sender.nickname}: ${last.content}`
  else preview = last.content

  return (
    <Link
      to={`/chat/rooms/${room.id}`}
      className="flex min-h-11 items-center gap-3 px-4 py-3 transition-colors duration-150 hover:bg-chalk-100"
    >
      {room.isGroup ? <GroupIcon /> : <Avatar user={room.peer ?? { nickname: title, image: null }} />}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <p
            className={`min-w-0 flex-1 truncate text-sm ${unread ? 'font-semibold text-ink-700' : 'font-medium text-ink-600'}`}
          >
            {title}
            {room.isGroup && (
              <span className="ml-1 text-xs font-normal text-ink-400 tabular-nums">
                {count.format(room.memberCount)}
              </span>
            )}
          </p>
          {last && (
            <time
              dateTime={last.createdAt}
              className="shrink-0 text-xs text-ink-400 tabular-nums"
            >
              {formatWhen(last.createdAt)}
            </time>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-2">
          <p
            className={`min-w-0 flex-1 truncate text-sm ${
              last?.type === 'system'
                ? 'text-ink-400 italic'
                : unread
                  ? 'text-ink-600'
                  : 'text-ink-400'
            }`}
          >
            {preview}
          </p>
          {unread && (
            // 배지는 CTA 가 아니지만 눈에 띄어야 해서 hold 색을 쓴다 (작게, 한 줄에 하나)
            <span className="inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-hold-500 px-1.5 text-xs font-semibold text-white tabular-nums">
              <span className="sr-only">안 읽은 메시지 </span>
              {room.unreadCount > 99 ? '99+' : room.unreadCount}
            </span>
          )}
        </div>
      </div>
    </Link>
  )
}
