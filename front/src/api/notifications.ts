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
  /** 크루장 위임 — 대상은 crew */
  | 'crew_owner'
  /** 자세 분석·리포트 결과 — 대상은 climb_log (분석 패널은 /logs/{id} 에 있다) */
  | 'analysis_done'
  | 'analysis_failed'
  | 'report_done'
  | 'report_failed'

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

// --- 알림 설정 (pages/Settings) ---

export interface NotificationSettings {
  /** 브라우저 푸시(Web Push) 수신 여부 — 구독 자체는 push-subscriptions 로 따로 관리한다 */
  pushEnabled: boolean
  /** 이메일 알림(모집·크루 결과, 분석 완료) 수신 여부 */
  emailEnabled: boolean
}

export async function fetchNotificationSettings(): Promise<NotificationSettings> {
  const { data } = await api.get<NotificationSettings>('/notifications/settings/')
  return data
}

/** 보낸 필드만 바뀐다. 갱신된 설정 전체를 돌려준다 */
export async function updateNotificationSettings(
  patch: Partial<NotificationSettings>,
): Promise<NotificationSettings> {
  const { data } = await api.patch<NotificationSettings>('/notifications/settings/', patch)
  return data
}

// --- 브라우저 푸시 구독 (hooks/usePush) ---

/** VAPID 공개키(base64url). 서버에 키가 없으면 503 push_not_configured */
export async function fetchPushPublicKey(): Promise<string> {
  const { data } = await api.get<{ publicKey: string }>('/notifications/push/public-key/')
  return data.publicKey
}

/** PushSubscription.toJSON() 모양 그대로 — 서버가 endpoint 로 중복을 거른다 */
export interface PushSubscriptionInput {
  endpoint: string
  keys: { p256dh: string; auth: string }
  userAgent?: string
}

export interface PushSubscriptionRecord {
  id: number
  endpoint: string
  createdAt: string
}

export async function createPushSubscription(
  input: PushSubscriptionInput,
): Promise<PushSubscriptionRecord> {
  const { data } = await api.post<PushSubscriptionRecord>('/notifications/push-subscriptions/', input)
  return data
}

/** 204 — endpoint 로 찾는다 (같은 브라우저의 구독만 지운다) */
export async function deletePushSubscription(endpoint: string): Promise<void> {
  await api.delete('/notifications/push-subscriptions/', { data: { endpoint } })
}
