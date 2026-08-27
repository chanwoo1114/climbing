import { useEffect, useRef } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { getErrorMessage } from '@/api/client'
import type { PostCategory, PostListParams } from '@/api/posts'
import Button from '@/components/common/Button'
import PostCard from '@/components/community/PostCard'
import { useGym } from '@/hooks/useGyms'
import { usePosts } from '@/hooks/usePosts'

type Tab = 'all' | PostCategory

const TABS: { value: Tab; label: string }[] = [
  { value: 'all', label: '전체' },
  { value: 'free', label: '자유' },
  { value: 'recruit', label: '모집' },
]

/** ?category= 가 없거나 이상하면 전체 */
function tabFromParams(params: URLSearchParams): Tab {
  const value = params.get('category')
  return value === 'free' || value === 'recruit' ? value : 'all'
}

/** ?gym= 은 양의 정수일 때만 필터로 쓴다 */
function gymFromParams(params: URLSearchParams): number | null {
  const value = Number(params.get('gym'))
  return Number.isInteger(value) && value > 0 ? value : null
}

/** 탭·암장 필터 상태는 URL 에 산다 — 새로고침·공유해도 같은 화면 */
function searchFor(tab: Tab, gym: number | null): string {
  const params = new URLSearchParams()
  if (tab !== 'all') params.set('category', tab)
  if (gym !== null) params.set('gym', String(gym))
  const query = params.toString()
  return query ? `?${query}` : ''
}

export default function PostList() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const tab = tabFromParams(searchParams)
  const gymId = gymFromParams(searchParams)

  const params: PostListParams = {
    ...(tab !== 'all' ? { category: tab } : {}),
    ...(gymId !== null ? { gym: gymId } : {}),
  }
  const posts = usePosts(params)
  const items = posts.data?.pages.flatMap((page) => page.results) ?? []
  // 필터 칩에 보여줄 암장 이름 — 암장 상세는 공개 API 라 목록이 비어도 이름을 알 수 있다
  const gym = useGym(gymId ?? NaN)

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = posts
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

  // 모집 탭에서 글쓰기를 누르면 모집글 폼으로, 암장 필터 중이면 그 암장이 기본 선택된다
  const createPath = `/posts/new${searchFor(tab, gymId)}`

  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-ink-700">게시판</h1>
        {/* 이 페이지의 유일한 primary CTA */}
        <Button onClick={() => navigate(createPath)}>글쓰기</Button>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <nav aria-label="게시글 종류" className="inline-flex rounded-xl bg-chalk-200 p-1">
          {TABS.map((item) => {
            const active = item.value === tab
            return (
              <Link
                key={item.value}
                to={`/posts${searchFor(item.value, gymId)}`}
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

        {gymId !== null && (
          <Link
            to={`/posts${searchFor(tab, null)}`}
            replace
            aria-label={`${gym.data?.name ?? '암장'} 필터 해제`}
            className="inline-flex min-h-11 max-w-full items-center gap-1.5 rounded-xl border border-chalk-300 bg-white px-3 text-sm font-medium text-ink-600 transition-colors duration-150 hover:bg-chalk-100"
          >
            <span className="min-w-0 truncate">{gym.data?.name ?? `암장 #${gymId}`}</span>
            <span aria-hidden className="text-ink-400">
              ✕
            </span>
          </Link>
        )}
      </div>

      {posts.isPending && (
        <p role="status" className="py-10 text-center text-sm text-ink-400">
          게시글을 불러오는 중…
        </p>
      )}

      {posts.isError && (
        <div role="alert" className="py-10 text-center">
          <p className="text-sm text-danger-500">
            {getErrorMessage(posts.error, '게시글을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => posts.refetch()}>
            다시 시도
          </Button>
        </div>
      )}

      {posts.data && items.length === 0 && (
        <EmptyPosts tab={tab} filteredByGym={gymId !== null} createPath={createPath} />
      )}

      {items.length > 0 && (
        <ul className="space-y-3">
          {items.map((post) => (
            <li key={post.id}>
              <PostCard post={post} />
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
          다음 게시글을 불러오는 중
        </p>
      )}
    </div>
  )
}

const EMPTY: Record<Tab, { title: string; hint: string; action: string }> = {
  all: { title: '아직 게시글이 없어요', hint: '첫 글을 남겨보세요.', action: '글쓰기' },
  free: { title: '자유 게시글이 아직 없어요', hint: '궁금한 것, 나누고 싶은 이야기를 적어보세요.', action: '글쓰기' },
  recruit: {
    title: '모집 중인 투어가 없어요',
    hint: '같이 갈 사람을 직접 모아보세요.',
    action: '모집글 쓰기',
  },
}

function EmptyPosts({
  tab,
  filteredByGym,
  createPath,
}: {
  tab: Tab
  filteredByGym: boolean
  createPath: string
}) {
  const copy = EMPTY[tab]
  return (
    <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
      <p className="text-sm font-medium text-ink-600">
        {filteredByGym ? '이 암장 관련 글이 아직 없어요' : copy.title}
      </p>
      <p className="mt-1 text-xs text-pretty text-ink-400">{copy.hint}</p>
      <div className="mt-3 flex flex-wrap justify-center gap-1">
        <Link
          to={createPath}
          className="inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
        >
          {copy.action}
        </Link>
        {filteredByGym && (
          <Link
            to={`/posts${searchFor(tab, null)}`}
            replace
            className="inline-flex min-h-11 items-center px-3 text-sm font-medium text-ink-500 hover:text-ink-700"
          >
            전체 글 보기
          </Link>
        )}
      </div>
    </div>
  )
}
