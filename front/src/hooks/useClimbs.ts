import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type Query,
  type QueryClient,
} from '@tanstack/react-query'

import {
  createLog,
  createLogComment,
  deleteLog,
  deleteLogComment,
  fetchFeed,
  fetchLog,
  fetchLogComments,
  fetchMyLogs,
  likeLog,
  unlikeLog,
  updateLog,
  type ClimbLog,
  type ClimbLogCommentInput,
  type ClimbLogInput,
  type FeedScope,
  type MyLogsParams,
} from '@/api/climbs'
import { fetchGymDifficulties, type CursorPage } from '@/api/gyms'

/**
 * 쿼리 키
 * - ['feed', scope]              피드 (무한)
 * - ['logs', 'mine', params]     내 기록 (무한)
 * - ['logs', 'user', id]         회원 프로필의 기록 (무한, hooks/useUsers)
 * - ['logs', id]                 기록 상세
 * - ['logs', id, 'comments']     댓글 (무한) — ['logs', id] 무효화에 같이 딸려간다
 */
const feedKey = (scope: FeedScope) => ['feed', scope] as const
const myLogsKey = (params: MyLogsParams) => ['logs', 'mine', params] as const
const logKey = (id: number) => ['logs', id] as const
const commentsKey = (id: number) => ['logs', id, 'comments'] as const

type LogPages = InfiniteData<CursorPage<ClimbLog>, string | undefined>

/** 기록 목록 캐시 전부 — 내 기록 + 회원 프로필 기록. ['logs', id] 상세는 제외 */
const LOG_LISTS = {
  queryKey: ['logs'],
  predicate: (query: Query) => query.queryKey[1] === 'mine' || query.queryKey[1] === 'user',
}

/**
 * 같은 기록이 피드·내 기록·회원 기록·상세 캐시에 동시에 있을 수 있다.
 * 좋아요/댓글 수처럼 즉시 반영해야 하는 값은 세 군데를 한 번에 고친다.
 */
function patchLogEverywhere(
  queryClient: QueryClient,
  id: number,
  patch: (log: ClimbLog) => ClimbLog,
) {
  const inList = (pages: LogPages | undefined) =>
    pages && {
      ...pages,
      pages: pages.pages.map((page) => ({
        ...page,
        results: page.results.map((log) => (log.id === id ? patch(log) : log)),
      })),
    }
  queryClient.setQueriesData<LogPages>({ queryKey: ['feed'] }, inList)
  queryClient.setQueriesData<LogPages>(LOG_LISTS, inList)
  queryClient.setQueryData<ClimbLog>(logKey(id), (log) => log && patch(log))
}

// --- 조회 ---

export function useFeed(scope: FeedScope) {
  return useInfiniteQuery({
    queryKey: feedKey(scope),
    queryFn: ({ pageParam }) => fetchFeed(scope, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  })
}

export function useMyLogs(params: MyLogsParams = {}) {
  return useInfiniteQuery({
    queryKey: myLogsKey(params),
    queryFn: ({ pageParam }) => fetchMyLogs(params, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  })
}

export function useLog(id: number) {
  return useQuery({
    queryKey: logKey(id),
    queryFn: () => fetchLog(id),
    enabled: Number.isFinite(id),
  })
}

/** 기록 작성 폼의 난이도 선택지. 암장이 바뀌면 다시 받는다 */
export function useGymDifficulties(gymId: number | null) {
  return useQuery({
    queryKey: ['gyms', gymId, 'difficulties'],
    queryFn: () => fetchGymDifficulties(gymId as number),
    enabled: gymId !== null && Number.isFinite(gymId),
    staleTime: 10 * 60 * 1000,
  })
}

// --- 기록 CRUD ---

export function useCreateLog() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ClimbLogInput) => createLog(input),
    onSuccess: (log) => {
      // 상세로 바로 이동하므로 응답을 캐시에 미리 넣어 두면 로딩 없이 뜬다
      queryClient.setQueryData(logKey(log.id), log)
      queryClient.invalidateQueries({ queryKey: ['feed'] })
      queryClient.invalidateQueries(LOG_LISTS)
    },
  })
}

export function useUpdateLog(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: Partial<ClimbLogInput>) => updateLog(id, input),
    onSuccess: (log) => {
      queryClient.setQueryData(logKey(log.id), log)
      queryClient.invalidateQueries({ queryKey: ['feed'] })
      queryClient.invalidateQueries(LOG_LISTS)
    },
  })
}

export function useDeleteLog() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteLog(id),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: logKey(id) })
      queryClient.invalidateQueries({ queryKey: ['feed'] })
      queryClient.invalidateQueries(LOG_LISTS)
    },
  })
}

// --- 좋아요 ---

/**
 * 좋아요 토글 — 낙관적 업데이트. 누르는 즉시 하트·숫자를 바꾸고 실패하면 되돌린다.
 * 서버 API 가 멱등(POST/DELETE 모두 204)이라 연타해도 최종 상태만 맞으면 된다.
 */
export function useToggleLike(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (liked: boolean) => (liked ? likeLog(id) : unlikeLog(id)),
    onMutate: async (liked) => {
      await queryClient.cancelQueries({ queryKey: logKey(id), exact: true })
      patchLogEverywhere(queryClient, id, (log) =>
        log.isLiked === liked
          ? log
          : { ...log, isLiked: liked, likeCount: Math.max(0, log.likeCount + (liked ? 1 : -1)) },
      )
    },
    onError: (_error, liked) => {
      // 되돌리기 — 낙관적으로 바꾼 만큼 반대로 되돌린다
      patchLogEverywhere(queryClient, id, (log) =>
        log.isLiked === liked
          ? { ...log, isLiked: !liked, likeCount: Math.max(0, log.likeCount + (liked ? -1 : 1)) }
          : log,
      )
    },
    onSettled: () => {
      // 서버 집계값으로 최종 동기화 (상세만 — 피드는 스크롤 위치가 튀지 않게 그대로 둔다)
      queryClient.invalidateQueries({ queryKey: logKey(id), exact: true })
    },
  })
}

// --- 댓글 ---

export function useLogComments(logId: number) {
  return useInfiniteQuery({
    queryKey: commentsKey(logId),
    queryFn: ({ pageParam }) => fetchLogComments(logId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    enabled: Number.isFinite(logId),
  })
}

export function useCreateComment(logId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ClimbLogCommentInput) => createLogComment(logId, input),
    onSuccess: () => {
      patchLogEverywhere(queryClient, logId, (log) => ({
        ...log,
        commentCount: log.commentCount + 1,
      }))
      // 오래된 순이라 새 댓글은 마지막 페이지 뒤 — 목록을 다시 받는다
      queryClient.invalidateQueries({ queryKey: commentsKey(logId) })
    },
  })
}

export function useDeleteComment(logId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (commentId: number) => deleteLogComment(logId, commentId),
    onSuccess: () => {
      patchLogEverywhere(queryClient, logId, (log) => ({
        ...log,
        commentCount: Math.max(0, log.commentCount - 1),
      }))
      queryClient.invalidateQueries({ queryKey: commentsKey(logId) })
    },
  })
}
