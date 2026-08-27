import { Link, useNavigate, useSearchParams } from 'react-router'

import LogList from '@/components/climbs/LogList'
import Button from '@/components/common/Button'
import { useMyLogs } from '@/hooks/useClimbs'

type Filter = 'all' | 'success' | 'fail'

const FILTERS: { value: Filter; label: string; to: string }[] = [
  { value: 'all', label: '전체', to: '/logs' },
  { value: 'success', label: '성공', to: '/logs?is_success=true' },
  { value: 'fail', label: '실패', to: '/logs?is_success=false' },
]

/** ?is_success= 가 없거나 이상하면 전체 */
function filterFromParams(params: URLSearchParams): Filter {
  const value = params.get('is_success')
  if (value === 'true') return 'success'
  if (value === 'false') return 'fail'
  return 'all'
}

export default function MyLogs() {
  const [searchParams] = useSearchParams()
  const filter = filterFromParams(searchParams)
  const logs = useMyLogs(filter === 'all' ? {} : { isSuccess: filter === 'success' })

  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-ink-700">내 기록</h1>
        {/* 필터 상태는 URL(?is_success=)에 산다 — 새로고침·공유해도 같은 필터 */}
        <nav aria-label="결과 필터" className="inline-flex rounded-xl bg-chalk-200 p-1">
          {FILTERS.map((item) => {
            const active = item.value === filter
            return (
              <Link
                key={item.value}
                to={item.to}
                replace
                aria-current={active ? 'page' : undefined}
                className={`inline-flex min-h-11 items-center rounded-lg px-3 text-sm transition-colors duration-150 sm:px-4 ${
                  active
                    ? 'bg-white font-semibold text-ink-700'
                    : 'font-medium text-ink-500 hover:text-ink-700'
                }`}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>
      </div>

      <LogList
        query={logs}
        errorMessage="기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
        empty={<EmptyLogs filter={filter} />}
      />
    </div>
  )
}

function EmptyLogs({ filter }: { filter: Filter }) {
  const navigate = useNavigate()
  if (filter !== 'all') {
    return (
      <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
        <p className="text-sm font-medium text-ink-600">
          {filter === 'success' ? '성공한 기록이 없어요' : '실패한 기록이 없어요'}
        </p>
        <Link
          to="/logs"
          replace
          className="mt-3 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
        >
          전체 기록 보기
        </Link>
      </div>
    )
  }
  return (
    <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
      <p className="text-sm font-medium text-ink-600">아직 기록이 없어요</p>
      <p className="mt-1 text-xs text-pretty text-ink-400">
        오늘 등반을 기록하면 여기에 쌓여요.
      </p>
      {/* 이 페이지의 유일한 primary CTA */}
      <Button className="mt-4" onClick={() => navigate('/logs/new')}>
        첫 기록 남기기
      </Button>
    </div>
  )
}
