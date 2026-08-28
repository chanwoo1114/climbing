import { Link } from 'react-router'

import type { ClimbBeta } from '@/api/betas'
import { formatRelativeDate } from '@/components/climbs/LogCard'
import Avatar from '@/components/common/Avatar'

const count = new Intl.NumberFormat('ko-KR')

/** 썸네일 없는 카드의 자리표시자 겸 재생 표시 */
export function PlayGlyph({ className = 'size-10' }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M8 5.5v13l11-6.5z" />
    </svg>
  )
}

/** 난이도 알약 — 색은 토큰이 아니라 암장이 정한 값(GymDifficulty.color) */
export function DifficultyPill({ difficulty }: { difficulty: NonNullable<ClimbBeta['difficulty']> }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-xl bg-chalk-100 px-2 py-0.5 text-xs font-medium text-ink-600">
      <span
        aria-hidden
        className="size-2.5 shrink-0 rounded-full border border-chalk-400"
        style={{ backgroundColor: difficulty.color }}
      />
      <span className="truncate">{difficulty.name}</span>
    </span>
  )
}

/** 암장 베타 탭의 격자 카드. 카드 전체가 상세 링크다 */
export default function BetaCard({ beta }: { beta: ClimbBeta }) {
  return (
    <article className="overflow-hidden rounded-card border border-chalk-300 bg-white">
      <Link to={`/betas/${beta.id}`} className="block rounded-card">
        <div className="relative aspect-video bg-ink-700 text-white">
          {beta.thumbnailUrl ? (
            <img
              src={beta.thumbnailUrl}
              alt=""
              loading="lazy"
              className="size-full object-cover"
            />
          ) : (
            <div className="flex size-full items-center justify-center text-chalk-300">
              <PlayGlyph />
            </div>
          )}
          {beta.thumbnailUrl && (
            <span className="absolute right-2 bottom-2 inline-flex size-8 items-center justify-center rounded-full bg-ink-700/70">
              <PlayGlyph className="size-5" />
            </span>
          )}
        </div>

        <div className="space-y-2 p-3">
          <h3 className="line-clamp-2 text-sm font-medium break-words text-ink-700">
            {beta.title}
          </h3>

          {(beta.difficulty || beta.sector) && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-ink-500">
              {beta.difficulty && <DifficultyPill difficulty={beta.difficulty} />}
              {beta.sector && <span className="min-w-0 truncate">{beta.sector}</span>}
            </div>
          )}

          <div className="flex items-center gap-2">
            <Avatar user={beta.user} size="sm" />
            <span className="min-w-0 flex-1 truncate text-xs text-ink-600">{beta.user.nickname}</span>
          </div>

          <p className="flex flex-wrap gap-x-2 text-xs text-ink-400 tabular-nums">
            <span>조회 {count.format(beta.viewCount)}</span>
            <span aria-hidden>·</span>
            <time dateTime={beta.createdAt}>{formatRelativeDate(beta.createdAt)}</time>
          </p>
        </div>
      </Link>
    </article>
  )
}
