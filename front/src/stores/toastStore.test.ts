import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { targetPath } from '@/api/notifications'
import { TOAST_DURATION_MS, TOAST_MAX, useToastStore } from '@/stores/toastStore'

describe('toastStore', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    useToastStore.setState({ toasts: [] })
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('push 하면 쌓이고 5초 뒤 스스로 사라진다', () => {
    useToastStore.getState().push({ title: '누군가 좋아요를 눌렀어요', href: '/logs/1' })
    expect(useToastStore.getState().toasts).toHaveLength(1)
    vi.advanceTimersByTime(TOAST_DURATION_MS - 1)
    expect(useToastStore.getState().toasts).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('최대 3개 — 넘치면 가장 오래된 것부터 뺀다', () => {
    const { push } = useToastStore.getState()
    const ids = [1, 2, 3, 4].map((n) => push({ title: `알림 ${n}` }))
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(TOAST_MAX)
    expect(toasts.map((t) => t.id)).toEqual(ids.slice(1))
  })

  it('dismiss 는 그 토스트만 지우고 타이머도 정리한다', () => {
    const { push, dismiss } = useToastStore.getState()
    const a = push({ title: 'a' })
    const b = push({ title: 'b' })
    dismiss(a)
    expect(useToastStore.getState().toasts.map((t) => t.id)).toEqual([b])
    // 이미 지운 id 를 다시 지워도 상태는 그대로
    const before = useToastStore.getState().toasts
    dismiss(a)
    expect(useToastStore.getState().toasts).toBe(before)
  })
})

describe('targetPath', () => {
  it('target_type 별로 routes.tsx 경로에 맞춘다', () => {
    expect(targetPath({ targetType: 'climb_log', targetId: 7 })).toBe('/logs/7')
    expect(targetPath({ targetType: 'post', targetId: 7 })).toBe('/posts/7')
    expect(targetPath({ targetType: 'recruitment', targetId: 7 })).toBe('/posts/7')
    expect(targetPath({ targetType: 'crew', targetId: 7 })).toBe('/crews/7')
    expect(targetPath({ targetType: 'user', targetId: 7 })).toBe('/users/7')
  })
})
