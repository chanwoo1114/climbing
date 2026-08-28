import { Link, useSearchParams } from 'react-router'

import { getErrorMessage } from '@/api/client'
import type { Notification, NotificationType } from '@/api/notifications'
import Avatar from '@/components/common/Avatar'
import Button from '@/components/common/Button'
import { formatRelativeDate } from '@/components/climbs/LogCard'
import { useInfiniteSentinel } from '@/hooks/useInfiniteSentinel'
import {
  targetPath,
  useDeleteNotification,
  useMarkAllRead,
  useMarkRead,
  useNotifications,
  useUnreadCount,
} from '@/hooks/useNotifications'

const count = new Intl.NumberFormat('ko-KR')

const FILTERS: { unread: boolean; label: string }[] = [
  { unread: false, label: '전체' },
  { unread: true, label: '안 읽음' },
]

/** ?unread=1 이면 안 읽은 것만. 필터 상태는 URL 에 산다 */
function unreadFromParams(params: URLSearchParams): boolean {
  const value = params.get('unread')
  return value === '1' || value === 'true'
}

function searchFor(unread: boolean): string {
  return unread ? '?unread=1' : ''
}

export default function Notifications() {
  const [searchParams] = useSearchParams()
  const unreadOnly = unreadFromParams(searchParams)

  const notifications = useNotifications(unreadOnly)
  const items = notifications.data?.pages.flatMap((page) => page.results) ?? []
  const unread = useUnreadCount()
  const markAll = useMarkAllRead()

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = notifications
  const sentinelRef = useInfiniteSentinel({ hasNextPage, isFetchingNextPage, fetchNextPage })

  const unreadCount = unread.data ?? 0

  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-ink-700">알림</h1>
        <Button
          variant="secondary"
          onClick={() => markAll.mutate()}
          disabled={unreadCount === 0 || markAll.isPending}
        >
          {markAll.isPending ? '처리 중…' : '모두 읽음'}
        </Button>
      </div>

      <nav aria-label="알림 필터" className="mb-4 inline-flex rounded-xl bg-chalk-200 p-1">
        {FILTERS.map((item) => {
          const active = item.unread === unreadOnly
          return (
            <Link
              key={item.label}
              to={`/notifications${searchFor(item.unread)}`}
              replace
              aria-current={active ? 'page' : undefined}
              className={`inline-flex min-h-11 items-center gap-1.5 rounded-lg px-3 text-sm transition-colors duration-150 sm:px-4 ${
                active
                  ? 'bg-white font-semibold text-ink-700'
                  : 'font-medium text-ink-500 hover:text-ink-700'
              }`}
            >
              {item.label}
              {item.unread && unreadCount > 0 && (
                <span className="text-xs font-normal text-ink-400 tabular-nums">
                  {count.format(unreadCount)}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {notifications.isPending && (
        <p role="status" className="py-10 text-center text-sm text-ink-400">
          알림을 불러오는 중…
        </p>
      )}

      {notifications.isError && (
        <div role="alert" className="py-10 text-center">
          <p className="text-sm text-pretty text-danger-500">
            {getErrorMessage(
              notifications.error,
              '알림을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.',
            )}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => notifications.refetch()}>
            다시 시도
          </Button>
        </div>
      )}

      {notifications.data && items.length === 0 && (
        <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
          <p className="text-sm font-medium text-ink-600">
            {unreadOnly ? '안 읽은 알림이 없어요' : '아직 알림이 없어요'}
          </p>
          <p className="mt-1 text-xs text-pretty text-ink-400">
            {unreadOnly
              ? '새 알림이 오면 여기에 모여요.'
              : '좋아요·댓글·팔로우·모집 결과가 오면 여기에 모여요.'}
          </p>
          {unreadOnly && (
            <Link
              to="/notifications"
              replace
              className="mt-3 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
            >
              전체 알림 보기
            </Link>
          )}
        </div>
      )}

      {items.length > 0 && (
        <ul className="divide-y divide-chalk-200 overflow-hidden rounded-card border border-chalk-300 bg-white">
          {items.map((notification) => (
            <li key={notification.id}>
              <NotificationRow notification={notification} />
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
          다음 알림을 불러오는 중
        </p>
      )}
    </div>
  )
}

/** 종류별 짧은 라벨 — 시간 옆에 붙는다. 서버가 새 type 을 내려도 기본값으로 렌더된다 */
const TYPE_LABEL: Record<NotificationType, string> = {
  like: '좋아요',
  comment: '댓글',
  reply: '답글',
  follow: '팔로우',
  recruitment_closed: '모집 마감',
  recruitment_approved: '참여 승인',
  recruitment_rejected: '참여 거절',
  crew_approved: '크루 가입 승인',
  crew_rejected: '크루 가입 거절',
  crew_joined: '크루 가입',
  crew_owner: '크루장 위임',
  analysis_done: '분석 완료',
  analysis_failed: '분석 실패',
  report_done: '리포트 완료',
  report_failed: '리포트 실패',
}

export function typeLabel(type: string): string {
  return (TYPE_LABEL as Record<string, string>)[type] ?? '알림'
}

/** 행위자가 없는 시스템 알림(모집 마감·승인·분석 결과 등)의 자리 표시 아이콘 */
function TypeIcon({ type }: { type: NotificationType }) {
  let path: string
  let tone: string
  switch (type) {
    case 'recruitment_approved':
    case 'crew_approved':
    case 'analysis_done':
    case 'report_done':
      path = 'm5 12.5 4.5 4.5L19 7.5'
      tone = 'bg-moss-100 text-moss-500'
      break
    case 'analysis_failed':
    case 'report_failed':
      // 경고 삼각형 — 오류 전용 danger
      path = 'M12 4 2.5 20h19L12 4zM12 10v4M12 17.5v.5'
      tone = 'bg-danger-100 text-danger-500'
      break
    case 'crew_owner':
      // 왕관
      path = 'M4 18h16M4 18 3 8l5 4 4-6 4 6 5-4-1 10'
      tone = 'bg-ochre-100 text-ochre-500'
      break
    case 'recruitment_rejected':
    case 'crew_rejected':
      path = 'M7 7l10 10M17 7 7 17'
      tone = 'bg-chalk-200 text-ink-500'
      break
    case 'recruitment_closed':
      path = 'M5 4v16M5 5h13l-2.5 4L18 13H5'
      tone = 'bg-ochre-100 text-ochre-500'
      break
    default:
      path = 'M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20a2 2 0 0 0 4 0'
      tone = 'bg-slate-100 text-slate-500'
  }
  return (
    <span
      aria-hidden
      className={`inline-flex size-10 shrink-0 items-center justify-center rounded-full ${tone}`}
    >
      <svg
        viewBox="0 0 24 24"
        className="size-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d={path} />
      </svg>
    </span>
  )
}

/** 메시지 일부 — 삭제 버튼 aria-label 에 붙여 어느 알림인지 알려준다 */
function excerpt(message: string, max = 20): string {
  const chars = [...message]
  return chars.length > max ? `${chars.slice(0, max).join('')}…` : message
}

/**
 * 행 전체가 대상으로 가는 링크. 누르면 먼저 읽음 처리(낙관적)하고 이동한다.
 * 삭제 버튼은 링크 안에 중첩할 수 없어 옆에 나란히 둔다.
 */
function NotificationRow({ notification }: { notification: Notification }) {
  const markRead = useMarkRead(notification.id)
  const remove = useDeleteNotification(notification.id)
  const unread = !notification.isRead

  return (
    <div
      className={`flex items-stretch transition-colors duration-150 ${
        unread ? 'bg-hold-100/40 hover:bg-hold-100/60' : 'hover:bg-chalk-100'
      }`}
    >
      <Link
        to={targetPath(notification)}
        onClick={() => {
          if (unread && !markRead.isPending) markRead.mutate()
        }}
        className="flex min-h-11 min-w-0 flex-1 items-center gap-3 py-3 pl-4"
      >
        {notification.actor ? (
          <Avatar user={notification.actor} />
        ) : (
          <TypeIcon type={notification.type} />
        )}
        <div className="min-w-0 flex-1">
          <p
            className={`text-sm text-pretty break-words ${
              unread ? 'font-medium text-ink-700' : 'text-ink-600'
            }`}
          >
            {unread && <span className="sr-only">안 읽음: </span>}
            {notification.message}
          </p>
          <p className="mt-0.5 text-xs text-ink-400">
            <span>{typeLabel(notification.type)}</span>
            <span aria-hidden> · </span>
            <time dateTime={notification.createdAt} className="tabular-nums">
              {formatRelativeDate(notification.createdAt)}
            </time>
          </p>
        </div>
        {unread && (
          <span aria-hidden className="size-2 shrink-0 rounded-full bg-hold-500" />
        )}
      </Link>
      <button
        type="button"
        aria-label={`알림 삭제: ${excerpt(notification.message)}`}
        onClick={() => remove.mutate()}
        disabled={remove.isPending}
        className="inline-flex min-h-11 shrink-0 items-center px-3 text-xs font-medium text-ink-400 transition-colors duration-150 hover:text-danger-500 disabled:opacity-50"
      >
        삭제
      </button>
    </div>
  )
}
