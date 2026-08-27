import { Link } from 'react-router'

import type { CrewSummary } from '@/api/crews'
import { CrewImage, JoinTypeBadge, StatusBadge, memberCountText } from '@/components/crews/CrewBits'

// 작은 메타 링크(홈짐)도 44px 터치 영역 — 카드 안 줄 높이는 음수 마진으로 상쇄
const META_LINK = '-my-2 inline-flex min-h-11 max-w-full items-center truncate hover:underline'

export default function CrewCard({ crew }: { crew: CrewSummary }) {
  const detailPath = `/crews/${crew.id}`

  return (
    <article
      aria-labelledby={`crew-${crew.id}-name`}
      className="rounded-card border border-chalk-300 bg-white p-4 md:p-5"
    >
      <div className="flex gap-3">
        {/* 이미지는 이름 링크와 같은 곳으로 가는 터치 영역 — 키보드 탭 순서에선 이름만 */}
        <Link to={detailPath} tabIndex={-1} className="shrink-0 rounded-xl">
          <CrewImage crew={crew} />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            {/* 이름+소개가 한 덩어리의 상세 링크 — 두 줄이면 터치 영역이 넉넉하다 */}
            <Link to={detailPath} className="block min-w-0 flex-1 rounded-xl">
              <h2
                id={`crew-${crew.id}-name`}
                className="truncate text-base font-semibold text-ink-700"
              >
                {crew.name}
              </h2>
              {crew.description && (
                <p className="mt-0.5 line-clamp-2 text-sm text-pretty break-words text-ink-500">
                  {crew.description}
                </p>
              )}
            </Link>
            {crew.myStatus && <StatusBadge status={crew.myStatus} />}
          </div>

          <p className="mt-2 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-400">
            <span className="font-medium text-ink-600 tabular-nums">
              <span className="sr-only">크루원 </span>
              {memberCountText(crew)}
            </span>
            <JoinTypeBadge joinType={crew.joinType} />
            {crew.homeGym && (
              <Link to={`/gyms/${crew.homeGym.id}`} className={`${META_LINK} text-hold-600`}>
                {crew.homeGym.name}
              </Link>
            )}
          </p>
        </div>
      </div>
    </article>
  )
}
