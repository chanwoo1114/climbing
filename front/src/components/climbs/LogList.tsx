import { useEffect, useRef, type ReactNode } from 'react'
import type { InfiniteData, UseInfiniteQueryResult } from '@tanstack/react-query'

import type { ClimbLog } from '@/api/climbs'
import { getErrorMessage } from '@/api/client'
import type { CursorPage } from '@/api/gyms'
import LogCard from '@/components/climbs/LogCard'
import Button from '@/components/common/Button'

// useInfiniteQuery 의 data 는 TData 기본값(InfiniteData<T>, pageParam=unknown)으로 나온다.
// 훅이 initialPageParam 을 string | undefined 로 줘도 결과 타입엔 반영되지 않으니 기본값에 맞춘다.
type LogQuery = UseInfiniteQueryResult<InfiniteData<CursorPage<ClimbLog>>, Error>

interface Props {
  query: LogQuery
  /** 결과가 0건일 때 보여줄 빈 상태 UI */
  empty: ReactNode
  errorMessage: string
}

/**
 * 커서 기반 기록 목록 (프로필·내 기록). 피드(Feed.tsx)와 같은 방식:
 * 끝에 가까워지면 다음 페이지, 관찰자가 없는 환경은 "더 보기" 버튼이 대신한다.
 */
export default function LogList({ query, empty, errorMessage }: Props) {
  const logs = query.data?.pages.flatMap((page) => page.results) ?? []
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = query
  const sentinelRef = useRef<HTMLDivElement>(null)

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
    <div>
      {query.isPending && (
        <p role="status" className="py-10 text-center text-sm text-ink-400">
          기록을 불러오는 중…
        </p>
      )}

      {query.isError && (
        <div role="alert" className="py-10 text-center">
          <p className="text-sm text-pretty text-danger-500">
            {getErrorMessage(query.error, errorMessage)}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => query.refetch()}>
            다시 시도
          </Button>
        </div>
      )}

      {query.data && logs.length === 0 && empty}

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
