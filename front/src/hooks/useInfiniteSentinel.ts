import { useEffect, useRef } from 'react'

interface InfiniteLike {
  hasNextPage: boolean
  isFetchingNextPage: boolean
  fetchNextPage: () => unknown
}

/**
 * 커서 목록의 끝에 가까워지면 다음 페이지를 받는다 (Feed/PostList 와 같은 규칙).
 * 돌려준 ref 를 목록 아래 빈 div 에 붙인다. 관찰자가 없는 환경은 "더 보기" 버튼이 대신한다.
 */
export function useInfiniteSentinel({
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
}: InfiniteLike) {
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

  return sentinelRef
}
