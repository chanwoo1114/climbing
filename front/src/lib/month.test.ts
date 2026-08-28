import { describe, expect, it } from 'vitest'

import { currentMonth, formatMonth, isValidMonth, monthFromParams, shiftMonth } from '@/lib/month'

describe('month', () => {
  it('validates YYYY-MM', () => {
    expect(isValidMonth('2026-08')).toBe(true)
    expect(isValidMonth('2026-13')).toBe(false)
    expect(isValidMonth('2026-8')).toBe(false)
    expect(isValidMonth('')).toBe(false)
    expect(isValidMonth(null)).toBe(false)
  })

  it('shifts across year boundaries', () => {
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
    expect(shiftMonth('2025-12', 1)).toBe('2026-01')
    expect(shiftMonth('2026-08', -14)).toBe('2025-06')
  })

  it('uses Asia/Seoul for the current month', () => {
    // UTC 2026-08-31 15:30 은 서울에서 이미 9월 1일 00:30
    expect(currentMonth(new Date('2026-08-31T15:30:00Z'))).toBe('2026-09')
    expect(currentMonth(new Date('2026-08-31T14:30:00Z'))).toBe('2026-08')
  })

  it('falls back to the current month for a bad ?month=', () => {
    expect(monthFromParams(new URLSearchParams('month=2026-07'))).toBe('2026-07')
    expect(monthFromParams(new URLSearchParams('month=nope'))).toBe(currentMonth())
    expect(monthFromParams(new URLSearchParams())).toBe(currentMonth())
  })

  it('formats a Korean label', () => {
    expect(formatMonth('2026-08')).toBe('2026년 8월')
  })
})
