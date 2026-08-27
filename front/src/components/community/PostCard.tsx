import { Link } from 'react-router'

import type { PostSummary } from '@/api/posts'
import { formatRelativeDate } from '@/components/climbs/LogCard'
import {
  CategoryBadge,
  RecruitmentStatusBadge,
  count,
  formatMeetAtShort,
  memberCount,
} from '@/components/community/PostBits'

function CommentIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
    >
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9a1.5 1.5 0 0 1-1.5 1.5H9l-5 4z" />
    </svg>
  )
}

function EyeIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
    >
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

// 작은 메타 링크(닉네임·암장)도 44px 터치 영역 — 카드 안 줄 높이는 음수 마진으로 상쇄
const META_LINK = '-my-2 inline-flex min-h-11 max-w-full items-center truncate hover:underline'

export default function PostCard({ post }: { post: PostSummary }) {
  const detailPath = `/posts/${post.id}`
  const recruitment = post.recruitment

  return (
    <article
      aria-labelledby={`post-${post.id}-title`}
      className="rounded-card border border-chalk-300 bg-white p-4 md:p-5"
    >
      <div className="flex items-center gap-2">
        <CategoryBadge category={post.category} />
        {recruitment && <RecruitmentStatusBadge recruitment={recruitment} />}
        <time
          dateTime={post.createdAt}
          className="ml-auto shrink-0 text-xs text-ink-400 tabular-nums"
        >
          {formatRelativeDate(post.createdAt)}
        </time>
      </div>

      {/* 제목+미리보기가 한 덩어리의 상세 링크 — 두 줄이면 터치 영역이 넉넉하다 */}
      <Link to={detailPath} className="mt-2 block rounded-xl">
        <h2
          id={`post-${post.id}-title`}
          className="line-clamp-2 text-base font-semibold break-words text-ink-700"
        >
          {post.title}
        </h2>
        {post.preview && (
          <p className="mt-1 line-clamp-2 text-sm text-pretty break-words text-ink-500">
            {post.preview}
          </p>
        )}
      </Link>

      {recruitment && (
        <p className="mt-2 flex flex-wrap items-center gap-x-1.5 text-sm text-ink-600">
          <span className="font-medium">
            {recruitment.status === 'open' ? '모집중' : '마감'}
          </span>
          <span className="tabular-nums">
            {count.format(memberCount(recruitment))}/{count.format(recruitment.capacity)}
          </span>
          <span aria-hidden className="text-ink-300">
            ·
          </span>
          <time dateTime={recruitment.meetAt} className="tabular-nums">
            {formatMeetAtShort(recruitment.meetAt)}
          </time>
        </p>
      )}

      <footer className="mt-3 flex min-w-0 items-center gap-x-3 text-xs text-ink-400">
        <Link to={`/users/${post.user.id}`} className={`${META_LINK} font-medium text-ink-600`}>
          {post.user.nickname}
        </Link>
        {post.gym && (
          <Link to={`/gyms/${post.gym.id}`} className={`${META_LINK} text-hold-600`}>
            {post.gym.name}
          </Link>
        )}
        <span className="ml-auto inline-flex shrink-0 items-center gap-1 tabular-nums">
          <CommentIcon />
          <span className="sr-only">댓글 </span>
          {count.format(post.commentCount)}
        </span>
        <span className="inline-flex shrink-0 items-center gap-1 tabular-nums">
          <EyeIcon />
          <span className="sr-only">조회 </span>
          {count.format(post.viewCount)}
        </span>
      </footer>
    </article>
  )
}
