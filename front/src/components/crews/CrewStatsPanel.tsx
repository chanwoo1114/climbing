import { Link, useSearchParams } from 'react-router'

import { getErrorCode, getErrorMessage } from '@/api/client'
import type { Crew, CrewMemberRank } from '@/api/crews'
import Avatar from '@/components/common/Avatar'
import Button from '@/components/common/Button'
import { RankBadge, count, percent } from '@/components/crews/CrewBits'
import MonthPicker from '@/components/crews/MonthPicker'
import { useCrewStats } from '@/hooks/useCrews'
import { formatMonth, monthFromParams } from '@/lib/month'

/** 크루 상세의 "통계" 탭 — 월 선택은 ?month= 에, 탭은 ?tab=stats 에 산다 */
export default function CrewStatsPanel({ crew, myId }: { crew: Crew; myId: number | null }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const month = monthFromParams(searchParams)
  const stats = useCrewStats(crew.id, month)

  const setMonth = (next: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('tab', 'stats')
    params.set('month', next)
    setSearchParams(params, { replace: true })
  }

  const forbidden =
    stats.isError &&
    (getErrorCode(stats.error) === 'permission_denied' || getErrorCode(stats.error) === 'http_403')

  return (
    <section aria-labelledby="stats-heading" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="stats-heading" className="text-base font-semibold text-ink-700">
          {formatMonth(month)} 활동
        </h2>
        <MonthPicker month={month} onChange={setMonth} />
      </div>

      {forbidden ? (
        <div role="alert" className="rounded-card border border-chalk-300 bg-white p-8 text-center">
          <p className="text-sm font-medium text-ink-600">크루원만 볼 수 있어요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">
            {crew.myStatus === 'pending'
              ? '승인되면 크루의 월간 통계를 볼 수 있어요.'
              : '가입하면 크루원들의 완등·기록 통계를 볼 수 있어요.'}
          </p>
        </div>
      ) : stats.isPending ? (
        <StatsSkeleton />
      ) : stats.isError ? (
        <div role="alert" className="py-10 text-center">
          <p className="text-sm text-pretty text-danger-500">
            {getErrorMessage(stats.error, '통계를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => stats.refetch()}>
            다시 시도
          </Button>
        </div>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5">
            <StatTile label="완등" value={count.format(stats.data.successCount)} accent />
            <StatTile label="기록" value={count.format(stats.data.logCount)} />
            <StatTile label="성공률" value={`${percent.format(stats.data.successRate)}%`} />
            <StatTile
              label="활동 크루원"
              value={count.format(stats.data.activeMemberCount)}
              suffix={`/ ${count.format(stats.data.memberCount)}`}
            />
            <StatTile label="암장 수" value={count.format(stats.data.gymCount)} />
          </dl>

          <MemberRanking ranking={stats.data.ranking} myId={myId} />
        </>
      )}
    </section>
  )
}

function StatTile({
  label,
  value,
  suffix,
  accent = false,
}: {
  label: string
  value: string
  suffix?: string
  accent?: boolean
}) {
  return (
    <div className="rounded-card border border-chalk-300 bg-white px-3 py-3">
      <dt className="text-xs text-ink-400">{label}</dt>
      <dd
        className={`mt-1 text-xl font-semibold tabular-nums ${accent ? 'text-hold-600' : 'text-ink-700'}`}
      >
        {value}
        {suffix && <span className="ml-1 text-sm font-medium text-ink-400">{suffix}</span>}
      </dd>
    </div>
  )
}

function MemberRanking({ ranking, myId }: { ranking: CrewMemberRank[]; myId: number | null }) {
  return (
    <section
      aria-labelledby="member-ranking-heading"
      className="rounded-card border border-chalk-300 bg-white p-4 md:p-5"
    >
      <h3 id="member-ranking-heading" className="text-base font-semibold text-ink-700">
        크루원 랭킹{' '}
        <span className="text-xs font-normal text-ink-400">완등 수 순 · 상위 10명</span>
      </h3>

      {ranking.length === 0 ? (
        <div role="status" className="py-6 text-center">
          <p className="text-sm font-medium text-ink-600">이 달 기록이 없어요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">
            크루원이 공개로 남긴 등반 기록이 있으면 여기에 순위가 매겨져요.
          </p>
        </div>
      ) : (
        <ol className="mt-2 divide-y divide-chalk-200">
          {ranking.map((row) => {
            const isMe = row.user.id === myId
            return (
              <li
                key={row.user.id}
                aria-current={isMe ? 'true' : undefined}
                className={`flex items-center gap-3 py-2 ${isMe ? '-mx-2 rounded-xl bg-chalk-100 px-2' : ''}`}
              >
                <RankBadge rank={row.rank} />
                <Link
                  to={`/users/${row.user.id}`}
                  tabIndex={-1}
                  className="-m-1.5 shrink-0 rounded-full p-1.5"
                >
                  <Avatar user={row.user} size="sm" />
                </Link>
                <p className="flex min-w-0 flex-1 items-center gap-2 text-sm font-medium text-ink-700">
                  <Link to={`/users/${row.user.id}`} className="min-w-0 truncate hover:underline">
                    {row.user.nickname}
                  </Link>
                  {isMe && <span className="shrink-0 text-xs font-normal text-ink-400">나</span>}
                </p>
                <p className="shrink-0 text-xs text-ink-400 tabular-nums">
                  완등 <span className="font-semibold text-ink-700">{count.format(row.successCount)}</span>
                  <span aria-hidden className="mx-1.5">
                    ·
                  </span>
                  기록 <span className="font-medium text-ink-600">{count.format(row.logCount)}</span>
                </p>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}

/** 자리 잡기용 — 타일 5개 + 랭킹 줄 3개. 깜빡임은 opacity 만 (animate-pulse) */
function StatsSkeleton() {
  return (
    <div role="status" aria-live="polite" className="space-y-4">
      <span className="sr-only">통계를 불러오는 중…</span>
      <div aria-hidden className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="rounded-card border border-chalk-300 bg-white px-3 py-3">
            <div className="h-3 w-12 animate-pulse rounded bg-chalk-200" />
            <div className="mt-2 h-6 w-16 animate-pulse rounded bg-chalk-200" />
          </div>
        ))}
      </div>
      <div aria-hidden className="rounded-card border border-chalk-300 bg-white p-4 md:p-5">
        <div className="h-4 w-24 animate-pulse rounded bg-chalk-200" />
        <ul className="mt-3 divide-y divide-chalk-200">
          {Array.from({ length: 3 }, (_, i) => (
            <li key={i} className="flex items-center gap-3 py-2">
              <div className="size-7 animate-pulse rounded-lg bg-chalk-200" />
              <div className="size-8 animate-pulse rounded-full bg-chalk-200" />
              <div className="h-4 flex-1 animate-pulse rounded bg-chalk-200" />
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
