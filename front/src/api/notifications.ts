import { api } from '@/api/client'
import { cursorFromLink, type CursorPage, type RawCursorPage } from '@/api/gyms'

// --- 읽기 모델 (backend notifications/serializers.py) ---

export type NotificationType =
  | 'like'
  | 'comment'
  | 'reply'
  | 'follow'
  | 'recruitment_closed'
  | 'recruitment_approved'
  | 'recruitment_rejected'
  | 'crew_approved'
  | 'crew_rejected'
  | 'crew_joined'

/** 눌렀을 때 이동할 대상 종류 */
export type NotificationTargetType = 'climb_log' | 'post' | 'recruitment' | 'crew' | 'user'

/** 행위자 요약 (ActorSerializer). 시스템 알림(모집 마감 등)은 null */
export interface NotificationActor {
  id: number
  nickname: string
  image: string | null
}

/** REST 항목과 WebSocket "notification" 이벤트가 같은 모양 (NotificationSerializer) */
export interface Notification {
  id: number
  type: NotificationType
  actor: NotificationActor | null
  targetType: NotificationTargetType
  targetId: number
  /** 서버가 렌더링한 한국어 문구 (최대 200자) */
  message: string
  isRead: boolean
  createdAt: string
}

/** 알림을 눌렀을 때 갈 곳 — 서버의 target_type 과 짝 (routes.tsx 경로) */
export function targetPath(
  notification: Pick<Notification, 'targetType' | 'targetId'>,
): string {
  const { targetType, targetId } = notification
  switch (targetType) {
    case 'climb_log':
      return `/logs/${targetId}`
    case 'post':
    case 'recruitment':
      return `/posts/${targetId}`
    case 'crew':
      return `/crews/${targetId}`
    case 'user':
      return `/users/${targetId}`
  }
}

// --- 조회 ---

/** 내 알림 — 최신순 커서. unreadOnly 면 안 읽은 것만 */
export async function fetchNotifications(
  unreadOnly: boolean,
  cursor?: string,
): Promise<CursorPage<Notification>> {
  const { data } = await api.get<RawCursorPage<Notification>>('/notifications/', {
    params: { ...(unreadOnly ? { unread: 'true' } : {}), ...(cursor ? { cursor } : {}) },
  })
  return { results: data.results, nextCursor: cursorFromLink(data.nextCursor) }
}

export async function fetchUnreadCount(): Promise<number> {
  const { data } = await api.get<{ count: number }>('/notifications/unread-count/')
  return data.count
}

// --- 변경 (읽음 처리는 REST 로만 — 소켓은 서버→클라이언트 전용) ---

/** 한 건 읽음 (멱등). 갱신된 알림을 돌려준다 */
export async function markNotificationRead(id: number): Promise<Notification> {
  const { data } = await api.post<Notification>(`/notifications/${id}/read/`)
  return data
}

/** 전체 읽음. 갱신된 건수 */
export async function markAllNotificationsRead(): Promise<number> {
  const { data } = await api.post<{ updated: number }>('/notifications/read-all/')
  return data.updated
}

export async function deleteNotification(id: number): Promise<void> {
  await api.delete(`/notifications/${id}/`)
}
