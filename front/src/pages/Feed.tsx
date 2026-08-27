import { useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { FeedScope } from '@/api/climbs'
import { getErrorMessage } from '@/api/client'
import LogCard from '@/components/climbs/LogCard'
import Button from '@/components/common/Button'
import { useFeed } from '@/hooks/useClimbs'

const TABS: { scope: FeedScope; label: string; to: string }[] = [
  { scope: 'explore', label: '탐색', to: '/feed' },
  { scope: 'following', label: '팔로잉', to: '/feed?scope=following' },
]

/** ?scope= 가 없거나 이상하면 탐색 */
function scopeFromParams(params: URLSearchParams): FeedScope {
  return params.get('scope') === 'following' ? 'following' : 'explore'
}

export default function Feed() {
  const [searchParams] = useSearchParams()
  const scope = scopeFromParams(searchParams)
  const feed = useFeed(scope)
  const logs = feed.data?.pages.flatMap((page) => page.results) ?? []

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = feed
  const sentinelRef = useRef<HTMLDivElement>(null)

  // 끝에 가까워지면 다음 페이지 — 관찰자가 없는 환경은 아래 "더 보기" 버튼이 대신한다
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel || !hasNextPage || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting) && !isFetchingNextPage) {
          fetchNextPage()
        }
      },
      { rootMargin: '400px 0px' },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-ink-700">피드</h1>
        {/* 탭 상태는 URL(?scope=)에 산다 — 새로고침·공유해도 같은 탭 */}
        <nav aria-label="피드 범위" className="inline-flex rounded-xl bg-chalk-200 p-1">
          {TABS.map((tab) => {
            const active = tab.scope === scope
            return (
              <Link
                key={tab.scope}
                to={tab.to}
                replace
                aria-current={active ? 'page' : undefined}
                className={`inline-flex min-h-11 items-center rounded-lg px-4 text-sm transition-colors duration-150 ${
                  active
                    ? 'bg-white font-semibold text-ink-700'
                    : 'font-medium text-ink-500 hover:text-ink-700'
                }`}
              >
                {tab.label}
              </Link>
            )
          })}
        </nav>
      </div>

      {feed.isPending && (
        <p role="status" className="py-10 text-center text-sm text-ink-400">
          기록을 불러오는 중…
        </p>
      )}

      {feed.isError && (
        <div role="alert" className="py-10 text-center">
          <p className="text-sm text-danger-500">
            {getErrorMessage(feed.error, '피드를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => feed.refetch()}>
            다시 시도
          </Button>
        </div>
      )}

      {feed.data && logs.length === 0 && <EmptyFeed scope={scope} />}

      {logs.length > 0 && (
        <ul className="space-y-3">
          {logs.map((log) => (
            <li key={log.id}>
              <LogCard log={log} />
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
          다음 기록을 불러오는 중
        </p>
      )}
    </div>
  )
}

function EmptyFeed({ scope }: { scope: FeedScope }) {
  if (scope === 'following') {
    return (
      <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
        <p className="text-sm font-medium text-ink-600">팔로우한 사람의 기록이 아직 없어요</p>
        <p className="mt-1 text-xs text-pretty text-ink-400">
          탐색 탭에서 다른 클라이머의 기록을 둘러보세요.
        </p>
        <Link
          to="/feed"
          replace
          className="mt-3 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
        >
          탐색 탭으로
        </Link>
      </div>
    )
  }
  return (
    <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
      <p className="text-sm font-medium text-ink-600">아직 공개된 기록이 없어요</p>
      <p className="mt-1 text-xs text-pretty text-ink-400">첫 등반 기록을 남겨보세요.</p>
      <Link
        to="/logs/new"
        className="mt-3 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
      >
        기록하기
      </Link>
    </div>
  )
}
