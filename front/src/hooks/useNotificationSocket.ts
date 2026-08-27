import { useEffect, useRef, useState } from 'react'

import { keysToCamel } from '@/api/case'
import type { Notification } from '@/api/notifications'
import { useAuthStore } from '@/stores/authStore'

/**
 * 알림 WebSocket — 이 훅으로만 접근한다 (컴포넌트에서 직접 new WebSocket 금지).
 * 앱 전체에서 한 번만 마운트한다 (RootLayout 의 NotificationSocketBridge, 로그인 상태일 때만).
 *
 * 주소: ws(s)://<현재 호스트>/ws/notifications/?token=<access JWT>
 *   - 호스트를 현재 페이지에서 가져와야 vite 의 /ws 프록시(외부 접속 시 5180 하나만 개방)를 탄다.
 *   - 서버 페이로드는 snake_case 이고 응답 래퍼가 없다 → keysToCamel 로 바꿔 넘긴다.
 *   - 접속 직후 {"type":"unread_count","count"} 한 번, 그 뒤 {"type":"notification","notification"}.
 *   - 클라이언트→서버 입력은 없다 (읽음 처리는 REST).
 *
 * 재연결 (useChatSocket 과 같은 규칙)
 *   - 비정상 종료는 1s → 2s → 5s 간격으로 최대 5회. 그 뒤엔 조용히 포기한다 —
 *     화면에 알리지 않는다. 헤더 배지는 REST(useUnreadCount, 포커스 시 재조회)로도 유지된다.
 *   - 4401(토큰 무효): authStore.refresh() 를 한 번만 부르고 새 토큰으로 다시 붙는다.
 *     그래도 4401 이면 포기 (세션이 끝난 것 — RequireAuth 가 /login 으로 보낸다).
 *   - enabled 가 꺼지거나 언마운트되면 닫고, 그 뒤 들어오는 close 이벤트는 무시한다.
 */

export type NotificationSocketStatus = 'connecting' | 'open' | 'closed'

export interface NotificationSocketHandlers {
  onUnreadCount?: (count: number) => void
  onNotification?: (notification: Notification) => void
}

const RETRY_DELAYS_MS = [1000, 2000, 5000, 5000, 5000]
const MAX_RETRIES = RETRY_DELAYS_MS.length

const CLOSE_UNAUTHENTICATED = 4401

function socketUrl(token: string): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const base = import.meta.env.VITE_WS_BASE_URL || `${scheme}://${window.location.host}`
  return `${base}/ws/notifications/?token=${encodeURIComponent(token)}`
}

export function useNotificationSocket(enabled: boolean, handlers: NotificationSocketHandlers = {}) {
  const [status, setStatus] = useState<NotificationSocketStatus>('closed')
  const socketRef = useRef<WebSocket | null>(null)

  // 핸들러는 ref 로 들고 있어 매 렌더마다 바뀌어도 재연결하지 않는다
  const handlersRef = useRef(handlers)
  useEffect(() => {
    handlersRef.current = handlers
  })

  useEffect(() => {
    if (!enabled) return

    let disposed = false
    let attempt = 0
    let refreshed = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const dispatch = (raw: unknown) => {
      const event = keysToCamel(raw) as { type?: string } & Record<string, unknown>
      const h = handlersRef.current
      switch (event.type) {
        case 'unread_count':
          h.onUnreadCount?.(Number(event.count))
          break
        case 'notification':
          h.onNotification?.(event.notification as Notification)
          break
      }
    }

    const connect = () => {
      const token = useAuthStore.getState().accessToken
      if (!token) {
        setStatus('closed')
        return
      }
      setStatus('connecting')
      const socket = new WebSocket(socketUrl(token))
      socketRef.current = socket

      socket.onopen = () => {
        if (disposed) return
        attempt = 0
        refreshed = false
        setStatus('open')
      }
      socket.onmessage = (e: MessageEvent<string>) => {
        if (disposed) return
        try {
          dispatch(JSON.parse(e.data))
        } catch {
          // 깨진 프레임은 무시
        }
      }
      socket.onclose = (e: CloseEvent) => {
        if (disposed) return
        socketRef.current = null
        setStatus('closed')

        if (e.code === CLOSE_UNAUTHENTICATED) {
          if (refreshed) return
          refreshed = true
          void useAuthStore
            .getState()
            .refresh()
            .then((ok) => {
              if (!disposed && ok) connect()
            })
          return
        }
        if (attempt >= MAX_RETRIES) return
        timer = setTimeout(connect, RETRY_DELAYS_MS[attempt])
        attempt += 1
      }
      // onerror 뒤에는 항상 onclose 가 따라오므로 재연결은 거기서만 다룬다
      socket.onerror = () => undefined
    }

    connect()

    return () => {
      disposed = true
      if (timer !== undefined) clearTimeout(timer)
      const socket = socketRef.current
      socketRef.current = null
      if (socket) {
        socket.onclose = null
        socket.close()
      }
      setStatus('closed')
    }
  }, [enabled])

  return { status }
}
