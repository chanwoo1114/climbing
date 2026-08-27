import { create } from 'zustand'

/**
 * 앱 전역 토스트 — 화면은 components/common/Toast (RootLayout 에 한 번 렌더).
 * 새 알림(useNotificationSocket)처럼 화면 밖에서 생긴 일을 잠깐 알린다.
 * 5초 뒤 스스로 사라지고, 최대 3개까지만 쌓인다 (넘치면 가장 오래된 것부터 뺀다).
 */
export interface Toast {
  id: number
  title: string
  description?: string
  /** 있으면 토스트 전체가 이 경로로 가는 링크 */
  href?: string
}

export type ToastInput = Omit<Toast, 'id'>

interface ToastState {
  toasts: Toast[]
  push: (input: ToastInput) => number
  dismiss: (id: number) => void
}

export const TOAST_DURATION_MS = 5000
export const TOAST_MAX = 3

let nextId = 1
const timers = new Map<number, ReturnType<typeof setTimeout>>()

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],

  push: (input) => {
    const id = nextId++
    set((state) => {
      const next = [...state.toasts, { id, ...input }]
      // 오래된 것부터 잘라내고 타이머도 같이 정리한다
      while (next.length > TOAST_MAX) {
        const dropped = next.shift()!
        clearTimeout(timers.get(dropped.id))
        timers.delete(dropped.id)
      }
      return { toasts: next }
    })
    timers.set(
      id,
      setTimeout(() => get().dismiss(id), TOAST_DURATION_MS),
    )
    return id
  },

  dismiss: (id) => {
    clearTimeout(timers.get(id))
    timers.delete(id)
    set((state) =>
      state.toasts.some((t) => t.id === id)
        ? { toasts: state.toasts.filter((t) => t.id !== id) }
        : state,
    )
  },
}))
