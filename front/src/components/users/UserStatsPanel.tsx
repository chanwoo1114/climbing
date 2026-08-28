import { Link } from 'react-router'

import { getErrorMessage } from '@/api/client'
import type { UserStats, UserStatsDifficulty, UserStatsMonth } from '@/api/users'
import Button from '@/components/common/Button'
import { useUserStats } from '@/hooks/useUsers'
import { formatMonth } from '@/lib/month'

const count = new Intl.NumberFormat('ko-KR')
const decimal = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 })
const percent = new Intl.NumberFormat('ko-KR', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const shortMonth = new Intl.DateTimeFormat('ko-KR', { month: 'short' })

/** 서버 success_rate(0~100) → "66.7%" */
export function formatRate(rate: number): string {
  return percent.format(rate / 100)
}

/** "2026-08" → 그 달 중순 정오 — 시간대와 무관하게 같은 달 */
function monthDate(month: string): Date {
  const [year, mon] = month.split('-').map(Number)
  return new Date(year, mon - 1, 15, 12)
}

const CARD = 'rounded-card border border-chalk-300 bg-white p-5'

interface Props {
  userId: number
}

/**
 * 프로필 통계 패널 — 요약 타일 + 월별 추이 + 난이도 분포 + 자주 간 암장.
 * 본인/타인(공개 기록만) 구분은 서버가 하므로 여기선 id 만 넘긴다.
 */
export default function UserStatsPanel({ userId }: Props) {
  const stats = useUserStats(userId)

  return (
    <section aria-labelledby="stats-heading" className="mt-6">
      <h2 id="stats-heading" className="mb-3 text-base font-semibold text-ink-700">
        통계
      </h2>

      {stats.isPending && <StatsSkeleton />}

      {stats.isError && (
        <div role="alert" className={`${CARD} text-center`}>
          <p className="text-sm text-pretty text-danger-500">
            {getErrorMessage(stats.error, '통계를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => stats.refetch()}>
            다시 시도
          </Button>
        </div>
      )}

      {stats.data &&
        (stats.data.totalCount === 0 ? (
          <div className={`${CARD} text-center`}>
            <p className="text-sm font-medium text-ink-600">아직 기록이 없어요</p>
            <p className="mt-1 text-xs text-pretty text-ink-400">
              기록이 쌓이면 성공률과 월별 추이가 여기에 나타나요.
            </p>
          </div>
        ) : (
          <StatsView stats={stats.data} />
        ))}
    </section>
  )
}

function StatsSkeleton() {
  return (
    <div role="status" aria-label="통계를 불러오는 중" className={CARD}>
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="h-14 animate-pulse rounded-xl bg-chalk-200" />
        ))}
      </div>
      <div className="mt-4 h-36 animate-pulse rounded-xl bg-chalk-200" />
    </div>
  )
}

function StatsView({ stats }: { stats: UserStats }) {
  const tiles: { label: string; value: string }[] = [
    { label: '총 기록', value: count.format(stats.totalCount) },
    { label: '완등', value: count.format(stats.successCount) },
    { label: '성공률', value: formatRate(stats.successRate) },
    { label: '방문 암장', value: count.format(stats.gymCount) },
    {
      label: '평균 시도',
      value: stats.avgAttempts === null ? '—' : decimal.format(stats.avgAttempts),
    },
  ]

  return (
    <div className="space-y-3">
      <div className={CARD}>
        <dl className="grid grid-cols-3 gap-3 sm:grid-cols-5">
          {tiles.map((tile) => (
            <div key={tile.label} className="rounded-xl bg-chalk-100 px-3 py-2.5">
              <dt className="text-xs text-ink-400">{tile.label}</dt>
              <dd className="mt-0.5 text-lg font-semibold text-ink-700 tabular-nums">
                {tile.value}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-sm text-ink-500">
          <span className="font-medium text-ink-600">{formatMonth(stats.thisMonth.month)}</span>{' '}
          기록{' '}
          <span className="font-semibold text-ink-700 tabular-nums">
            {count.format(stats.thisMonth.totalCount)}
          </span>
          <span aria-hidden> · </span>
          완등{' '}
          <span className="font-semibold text-ink-700 tabular-nums">
            {count.format(stats.thisMonth.successCount)}
          </span>
        </p>
      </div>

      <div className={CARD}>
        <h3 className="text-sm font-semibold text-ink-700">월별 추이</h3>
        <MonthChart months={stats.byMonth} />
      </div>

      {stats.byDifficulty.length > 0 && (
        <div className={CARD}>
          <h3 className="text-sm font-semibold text-ink-700">난이도 분포</h3>
          <DifficultyBars rows={stats.byDifficulty} />
        </div>
      )}

      {stats.topGyms.length > 0 && (
        <div className={CARD}>
          <h3 className="text-sm font-semibold text-ink-700">자주 간 암장</h3>
          <ol className="mt-1 divide-y divide-chalk-200">
            {stats.topGyms.map((item) => (
              <li key={item.gym.id}>
                <Link
                  to={`/gyms/${item.gym.id}`}
                  className="-mx-2 flex min-h-11 items-center justify-between gap-3 rounded-xl px-2 text-sm transition-colors duration-150 hover:bg-chalk-100"
                >
                  <span className="min-w-0 truncate font-medium text-ink-600">
                    {item.gym.name}
                  </span>
                  <span className="shrink-0 text-xs text-ink-400 tabular-nums">
                    기록 {count.format(item.totalCount)}
                    <span aria-hidden> · </span>완등 {count.format(item.successCount)}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}

// --- 월별 추이 (인라인 SVG, 차트 라이브러리 없음) ---

const CHART = {
  width: 360,
  height: 140,
  left: 28, // y 축 눈금 글자 자리
  right: 4,
  top: 8,
  bottom: 22, // 월 라벨 자리
  barWidth: 18, // <= 24px, 슬롯 나머지는 여백
  radius: 4, // 데이터 끝만 둥글게, 바닥은 각지게
} as const

/** 위만 둥근 막대 — 바닥(baseline)은 각지게 */
function barPath(x: number, y: number, width: number, height: number): string {
  if (height <= 0) return ''
  const r = Math.min(CHART.radius, height / 2, width / 2)
  const f = (n: number) => Math.round(n * 100) / 100
  const bottom = y + height
  return [
    `M${f(x)},${f(bottom)}`,
    `V${f(y + r)}`,
    `Q${f(x)},${f(y)} ${f(x + r)},${f(y)}`,
    `H${f(x + width - r)}`,
    `Q${f(x + width)},${f(y)} ${f(x + width)},${f(y + r)}`,
    `V${f(bottom)}`,
    'Z',
  ].join(' ')
}

function MonthChart({ months }: { months: UserStatsMonth[] }) {
  const plotWidth = CHART.width - CHART.left - CHART.right
  const plotHeight = CHART.height - CHART.top - CHART.bottom
  const baseline = CHART.top + plotHeight
  const slot = plotWidth / Math.max(months.length, 1)
  const max = Math.max(1, ...months.map((m) => m.totalCount))
  const scale = (value: number) => (value / max) * plotHeight

  const totalSum = months.reduce((sum, m) => sum + m.totalCount, 0)
  const successSum = months.reduce((sum, m) => sum + m.successCount, 0)
  const range =
    months.length > 0
      ? `${formatMonth(months[0].month)}부터 ${formatMonth(months[months.length - 1].month)}까지`
      : ''
  const summary = `${range} 월별 기록 추이. 총 기록 ${count.format(totalSum)}건, 완등 ${count.format(successSum)}건`

  return (
    <>
      {/* 두 시리즈라 범례 필수 — 색만으로 구분하지 않는다 */}
      <ul className="mt-2 flex gap-4 text-xs text-ink-500">
        <li className="inline-flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-sm bg-chalk-300" />
          기록
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-sm bg-hold-500" />
          완등
        </li>
      </ul>
      <svg
        role="img"
        aria-label={summary}
        viewBox={`0 0 ${CHART.width} ${CHART.height}`}
        className="mt-2 block h-auto w-full"
      >
        {/* 눈금: 0 과 최댓값만 — 나머지는 막대의 title 이 알려준다 */}
        <g className="fill-ink-400" fontSize={10} textAnchor="end">
          <text x={CHART.left - 6} y={CHART.top + 4}>
            {count.format(max)}
          </text>
          <text x={CHART.left - 6} y={baseline + 3}>
            0
          </text>
        </g>
        <line
          x1={CHART.left}
          x2={CHART.width - CHART.right}
          y1={CHART.top}
          y2={CHART.top}
          className="stroke-chalk-200"
          strokeWidth={1}
        />
        <line
          x1={CHART.left}
          x2={CHART.width - CHART.right}
          y1={baseline}
          y2={baseline}
          className="stroke-chalk-300"
          strokeWidth={1}
        />

        {months.map((m, i) => {
          const slotX = CHART.left + slot * i
          const x = slotX + (slot - CHART.barWidth) / 2
          const totalHeight = scale(m.totalCount)
          const successHeight = scale(m.successCount)
          const label = shortMonth.format(monthDate(m.month))
          return (
            <g key={m.month}>
              <title>{`${formatMonth(m.month)} 기록 ${count.format(m.totalCount)} · 완등 ${count.format(m.successCount)}`}</title>
              {/* 슬롯 전체가 hover/title 대상 — 막대보다 넓은 히트 영역 */}
              <rect
                x={slotX}
                y={CHART.top}
                width={slot}
                height={plotHeight}
                fill="transparent"
              />
              {totalHeight > 0 && (
                <path
                  d={barPath(x, baseline - totalHeight, CHART.barWidth, totalHeight)}
                  className="fill-chalk-300"
                />
              )}
              {successHeight > 0 && (
                <path
                  d={barPath(x, baseline - successHeight, CHART.barWidth, successHeight)}
                  className="fill-hold-500"
                />
              )}
              {i % 3 === 0 && (
                <text
                  x={slotX + slot / 2}
                  y={CHART.height - 6}
                  fontSize={10}
                  textAnchor="middle"
                  className="fill-ink-400"
                >
                  {label}
                </text>
              )}
            </g>
          )
        })}
      </svg>
    </>
  )
}

// --- 난이도 분포 (암장별 묶음, 가로 막대) ---

function DifficultyBars({ rows }: { rows: UserStatsDifficulty[] }) {
  // 서버 순서(암장 → 난이도 order)를 유지하면서 암장별로 묶는다
  const groups = new Map<number, { name: string; rows: UserStatsDifficulty[] }>()
  for (const row of rows) {
    const group = groups.get(row.gym.id) ?? { name: row.gym.name, rows: [] }
    group.rows.push(row)
    groups.set(row.gym.id, group)
  }
  const max = Math.max(1, ...rows.map((row) => row.totalCount))

  return (
    <div className="mt-2 space-y-4">
      {[...groups.entries()].map(([gymId, group]) => (
        <div key={gymId}>
          <h4 className="mb-1.5 truncate text-xs font-medium text-ink-500">{group.name}</h4>
          <ul className="space-y-1.5">
            {group.rows.map((row) => (
              <li
                key={row.difficulty.id}
                className="grid grid-cols-[minmax(0,5.5rem)_1fr_auto] items-center gap-2 text-sm"
              >
                <span className="inline-flex min-w-0 items-center gap-1.5">
                  {/* 난이도 색은 토큰이 아닌 DB 값 */}
                  <span
                    aria-hidden
                    data-testid="difficulty-dot"
                    className="size-2.5 shrink-0 rounded-full border border-chalk-400"
                    style={{ backgroundColor: row.difficulty.color }}
                  />
                  <span className="min-w-0 truncate text-ink-600">{row.difficulty.name}</span>
                </span>
                <span
                  aria-hidden
                  className="block h-2 overflow-hidden rounded-full bg-chalk-300"
                  style={{ width: `${(row.totalCount / max) * 100}%` }}
                >
                  <span
                    className="block h-full rounded-full bg-hold-500"
                    style={{
                      width: `${row.totalCount > 0 ? (row.successCount / row.totalCount) * 100 : 0}%`,
                    }}
                  />
                </span>
                <span className="text-xs text-ink-400 tabular-nums">
                  {count.format(row.successCount)}/{count.format(row.totalCount)} (
                  {formatRate(row.successRate)})
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
