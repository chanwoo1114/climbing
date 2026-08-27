import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from '@tanstack/react-query'

import type { CursorPage } from '@/api/gyms'
import {
  deleteNotification,
  fetchNotifications,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
  type Notification,
} from '@/api/notifications'
import { useAuthStore } from '@/stores/authStore'

export { targetPath } from '@/api/notifications'

/**
 * 쿼리 키
 * - ['notifications', 'list', 'all' | 'unread']   알림 목록 (무한, 최신순)
 * - ['notifications', 'unread-count']             안 읽은 수 (헤더 배지)
 *
 * 소켓(useNotificationSocket)과 뮤테이션이 같은 캐시 패치 함수를 쓴다.
 * 'list' 아래의 모든 목록(전체/안 읽음)을 한꺼번에 고치므로 어느 화면이 열려 있든 같은 상태를 본다.
 */
export const notificationsKey = ['notifications'] as const
export const listPrefix = ['notifications', 'list'] as const
export const listKey = (unreadOnly: boolean) =>
  ['notifications', 'list', unreadOnly ? 'unread' : 'all'] as const
export const unreadCountKey = ['notifications', 'unread-count'] as const

type Pages = InfiniteData<CursorPage<Notification>, string | undefined>

// --- 조회 ---

export function useNotifications(unreadOnly: boolean) {
  return useInfiniteQuery({
    queryKey: listKey(unreadOnly),
    queryFn: ({ pageParam }) => fetchNotifications(unreadOnly, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  })
}

/**
 * 안 읽은 수. 소켓이 접속 직후·새 알림마다 캐시를 갱신하지만, 소켓이 포기했을 때를 대비해
 * 탭에 돌아오면 다시 받는다 (전역 기본값은 refetchOnWindowFocus: false).
 */
export function useUnreadCount() {
  const authenticated = useAuthStore((s) => s.status === 'authenticated')
  return useQuery({
    queryKey: unreadCountKey,
    queryFn: fetchUnreadCount,
    enabled: authenticated,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  })
}

// --- 캐시 패치 (소켓 이벤트와 뮤테이션이 같이 쓴다) ---

function patchCount(queryClient: QueryClient, delta: number) {
  queryClient.setQueryData<number>(unreadCountKey, (count) =>
    count === undefined ? count : Math.max(0, count + delta),
  )
}

/** 열려 있는 목록 캐시(전체/안 읽음)를 하나씩 고친다 — 안 읽음 목록은 읽은 항목을 빼야 해서 구분한다 */
function patchLists(
  queryClient: QueryClient,
  patch: (pages: Pages, unreadList: boolean) => Pages,
) {
  for (const [queryKey, pages] of queryClient.getQueriesData<Pages>({ queryKey: listPrefix })) {
    if (!pages) continue
    queryClient.setQueryData<Pages>(queryKey, patch(pages, queryKey[2] === 'unread'))
  }
}

/** 목록 캐시의 항목 하나를 찾는다 (읽음 여부를 알아야 배지를 정확히 줄인다) */
function findInLists(queryClient: QueryClient, id: number): Notification | undefined {
  for (const [, pages] of queryClient.getQueriesData<Pages>({ queryKey: listPrefix })) {
    for (const page of pages?.pages ?? []) {
      const found = page.results.find((n) => n.id === id)
      if (found) return found
    }
  }
  return undefined
}

/**
 * 새 알림을 열려 있는 모든 목록의 맨 앞에 넣고 배지를 하나 올린다.
 * 소켓과 REST 재조회가 겹칠 수 있어 id 로 중복을 거른다 (중복이면 배지도 그대로).
 */
export function prependNotification(queryClient: QueryClient, notification: Notification) {
  let duplicate = false
  queryClient.setQueriesData<Pages>({ queryKey: listPrefix }, (pages) => {
    if (!pages) return pages
    if (pages.pages.some((page) => page.results.some((n) => n.id === notification.id))) {
      duplicate = true
      return pages
    }
    const [first, ...rest] = pages.pages
    const head = first ?? { results: [], nextCursor: null }
    return { ...pages, pages: [{ ...head, results: [notification, ...head.results] }, ...rest] }
  })
  if (duplicate || notification.isRead) return
  patchCount(queryClient, 1)
}

/** 한 건 읽음 — 전체 목록에선 isRead 를 켜고, 안 읽음 목록에선 뺀다. 안 읽은 것이었으면 배지 -1 */
export function applyRead(queryClient: QueryClient, id: number) {
  const before = findInLists(queryClient, id)
  patchLists(queryClient, (pages, unreadList) => ({
    ...pages,
    pages: pages.pages.map((page) => ({
      ...page,
      results: unreadList
        ? page.results.filter((n) => n.id !== id)
        : page.results.map((n) => (n.id === id && !n.isRead ? { ...n, isRead: true } : n)),
    })),
  }))
  if (!before || !before.isRead) patchCount(queryClient, -1)
}

/** 전체 읽음 — 전체 목록은 모두 isRead, 안 읽음 목록은 비우고 배지 0 */
export function applyReadAll(queryClient: QueryClient) {
  patchLists(queryClient, (pages, unreadList) => ({
    ...pages,
    pages: pages.pages.map((page) => ({
      ...page,
      results: unreadList ? [] : page.results.map((n) => (n.isRead ? n : { ...n, isRead: true })),
    })),
  }))
  queryClient.setQueryData<number>(unreadCountKey, 0)
}

/** 삭제 — 모든 목록에서 빼고, 안 읽은 것이었으면 배지 -1 */
export function removeNotification(queryClient: QueryClient, id: number) {
  const before = findInLists(queryClient, id)
  queryClient.setQueriesData<Pages>(
    { queryKey: listPrefix },
    (pages) =>
      pages && {
        ...pages,
        pages: pages.pages.map((page) => ({
          ...page,
          results: page.results.filter((n) => n.id !== id),
        })),
      },
  )
  if (before && !before.isRead) patchCount(queryClient, -1)
}

// --- 뮤테이션 (낙관적 — 실패하면 서버 상태로 되돌린다) ---

/** 행을 누르면 읽음 처리 후 이동. 캐시를 먼저 고쳐서 이동 중에 배지가 바로 줄어든다 */
export function useMarkRead(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => markNotificationRead(id),
    onMutate: () => applyRead(queryClient, id),
    onError: () => queryClient.invalidateQueries({ queryKey: notificationsKey }),
  })
}

export function useMarkAllRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: markAllNotificationsRead,
    onMutate: () => applyReadAll(queryClient),
    onError: () => queryClient.invalidateQueries({ queryKey: notificationsKey }),
  })
}

export function useDeleteNotification(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => deleteNotification(id),
    onMutate: () => removeNotification(queryClient, id),
    onError: () => queryClient.invalidateQueries({ queryKey: notificationsKey }),
  })
}
