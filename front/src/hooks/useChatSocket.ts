import { useEffect, useRef, useState } from 'react'

import { useAuthStore } from '@/stores/authStore'

/** WebSocket은 이 훅으로만 접근한다 (컴포넌트에서 직접 new WebSocket 금지). */
export function useChatSocket(roomId: number | null) {
  const accessToken = useAuthStore((s) => s.accessToken)
  const socketRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (!roomId || !accessToken) return

    // 기본은 현재 페이지 호스트 — vite dev 프록시(/ws)가 백엔드로 넘긴다.
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
    const base = import.meta.env.VITE_WS_BASE_URL || `${scheme}://${location.host}`
    const socket = new WebSocket(`${base}/ws/chat/${roomId}/?token=${accessToken}`)
    socketRef.current = socket

    socket.onopen = () => setConnected(true)
    socket.onclose = () => setConnected(false)

    return () => {
      socket.close()
      socketRef.current = null
    }
  }, [roomId, accessToken])

  return { socket: socketRef, connected }
}
