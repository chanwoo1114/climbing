import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { getErrorMessage } from '@/api/client'
import type { CrewListParams } from '@/api/crews'
import Button from '@/components/common/Button'
import TextField from '@/components/common/TextField'
import CrewCard from '@/components/crews/CrewCard'
import { useCrews } from '@/hooks/useCrews'
import { useGym } from '@/hooks/useGyms'
import { useInfiniteSentinel } from '@/hooks/useInfiniteSentinel'

const DEBOUNCE_MS = 300

/** ?gym= 은 양의 정수일 때만 필터로 쓴다 */
function gymFromParams(params: URLSearchParams): number | null {
  const value = Number(params.get('gym'))
  return Number.isInteger(value) && value > 0 ? value : null
}

/** 검색어·암장 필터 상태는 URL 에 산다 — 새로고침·공유해도 같은 화면 */
function searchFor(q: string, gym: number | null): string {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (gym !== null) params.set('gym', String(gym))
  const query = params.toString()
  return query ? `?${query}` : ''
}

export default function CrewList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const q = searchParams.get('q')?.trim() ?? ''
  const gymId = gymFromParams(searchParams)
  const [input, setInput] = useState(q)

  // 입력 → URL (디바운스). 암장 필터는 그대로 둔다
  useEffect(() => {
    const next = input.trim()
    if (next === q) return
    const timer = setTimeout(() => {
      setSearchParams(searchFor(next, gymId), { replace: true })
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [input, q, gymId, setSearchParams])

  // URL → 입력 (뒤로가기 등으로 바깥에서 바뀐 경우만)
  useEffect(() => {
    setInput((current) => (current.trim() === q ? current : q))
  }, [q])

  const params: CrewListParams = {
    ...(q ? { q } : {}),
    ...(gymId !== null ? { gym: gymId } : {}),
  }
  const crews = useCrews(params)
  const items = crews.data?.pages.flatMap((page) => page.results) ?? []
  // 필터 칩에 보여줄 암장 이름 — 암장 상세는 공개 API 라 목록이 비어도 이름을 알 수 있다
  const gym = useGym(gymId ?? NaN)
  const sentinelRef = useInfiniteSentinel(crews)
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = crews

  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-ink-700">크루</h1>
        {/* 이 페이지의 유일한 primary CTA */}
        <Button onClick={() => navigate('/crews/new')}>크루 만들기</Button>
      </div>

      <form role="search" onSubmit={(e) => e.preventDefault()} noValidate>
        <TextField
          label="크루 이름"
          name="q"
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="크루 이름으로 찾기"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
      </form>

      {gymId !== null && (
        <div className="mt-3">
          <Link
            to={`/crews${searchFor(q, null)}`}
            replace
            aria-label={`${gym.data?.name ?? '암장'} 필터 해제`}
            className="inline-flex min-h-11 max-w-full items-center gap-1.5 rounded-xl border border-chalk-300 bg-white px-3 text-sm font-medium text-ink-600 transition-colors duration-150 hover:bg-chalk-100"
          >
            <span className="min-w-0 truncate">
              <span className="sr-only">홈짐 </span>
              {gym.data?.name ?? `암장 #${gymId}`}
            </span>
            <span aria-hidden className="text-ink-400">
              ✕
            </span>
          </Link>
        </div>
      )}

      <div className="mt-4">
        {crews.isPending && (
          <p role="status" className="py-10 text-center text-sm text-ink-400">
            크루를 불러오는 중…
          </p>
        )}

        {crews.isError && (
          <div role="alert" className="py-10 text-center">
            <p className="text-sm text-pretty text-danger-500">
              {getErrorMessage(crews.error, '크루를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
            </p>
            <Button variant="secondary" className="mt-3" onClick={() => crews.refetch()}>
              다시 시도
            </Button>
          </div>
        )}

        {crews.data && items.length === 0 && (
          <EmptyCrews q={q} filteredByGym={gymId !== null} />
        )}

        {items.length > 0 && (
          <ul className="space-y-3">
            {items.map((crew) => (
              <li key={crew.id}>
                <CrewCard crew={crew} />
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
            다음 크루를 불러오는 중
          </p>
        )}
      </div>
    </div>
  )
}

function EmptyCrews({ q, filteredByGym }: { q: string; filteredByGym: boolean }) {
  if (q) {
    return (
      <div role="status" className="rounded-card border border-chalk-300 bg-white p-8 text-center">
        <p className="text-sm font-medium text-pretty break-words text-ink-600">
          '{q}'에 해당하는 크루가 없어요
        </p>
        <p className="mt-1 text-xs text-pretty text-ink-400">
          다른 이름으로 찾아보거나 직접 만들어보세요.
        </p>
        <Link
          to="/crews/new"
          className="mt-3 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
        >
          이 이름으로 크루 만들기
        </Link>
      </div>
    )
  }
  return (
    <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
      <p className="text-sm font-medium text-ink-600">
        {filteredByGym ? '이 암장을 홈으로 하는 크루가 아직 없어요' : '아직 크루가 없어요'}
      </p>
      <p className="mt-1 text-xs text-pretty text-ink-400">
        같이 오를 사람들을 모아 첫 크루를 만들어보세요.
      </p>
      <div className="mt-3 flex flex-wrap justify-center gap-1">
        <Link
          to="/crews/new"
          className="inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
        >
          크루 만들기
        </Link>
        {filteredByGym && (
          <Link
            to="/crews"
            replace
            className="inline-flex min-h-11 items-center px-3 text-sm font-medium text-ink-500 hover:text-ink-700"
          >
            전체 크루 보기
          </Link>
        )}
      </div>
    </div>
  )
}
