import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type Query,
  type QueryClient,
} from '@tanstack/react-query'

import type { Me } from '@/api/auth'
import {
  fetchFollowers,
  fetchFollowing,
  fetchUser,
  fetchUserLogs,
  followUser,
  searchUsers,
  unfollowUser,
  type UserProfile,
  type UserSummary,
} from '@/api/users'
import type { CursorPage } from '@/api/gyms'

/**
 * 쿼리 키
 * - ['users', id]                 공개 프로필
 * - ['users', id, 'followers']    팔로워 (무한)
 * - ['users', id, 'following']    팔로잉 (무한)
 * - ['users', 'search', q]        닉네임 검색 (무한)
 * - ['logs', 'user', id]          회원의 기록 (무한) — useClimbs 의 좋아요·작성 반영 대상에 포함된다
 */
const userKey = (id: number) => ['users', id] as const
const followersKey = (id: number) => ['users', id, 'followers'] as const
const followingKey = (id: number) => ['users', id, 'following'] as const
const searchKey = (q: string) => ['users', 'search', q] as const
const userLogsKey = (id: number) => ['logs', 'user', id] as const

type SummaryPages = InfiniteData<CursorPage<UserSummary>, string | undefined>

/** 회원 요약 목록 캐시 전부 (팔로워·팔로잉·검색). ['users', id] 프로필은 제외 */
const SUMMARY_LISTS = {
  queryKey: ['users'],
  predicate: (query: Query) => {
    const key = query.queryKey
    return key[1] === 'search' || key[2] === 'followers' || key[2] === 'following'
  },
}

/** 목록 안의 같은 회원 isFollowing 을 한 번에 맞춘다 */
function patchSummaryLists(queryClient: QueryClient, id: number, isFollowing: boolean) {
  queryClient.setQueriesData<SummaryPages>(
    SUMMARY_LISTS,
    (pages) =>
      pages && {
        ...pages,
        pages: pages.pages.map((page) => ({
          ...page,
          results: page.results.map((user) =>
            user.id === id && user.isFollowing !== isFollowing ? { ...user, isFollowing } : user,
          ),
        })),
      },
  )
}

const cursorPaging = {
  initialPageParam: undefined as string | undefined,
  getNextPageParam: <T>(lastPage: CursorPage<T>) => lastPage.nextCursor ?? undefined,
}

// --- 조회 ---

export function useUser(id: number) {
  return useQuery({
    queryKey: userKey(id),
    queryFn: () => fetchUser(id),
    enabled: Number.isFinite(id),
  })
}

export function useFollowers(id: number) {
  return useInfiniteQuery({
    queryKey: followersKey(id),
    queryFn: ({ pageParam }) => fetchFollowers(id, pageParam),
    enabled: Number.isFinite(id),
    ...cursorPaging,
  })
}

export function useFollowing(id: number) {
  return useInfiniteQuery({
    queryKey: followingKey(id),
    queryFn: ({ pageParam }) => fetchFollowing(id, pageParam),
    enabled: Number.isFinite(id),
    ...cursorPaging,
  })
}

/** 검색어는 페이지에서 디바운스해서 넘긴다. 빈 문자열이면 요청하지 않는다 */
export function useSearchUsers(q: string) {
  const query = q.trim()
  return useInfiniteQuery({
    queryKey: searchKey(query),
    queryFn: ({ pageParam }) => searchUsers(query, pageParam),
    enabled: query.length > 0,
    ...cursorPaging,
  })
}

export function useUserLogs(id: number) {
  return useInfiniteQuery({
    queryKey: userLogsKey(id),
    queryFn: ({ pageParam }) => fetchUserLogs(id, pageParam),
    enabled: Number.isFinite(id),
    ...cursorPaging,
  })
}

// --- 팔로우 ---

/**
 * 팔로우 토글 — 낙관적 업데이트. 누르는 즉시 버튼 상태·팔로워 수를 바꾸고 실패하면 되돌린다.
 * 서버 API 가 멱등이라 연타해도 최종 상태만 맞으면 된다.
 * 상대 프로필(팔로워 수)·내 프로필(팔로잉 수)·회원 목록의 isFollowing 을 같이 고친다.
 */
export function useToggleFollow(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (follow: boolean) => (follow ? followUser(id) : unfollowUser(id)),
    onMutate: async (follow) => {
      await queryClient.cancelQueries({ queryKey: userKey(id), exact: true })
      const previous = queryClient.getQueryData<UserProfile>(userKey(id))
      const myId = queryClient.getQueryData<Me>(['me'])?.id
      const previousMine =
        myId === undefined ? undefined : queryClient.getQueryData<UserProfile>(userKey(myId))
      const delta = follow ? 1 : -1

      // 프로필이 캐시에 없으면(목록에서 바로 누른 경우) 목록 값만 바꾼다
      const changed = previous ? previous.isFollowing !== follow : true
      if (previous && changed) {
        queryClient.setQueryData<UserProfile>(userKey(id), {
          ...previous,
          isFollowing: follow,
          followerCount: Math.max(0, previous.followerCount + delta),
        })
      }
      if (previousMine && changed) {
        queryClient.setQueryData<UserProfile>(userKey(previousMine.id), {
          ...previousMine,
          followingCount: Math.max(0, previousMine.followingCount + delta),
        })
      }
      patchSummaryLists(queryClient, id, follow)
      return { previous, previousMine }
    },
    onError: (_error, follow, context) => {
      if (context?.previous) queryClient.setQueryData(userKey(id), context.previous)
      if (context?.previousMine) {
        queryClient.setQueryData(userKey(context.previousMine.id), context.previousMine)
      }
      patchSummaryLists(queryClient, id, !follow)
    },
    onSettled: () => {
      // 서버 집계값으로 최종 동기화. 목록은 스크롤이 튀지 않게 그대로 두고 다음 방문 때 새로 받는다
      queryClient.invalidateQueries({ queryKey: userKey(id), exact: true })
      queryClient.invalidateQueries({ queryKey: followersKey(id), refetchType: 'none' })
      const myId = queryClient.getQueryData<Me>(['me'])?.id
      if (myId !== undefined) {
        queryClient.invalidateQueries({ queryKey: userKey(myId), exact: true })
        queryClient.invalidateQueries({ queryKey: followingKey(myId), refetchType: 'none' })
      }
      // 팔로잉 피드는 구성이 달라진다
      queryClient.invalidateQueries({ queryKey: ['feed', 'following'], refetchType: 'none' })
    },
  })
}
