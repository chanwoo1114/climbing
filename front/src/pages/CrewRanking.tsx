import { Link, useSearchParams } from 'react-router'

import { getErrorMessage } from '@/api/client'
import type { CrewRank } from '@/api/crews'
import Button from '@/components/common/Button'
import { CrewImage, RankBadge, count } from '@/components/crews/CrewBits'
import MonthPicker from '@/components/crews/MonthPicker'
import { useCrewRanking } from '@/hooks/useCrews'
import { formatMonth, monthFromParams } from '@/lib/month'

/** 이달의 크루 랭킹 — 그 달 활동 중 크루원들의 공개 완등 수 순. 월은 ?month= 에 산다 */
export default function CrewRanking() {
  const [searchParams, setSearchParams] = useSearchParams()
  const month = monthFromParams(searchParams)
  const ranking = useCrewRanking(month)

  const setMonth = (next: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('month', next)
    setSearchParams(params, { replace: true })
  }

  return (
    <div className="mx-auto max-w-xl">
      <Link
        to="/crews"
        className="-ml-2 inline-flex min-h-11 items-center px-2 text-sm font-medium text-ink-500 hover:text-ink-700"
      >
        <span aria-hidden className="mr-1">
          ←
        </span>
        크루
      </Link>

      <div className="mt-2 mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink-700">크루 랭킹</h1>
          <p className="mt-0.5 text-sm text-pretty text-ink-400">
            {formatMonth(month)} 크루원들이 공개로 남긴 완등 수 순이에요.
          </p>
        </div>
        <MonthPicker month={month} onChange={setMonth} />
      </div>

      {ranking.isPending && (
        <p role="status" className="py-10 text-center text-sm text-ink-400">
          랭킹을 불러오는 중…
        </p>
      )}

      {ranking.isError && (
        <div role="alert" className="py-10 text-center">
          <p className="text-sm text-pretty text-danger-500">
            {getErrorMessage(ranking.error, '랭킹을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => ranking.refetch()}>
            다시 시도
          </Button>
        </div>
      )}

      {ranking.data && ranking.data.length === 0 && (
        <div role="status" className="rounded-card border border-chalk-300 bg-white p-8 text-center">
          <p className="text-sm font-medium text-ink-600">이 달 기록이 있는 크루가 없어요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">
            크루원이 공개로 남긴 완등 기록이 쌓이면 순위가 매겨져요.
          </p>
          <Link
            to="/crews"
            className="mt-3 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
          >
            크루 둘러보기
          </Link>
        </div>
      )}

      {ranking.data && ranking.data.length > 0 && (
        <ol aria-label={`${formatMonth(month)} 크루 랭킹`} className="space-y-2">
          {ranking.data.map((row) => (
            <li key={row.crew.id}>
              <RankedCrewCard row={row} />
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function RankedCrewCard({ row }: { row: CrewRank }) {
  const { crew } = row
  const top = row.rank <= 3
  const detailPath = `/crews/${crew.id}`
  return (
    <article
      aria-labelledby={`rank-crew-${crew.id}`}
      // 상위 3개는 보더만 진하게 — 그라데이션·그림자 없이 플랫하게
      className={`flex items-center gap-3 rounded-card border bg-white p-4 ${
        top ? 'border-ochre-400' : 'border-chalk-300'
      }`}
    >
      <RankBadge rank={row.rank} />
      <Link to={detailPath} tabIndex={-1} className="shrink-0 rounded-xl">
        <CrewImage crew={{ name: crew.name, image: crew.image ?? '' }} size="sm" />
      </Link>
      <div className="min-w-0 flex-1">
        <h2 id={`rank-crew-${crew.id}`} className="min-w-0 truncate text-base text-ink-700">
          <Link to={detailPath} className={`hover:underline ${top ? 'font-semibold' : 'font-medium'}`}>
            {crew.name}
          </Link>
        </h2>
        <p className="mt-0.5 flex min-w-0 flex-wrap items-center gap-x-2 text-xs text-ink-400">
          {crew.homeGym && <span className="min-w-0 truncate text-hold-600">{crew.homeGym.name}</span>}
          <span className="tabular-nums">크루원 {count.format(row.memberCount)}명</span>
        </p>
      </div>
      <dl className="flex shrink-0 gap-3 text-right tabular-nums">
        <div>
          <dt className="text-[11px] text-ink-400">완등</dt>
          <dd className="text-base font-semibold text-ink-700">{count.format(row.successCount)}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-ink-400">기록</dt>
          <dd className="text-base font-medium text-ink-600">{count.format(row.logCount)}</dd>
        </div>
      </dl>
    </article>
  )
}
