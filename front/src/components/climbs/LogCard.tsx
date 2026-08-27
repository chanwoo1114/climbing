import { Link } from 'react-router'

import type { ClimbLog } from '@/api/climbs'
import Avatar from '@/components/common/Avatar'
import { useToggleLike } from '@/hooks/useClimbs'

const relative = new Intl.RelativeTimeFormat('ko', { numeric: 'auto' })
const absolute = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium' })
const climbedDate = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'long' })
const count = new Intl.NumberFormat('ko-KR')

const MINUTE = 60
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/** 7일 안쪽은 "3시간 전"·"어제", 그 밖은 절대 날짜 */
export function formatRelativeDate(iso: string, now = Date.now()): string {
  const date = new Date(iso)
  const diff = Math.round((date.getTime() - now) / 1000)
  const abs = Math.abs(diff)
  if (abs < MINUTE) return '방금 전'
  if (abs < HOUR) return relative.format(Math.trunc(diff / MINUTE), 'minute')
  if (abs < DAY) return relative.format(Math.trunc(diff / HOUR), 'hour')
  if (abs < 7 * DAY) return relative.format(Math.trunc(diff / DAY), 'day')
  return absolute.format(date)
}

/** "YYYY-MM-DD" 를 로컬 자정으로 — new Date("2026-08-27") 은 UTC 라 한국에선 날짜가 밀린다 */
export function parseDateOnly(value: string): Date {
  const [y, m, d] = value.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function HeartIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-5"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
    >
      <path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 8 3.5 4.5 7 4.5c2 0 3.4 1.1 5 3 1.6-1.9 3-3 5-3 3.5 0 5.6 3.5 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2z" />
    </svg>
  )
}

function CommentIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
    >
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9a1.5 1.5 0 0 1-1.5 1.5H9l-5 4z" />
    </svg>
  )
}

// 텍스트가 작아도 44px 터치 영역. 카드 하단에서 좌우 여백을 상쇄해 글자 정렬을 맞춘다.
const FOOTER_ACTION =
  'inline-flex min-h-11 items-center gap-1.5 rounded-xl px-2 text-sm transition-colors duration-150'

interface Props {
  log: ClimbLog
  /** feed: 메모 3줄 클램프 + 시간이 상세 링크 / detail: 전문 */
  variant?: 'feed' | 'detail'
}

export default function LogCard({ log, variant = 'feed' }: Props) {
  const toggleLike = useToggleLike(log.id)
  const inFeed = variant === 'feed'
  const detailPath = `/logs/${log.id}`
  const authorPath = `/users/${log.user.id}`
  const posted = formatRelativeDate(log.createdAt)

  return (
    <article
      aria-labelledby={`log-${log.id}-author`}
      className="rounded-card border border-chalk-300 bg-white p-4 md:p-5"
    >
      <header className="flex items-center gap-3">
        {/* 아바타는 닉네임 링크와 같은 곳으로 가는 44px 터치 영역 — 키보드 탭 순서에선 닉네임만 */}
        <Link to={authorPath} tabIndex={-1} className="-m-0.5 shrink-0 rounded-full p-0.5">
          <Avatar user={log.user} />
        </Link>
        <div className="min-w-0 flex-1">
          <p id={`log-${log.id}-author`} className="truncate text-sm font-medium text-ink-700">
            <Link to={authorPath} className="hover:underline">
              {log.user.nickname}
            </Link>
          </p>
          <p className="text-xs text-ink-400">
            {inFeed ? (
              <Link to={detailPath} className="-my-2 inline-flex min-h-11 items-center hover:underline">
                <time dateTime={log.createdAt}>{posted}</time>
              </Link>
            ) : (
              <time dateTime={log.createdAt}>{posted}</time>
            )}
          </p>
        </div>
        {!log.isShared && (
          // 비공개 기록은 본인만 볼 수 있으니 본인에게만 보이는 표시다
          <span className="shrink-0 rounded-xl bg-slate-100 px-2 py-1 text-xs font-medium text-slate-500">
            비공개
          </span>
        )}
      </header>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <Link
          to={`/gyms/${log.gym.id}`}
          className="-my-2 inline-flex min-h-11 max-w-full items-center truncate font-medium text-hold-600 hover:underline"
        >
          {log.gym.name}
        </Link>
        {log.difficulty && (
          <span className="inline-flex items-center gap-1.5 text-ink-600">
            {/* 색은 토큰이 아니라 암장이 정한 값 */}
            <span
              aria-hidden
              className="size-3.5 shrink-0 rounded-full border border-chalk-400"
              style={{ backgroundColor: log.difficulty.color }}
            />
            {log.difficulty.name}
          </span>
        )}
        {/* 실패는 오류가 아니라 과정 — danger 대신 ink 로 */}
        <span
          className={`rounded-xl px-2 py-0.5 text-xs font-medium ${
            log.isSuccess ? 'bg-moss-100 text-moss-500' : 'bg-chalk-200 text-ink-500'
          }`}
        >
          {log.isSuccess ? '성공' : '실패'}
        </span>
        <span className="text-ink-500 tabular-nums">{count.format(log.attempts)}회 시도</span>
      </div>

      {log.memo && (
        <p
          className={`mt-3 text-sm text-pretty break-words text-ink-600 ${
            inFeed ? 'line-clamp-3' : 'whitespace-pre-line'
          }`}
        >
          {log.memo}
        </p>
      )}

      {log.videoUrl && (
        <video
          controls
          preload="metadata"
          playsInline
          src={log.videoUrl}
          className="mt-3 aspect-video w-full rounded-xl bg-ink-700"
        />
      )}

      <footer className="-mb-2 mt-2 flex items-center gap-1">
        <button
          type="button"
          aria-pressed={log.isLiked}
          onClick={() => toggleLike.mutate(!log.isLiked)}
          className={`${FOOTER_ACTION} -ml-2 ${
            log.isLiked ? 'text-ochre-500' : 'text-ink-400 hover:text-ochre-500'
          }`}
        >
          <HeartIcon filled={log.isLiked} />
          <span className="sr-only">좋아요 </span>
          <span className="tabular-nums">{count.format(log.likeCount)}</span>
        </button>
        <Link
          to={`${detailPath}#comments`}
          className={`${FOOTER_ACTION} text-ink-400 hover:text-ink-600`}
        >
          <CommentIcon />
          <span className="sr-only">댓글 </span>
          <span className="tabular-nums">{count.format(log.commentCount)}</span>
        </Link>
        <time
          dateTime={log.climbedAt}
          className="ml-auto text-xs text-ink-400 tabular-nums"
        >
          {climbedDate.format(parseDateOnly(log.climbedAt))} 등반
        </time>
      </footer>
    </article>
  )
}
