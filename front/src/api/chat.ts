import { api } from '@/api/client'
import { cursorFromLink, type CursorPage, type RawCursorPage } from '@/api/gyms'

// --- 읽기 모델 (backend chat/serializers.py) ---

/** 메시지 보낸 사람 / 참여자 요약 (ChatUserSerializer) */
export interface ChatUser {
  id: number
  nickname: string
  image: string | null
}

export type MessageType = 'text' | 'system'

/** REST 응답과 WebSocket "message" 이벤트가 같은 모양 (MessageSerializer) */
export interface ChatMessage {
  id: number
  roomId: number
  /** null 이면 시스템 메시지 */
  sender: ChatUser | null
  type: MessageType
  content: string
  createdAt: string
}

/** 목록용 마지막 메시지 — sender 는 id·nickname 만 */
export interface LastMessage {
  id: number
  content: string
  type: MessageType
  sender: { id: number; nickname: string } | null
  createdAt: string
}

/** GET rooms/ 항목 (ChatRoomListSerializer) */
export interface ChatRoom {
  id: number
  isGroup: boolean
  /** 1:1 은 빈 문자열 — 화면은 peer.nickname 을 쓴다 */
  name: string
  /** 1:1 방의 상대. 그룹은 null */
  peer: ChatUser | null
  memberCount: number
  lastMessage: LastMessage | null
  unreadCount: number
  /** 내가 마지막으로 읽은 메시지 id */
  lastReadMessageId: number | null
  createdAt: string
}

export interface ChatRoomMember {
  user: ChatUser
  joinedAt: string
  lastReadMessageId: number | null
}

/** GET rooms/{id}/ = 목록 항목 + 참여자 */
export interface ChatRoomDetail extends ChatRoom {
  members: ChatRoomMember[]
}

export const MESSAGE_MAX_LENGTH = 2000

function toPage<T>(data: RawCursorPage<T>): CursorPage<T> {
  return { results: data.results, nextCursor: cursorFromLink(data.nextCursor) }
}

// --- 방 ---

/** 내 채팅방 — 최근 활동순 커서 */
export async function fetchRooms(cursor?: string): Promise<CursorPage<ChatRoom>> {
  const { data } = await api.get<RawCursorPage<ChatRoom>>('/chat/rooms/', {
    params: cursor ? { cursor } : undefined,
  })
  return toPage(data)
}

/** 1:1 방 찾기/만들기 — 있으면 200, 새로 만들면 201. 둘 다 방을 돌려준다 */
export async function openDirectRoom(userId: number): Promise<ChatRoom> {
  const { data } = await api.post<ChatRoom>('/chat/rooms/direct/', { userId })
  return data
}

export async function fetchRoom(id: number): Promise<ChatRoomDetail> {
  const { data } = await api.get<ChatRoomDetail>(`/chat/rooms/${id}/`)
  return data
}

/** 그룹 방만 (1:1 은 400) */
export async function leaveRoom(id: number): Promise<void> {
  await api.delete(`/chat/rooms/${id}/leave/`)
}

// --- 메시지 ---

/** 최신 먼저 (cursor -id). 화면은 뒤집어서 그린다 */
export async function fetchMessages(
  roomId: number,
  cursor?: string,
): Promise<CursorPage<ChatMessage>> {
  const { data } = await api.get<RawCursorPage<ChatMessage>>(`/chat/rooms/${roomId}/messages/`, {
    params: cursor ? { cursor } : undefined,
  })
  return toPage(data)
}

/** 소켓이 닫혀 있을 때의 전송 경로. 소켓 접속자에게도 같은 이벤트가 브로드캐스트된다 */
export async function sendMessage(roomId: number, content: string): Promise<ChatMessage> {
  const { data } = await api.post<ChatMessage>(`/chat/rooms/${roomId}/messages/`, { content })
  return data
}

/** 읽음 위치 갱신 — 뒤로는 가지 않는다. 응답은 갱신 후 last_read_message_id */
export async function markRead(roomId: number, messageId: number): Promise<number | null> {
  const { data } = await api.post<{ messageId: number | null }>(`/chat/rooms/${roomId}/read/`, {
    messageId,
  })
  return data.messageId
}
