import type { ReactNode } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'

import type { BetaListParams } from '@/api/betas'
import { getErrorMessage } from '@/api/client'
import type { GymDetail } from '@/api/gyms'
import BetaCard from '@/components/betas/BetaCard'
import Button from '@/components/common/Button'
import { useBetaSectors, useGymBetas } from '@/hooks/useBetas'
import { useInfiniteSentinel } from '@/hooks/useInfiniteSentinel'
import { useAuthStore } from '@/stores/authStore'

const count = new Intl.NumberFormat('ko-KR')

// 필터 칩 — 링크라서 새로고침·공유해도 같은 필터. 텍스트가 작아도 44px 터치 영역
const CHIP =
  'inline-flex min-h-11 max-w-full items-center gap-1.5 rounded-xl border px-3 text-sm transition-colors duration-150'
const CHIP_IDLE = 'border-chalk-300 bg-white text-ink-600 hover:bg-chalk-100'
const CHIP_ACTIVE = 'border-ink-500 bg-chalk-200 font-medium text-ink-700'

/** ?sector= / ?difficulty= 를 읽는다. difficulty 는 이 암장의 난이도 id 일 때만 인정 */
function paramsFrom(searchParams: URLSearchParams, gym: GymDetail): BetaListParams {
  const sector = searchParams.get('sector')?.trim() ?? ''
  const difficultyId = Number(searchParams.get('difficulty'))
  const difficulty = gym.difficulties.some((d) => d.id === difficultyId) ? difficultyId : undefined
  return { ...(sector ? { sector } : {}), ...(difficulty ? { difficulty } : {}) }
}

/**
 * 암장 상세의 "베타" 탭 — 섹터·난이도 칩으로 거르고 격자로 보여준다.
 * 읽기는 공개라 로그인 없이도 목록이 뜨고, "베타 올리기"만 로그인으로 보낸다.
 */
export default function GymBetas({ gym }: { gym: GymDetail }) {
  const [searchParams] = useSearchParams()
  const params = paramsFrom(searchParams, gym)
  const betas = useGymBetas(gym.id, params)
  const sectors = useBetaSectors(gym.id)
  const loaded = betas.data?.pages.flatMap((page) => page.results) ?? []
  const sentinelRef = useInfiniteSentinel(betas)
  const difficulties = [...gym.difficulties].sort((a, b) => a.order - b.order)

  /** 현재 탭·필터를 유지한 채 하나만 바꾼 링크 */
  const filterLink = (key: 'sector' | 'difficulty', value: string | null) => {
    const next = new URLSearchParams(searchParams)
    next.set('tab', 'betas')
    if (value === null) next.delete(key)
    else next.set(key, value)
    return `/gyms/${gym.id}?${next}`
  }

  return (
    <section aria-labelledby="betas-heading" className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 id="betas-heading" className="text-base font-semibold text-ink-700">
          베타 영상
        </h2>
        <UploadButton gymId={gym.id} />
      </div>

      {sectors.data && sectors.data.length > 0 && (
        <FilterRow label="섹터">
          <FilterChip to={filterLink('sector', null)} active={!params.sector}>
            전체
          </FilterChip>
          {sectors.data.map((item) => (
            <FilterChip
              key={item.sector}
              to={filterLink('sector', item.sector)}
              active={params.sector?.toLowerCase() === item.sector.toLowerCase()}
            >
              <span className="truncate">{item.sector}</span>
              <span className="text-xs text-ink-400 tabular-nums">{count.format(item.count)}</span>
            </FilterChip>
          ))}
        </FilterRow>
      )}

      {difficulties.length > 0 && (
        <FilterRow label="난이도">
          <FilterChip to={filterLink('difficulty', null)} active={params.difficulty === undefined}>
            전체
          </FilterChip>
          {difficulties.map((difficulty) => (
            <FilterChip
              key={difficulty.id}
              to={filterLink('difficulty', String(difficulty.id))}
              active={params.difficulty === difficulty.id}
            >
              {/* 색은 토큰이 아니라 암장이 정한 값 */}
              <span
                aria-hidden
                className="size-3 shrink-0 rounded-full border border-chalk-400"
                style={{ backgroundColor: difficulty.color }}
              />
              {difficulty.name}
            </FilterChip>
          ))}
        </FilterRow>
      )}

      {betas.isPending && (
        <p role="status" className="py-10 text-center text-sm text-ink-400">
          베타 영상을 불러오는 중…
        </p>
      )}
      {betas.isError && (
        <p role="alert" className="py-10 text-center text-sm text-danger-500">
          {getErrorMessage(betas.error, '베타 영상을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
      )}
      {betas.data && loaded.length === 0 && (
        <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
          <p className="text-sm font-medium text-ink-600">아직 베타 영상이 없어요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">
            {params.sector || params.difficulty
              ? '다른 섹터나 난이도를 골라 보세요.'
              : '첫 베타를 올려 문제 풀이를 나눠 보세요.'}
          </p>
        </div>
      )}
      {loaded.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {loaded.map((beta) => (
            <li key={beta.id}>
              <BetaCard beta={beta} />
            </li>
          ))}
        </ul>
      )}

      <div ref={sentinelRef} aria-hidden />
      {betas.hasNextPage && (
        <Button
          variant="secondary"
          full
          onClick={() => betas.fetchNextPage()}
          disabled={betas.isFetchingNextPage}
        >
          {betas.isFetchingNextPage ? '불러오는 중…' : '더 보기'}
        </Button>
      )}
    </section>
  )
}

function FilterRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-full text-xs font-medium text-ink-400 sm:w-auto">{label}</span>
      {children}
    </div>
  )
}

function FilterChip({
  to,
  active,
  children,
}: {
  to: string
  active: boolean
  children: ReactNode
}) {
  return (
    <Link
      to={to}
      replace
      aria-current={active ? 'true' : undefined}
      className={`${CHIP} ${active ? CHIP_ACTIVE : CHIP_IDLE}`}
    >
      {children}
    </Link>
  )
}

/** 이 탭의 유일한 primary CTA. 비로그인이면 로그인으로 보내고, 로그인 후 이 페이지로 돌아온다 */
function UploadButton({ gymId }: { gymId: number }) {
  const status = useAuthStore((s) => s.status)
  const navigate = useNavigate()
  const location = useLocation()
  const target = `/gyms/${gymId}/betas/new`

  const onClick = () => {
    if (status === 'authenticated') navigate(target)
    else navigate('/login', { state: { from: location.pathname + location.search } })
  }

  return (
    <Button onClick={onClick} disabled={status === 'booting'}>
      베타 올리기
    </Button>
  )
}
