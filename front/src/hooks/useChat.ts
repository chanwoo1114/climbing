import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from '@tanstack/react-query'
import { useNavigate } from 'react-router'

import {
  fetchMessages,
  fetchRoom,
  fetchRooms,
  leaveRoom,
  markRead,
  openDirectRoom,
  sendMessage,
  type ChatMessage,
  type ChatRoom,
  type ChatRoomDetail,
} from '@/api/chat'
import type { CursorPage } from '@/api/gyms'

/**
 * 쿼리 키
 * - ['chat', 'rooms']                    내 채팅방 목록 (무한, 최근 활동순)
 * - ['chat', 'room', id]                 방 상세 + 참여자
 * - ['chat', 'room', id, 'messages']     메시지 (무한, 페이지는 최신 먼저 — 화면은 뒤집어 그린다)
 */
export const roomsKey = ['chat', 'rooms'] as const
export const roomKey = (id: number) => ['chat', 'room', id] as const
export const messagesKey = (id: number) => ['chat', 'room', id, 'messages'] as const

type RoomPages = InfiniteData<CursorPage<ChatRoom>, string | undefined>
type MessagePages = InfiniteData<CursorPage<ChatMessage>, string | undefined>

// --- 조회 ---

export function useRooms(options: { enabled?: boolean; refetchInterval?: number } = {}) {
  return useInfiniteQuery({
    queryKey: roomsKey,
    queryFn: ({ pageParam }) => fetchRooms(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    enabled: options.enabled ?? true,
    refetchInterval: options.refetchInterval,
  })
}

export function useRoom(id: number) {
  return useQuery({
    queryKey: roomKey(id),
    queryFn: () => fetchRoom(id),
    enabled: Number.isFinite(id),
  })
}

/** 페이지는 최신 먼저(cursor -id). 오래된 순으로 그리려면 pages 와 results 를 둘 다 뒤집는다 */
export function useMessages(roomId: number) {
  return useInfiniteQuery({
    queryKey: messagesKey(roomId),
    queryFn: ({ pageParam }) => fetchMessages(roomId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    enabled: Number.isFinite(roomId),
    // 소켓이 실시간으로 캐시를 채우므로 포커스·재마운트 때 통째로 다시 받지 않는다
    staleTime: Infinity,
  })
}

/** 페이지(최신 먼저) → 화면 순서(오래된 → 최신) */
export function flattenMessages(
  pages: { pages: CursorPage<ChatMessage>[] } | undefined,
): ChatMessage[] {
  if (!pages) return []
  const out: ChatMessage[] = []
  for (let i = pages.pages.length - 1; i >= 0; i--) {
    const { results } = pages.pages[i]
    for (let j = results.length - 1; j >= 0; j--) out.push(results[j])
  }
  return out
}

// --- 캐시 패치 (소켓 이벤트와 뮤테이션 응답이 같이 쓴다) ---

function patchRoomInList(
  queryClient: QueryClient,
  roomId: number,
  patch: (room: ChatRoom) => ChatRoom,
  moveToTop = false,
) {
  queryClient.setQueryData<RoomPages>(roomsKey, (pages) => {
    if (!pages) return pages
    let found: ChatRoom | undefined
    const next = pages.pages.map((page) => ({
      ...page,
      results: page.results.flatMap((room) => {
        if (room.id !== roomId) return [room]
        found = patch(room)
        return moveToTop ? [] : [found]
      }),
    }))
    if (!found) return pages
    if (moveToTop && next.length > 0) {
      next[0] = { ...next[0], results: [found, ...next[0].results] }
    }
    return { ...pages, pages: next }
  })
  queryClient.setQueryData<ChatRoomDetail>(
    roomKey(roomId),
    (room) => room && { ...room, ...patch(room) },
  )
}

/**
 * 새 메시지를 메시지 캐시 맨 앞(최신 페이지의 첫 항목)에 넣고 방 목록의 미리보기·안 읽은 수를 올린다.
 * 내가 REST 로 보낸 메시지도 소켓으로 다시 오므로 id 로 중복을 거른다.
 */
export function appendMessage(queryClient: QueryClient, message: ChatMessage, meId?: number) {
  let duplicate = false
  queryClient.setQueryData<MessagePages>(messagesKey(message.roomId), (pages) => {
    if (!pages) return pages
    if (pages.pages.some((page) => page.results.some((m) => m.id === message.id))) {
      duplicate = true
      return pages
    }
    const [first, ...rest] = pages.pages
    const head = first ?? { results: [], nextCursor: null }
    return { ...pages, pages: [{ ...head, results: [message, ...head.results] }, ...rest] }
  })
  if (duplicate) return

  const mine = meId !== undefined && message.sender?.id === meId
  patchRoomInList(
    queryClient,
    message.roomId,
    (room) => ({
      ...room,
      lastMessage: {
        id: message.id,
        content: message.content,
        type: message.type,
        sender: message.sender ? { id: message.sender.id, nickname: message.sender.nickname } : null,
        createdAt: message.createdAt,
      },
      unreadCount: mine ? room.unreadCount : room.unreadCount + 1,
      lastReadMessageId: mine ? message.id : room.lastReadMessageId,
    }),
    true,
  )
}

/** 읽음 이벤트 — 참여자의 읽음 위치를 올린다. 내 것이면 목록의 안 읽은 수도 0 */
export function applyReadReceipt(
  queryClient: QueryClient,
  roomId: number,
  userId: number,
  messageId: number,
  meId?: number,
) {
  queryClient.setQueryData<ChatRoomDetail>(
    roomKey(roomId),
    (room) =>
      room && {
        ...room,
        members: room.members.map((member) =>
          member.user.id === userId && (member.lastReadMessageId ?? 0) < messageId
            ? { ...member, lastReadMessageId: messageId }
            : member,
        ),
      },
  )
  if (meId !== undefined && userId === meId) {
    patchRoomInList(queryClient, roomId, (room) => ({
      ...room,
      unreadCount: 0,
      lastReadMessageId: Math.max(room.lastReadMessageId ?? 0, messageId),
    }))
  }
}

// --- 뮤테이션 ---

/** 프로필의 "메시지" — 1:1 방을 찾거나 만들고 그 방으로 이동한다 */
export function useOpenDirectRoom(userId: number) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: () => openDirectRoom(userId),
    onSuccess: (room) => {
      queryClient.invalidateQueries({ queryKey: roomsKey })
      navigate(`/chat/rooms/${room.id}`)
    },
  })
}

/**
 * 메시지 전송. 소켓이 열려 있으면 소켓으로(sendOverSocket 이 true 를 돌려주면 끝),
 * 닫혀 있으면 REST 로 보낸다. 어느 쪽이든 저장된 메시지는 소켓 이벤트로도 돌아오므로
 * appendMessage 가 id 로 중복을 거른다.
 */
export function useSendMessage(
  roomId: number,
  sendOverSocket?: (content: string) => boolean,
  meId?: number,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (content: string): Promise<ChatMessage | null> => {
      if (sendOverSocket?.(content)) return null
      return sendMessage(roomId, content)
    },
    onSuccess: (message) => {
      if (message) appendMessage(queryClient, message, meId)
    },
  })
}

/** 읽음 위치 갱신. 성공하면 목록의 안 읽은 수를 0 으로 (서버 read 이벤트도 같은 일을 한다) */
export function useMarkRead(roomId: number, meId?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (messageId: number) => markRead(roomId, messageId),
    onSuccess: (lastRead) => {
      if (lastRead !== null && meId !== undefined) {
        applyReadReceipt(queryClient, roomId, meId, lastRead, meId)
      }
    },
  })
}

/** 그룹 방 나가기. 페이지가 성공 후 /chat 으로 이동한다 */
export function useLeaveRoom(roomId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => leaveRoom(roomId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: roomKey(roomId) })
      queryClient.setQueryData<RoomPages>(
        roomsKey,
        (pages) =>
          pages && {
            ...pages,
            pages: pages.pages.map((page) => ({
              ...page,
              results: page.results.filter((room) => room.id !== roomId),
            })),
          },
      )
      queryClient.invalidateQueries({ queryKey: roomsKey })
    },
  })
}
