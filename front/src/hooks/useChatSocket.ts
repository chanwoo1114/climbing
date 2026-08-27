import { useCallback, useEffect, useRef, useState } from 'react'

import { keysToCamel, keysToSnake } from '@/api/case'
import type { ChatMessage } from '@/api/chat'
import { useAuthStore } from '@/stores/authStore'

/**
 * WebSocket 은 이 훅으로만 접근한다 (컴포넌트에서 직접 new WebSocket 금지).
 *
 * 주소: ws(s)://<현재 호스트>/ws/chat/{roomId}/?token=<access JWT>
 *   - 호스트를 현재 페이지에서 가져와야 vite 의 /ws 프록시(외부 접속 시 5180 하나만 개방)를 탄다.
 *   - 서버 페이로드는 snake_case 이고 응답 래퍼가 없다 → 여기서 keysToCamel 로 바꿔 넘긴다.
 *
 * 재연결
 *   - 비정상 종료는 1s → 2s → 5s 간격으로 최대 5회.
 *   - 4401(토큰 무효): authStore.refresh() 를 한 번만 부르고 새 토큰으로 다시 붙는다.
 *     그래도 4401 이면 포기 (세션이 끝난 것 — RequireAuth 가 /login 으로 보낸다).
 *   - 4403(참여자 아님): 재시도하지 않고 error 로 알린다.
 *   - 언마운트·roomId 변경 시 닫고, 그 뒤 들어오는 close 이벤트는 무시한다.
 */

export type ChatSocketStatus = 'connecting' | 'open' | 'closed'

export interface ChatSocketHandlers {
  onMessage?: (message: ChatMessage) => void
  onRead?: (event: { userId: number; messageId: number }) => void
  onTyping?: (user: { id: number; nickname: string }) => void
  /** 서버가 내려준 요청 오류 (내용 길이 초과 등) */
  onError?: (error: { code: string; message: string }) => void
}

type Outbound =
  | { type: 'message'; content: string }
  | { type: 'read'; messageId: number }
  | { type: 'typing' }

const RETRY_DELAYS_MS = [1000, 2000, 5000, 5000, 5000]
const MAX_RETRIES = RETRY_DELAYS_MS.length
const TYPING_THROTTLE_MS = 2000

const CLOSE_UNAUTHENTICATED = 4401
const CLOSE_FORBIDDEN = 4403

export const SOCKET_ERROR = {
  forbidden: '이 채팅방의 멤버가 아니에요',
  unauthenticated: '로그인이 만료됐어요. 다시 로그인해 주세요.',
  gaveUp: '연결이 끊겼어요. 새로고침하면 다시 연결돼요.',
} as const

function socketUrl(roomId: number, token: string): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const base = import.meta.env.VITE_WS_BASE_URL || `${scheme}://${window.location.host}`
  return `${base}/ws/chat/${roomId}/?token=${encodeURIComponent(token)}`
}

export function useChatSocket(roomId: number | null, handlers: ChatSocketHandlers = {}) {
  const [status, setStatus] = useState<ChatSocketStatus>('closed')
  const [error, setError] = useState<string | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const lastTypingAtRef = useRef(0)

  // 핸들러는 ref 로 들고 있어 매 렌더마다 바뀌어도 재연결하지 않는다
  const handlersRef = useRef(handlers)
  useEffect(() => {
    handlersRef.current = handlers
  })

  useEffect(() => {
    if (roomId === null || !Number.isFinite(roomId)) return

    let disposed = false
    let attempt = 0
    let refreshed = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const dispatch = (raw: unknown) => {
      const event = keysToCamel(raw) as { type?: string } & Record<string, unknown>
      const h = handlersRef.current
      switch (event.type) {
        case 'message':
          h.onMessage?.(event.message as ChatMessage)
          break
        case 'read':
          h.onRead?.({ userId: event.userId as number, messageId: event.messageId as number })
          break
        case 'typing':
          h.onTyping?.(event.user as { id: number; nickname: string })
          break
        case 'error':
          h.onError?.({ code: String(event.code), message: String(event.message) })
          break
      }
    }

    const connect = () => {
      const token = useAuthStore.getState().accessToken
      if (!token) {
        setStatus('closed')
        setError(SOCKET_ERROR.unauthenticated)
        return
      }
      setStatus('connecting')
      const socket = new WebSocket(socketUrl(roomId, token))
      socketRef.current = socket

      socket.onopen = () => {
        if (disposed) return
        attempt = 0
        refreshed = false
        setStatus('open')
        setError(null)
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

        if (e.code === CLOSE_FORBIDDEN) {
          setError(SOCKET_ERROR.forbidden)
          return
        }
        if (e.code === CLOSE_UNAUTHENTICATED) {
          if (refreshed) {
            setError(SOCKET_ERROR.unauthenticated)
            return
          }
          refreshed = true
          void useAuthStore
            .getState()
            .refresh()
            .then((ok) => {
              if (disposed) return
              if (ok) connect()
              else setError(SOCKET_ERROR.unauthenticated)
            })
          return
        }
        if (attempt >= MAX_RETRIES) {
          setError(SOCKET_ERROR.gaveUp)
          return
        }
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
      setError(null)
    }
  }, [roomId])

  /** 열려 있으면 보내고 true, 아니면 false (호출자가 REST 로 대신 보낸다) */
  const send = useCallback((payload: Outbound): boolean => {
    const socket = socketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) return false
    socket.send(JSON.stringify(keysToSnake(payload)))
    return true
  }, [])

  /** 입력 중 알림 — 2초에 한 번만 나간다 */
  const sendTyping = useCallback(() => {
    const now = Date.now()
    if (now - lastTypingAtRef.current < TYPING_THROTTLE_MS) return
    if (send({ type: 'typing' })) lastTypingAtRef.current = now
  }, [send])

  return { status, error, send, sendTyping }
}
