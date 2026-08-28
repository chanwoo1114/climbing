/**
 * "YYYY-MM" 월 문자열 유틸 — 크루 통계(?month=)·크루 랭킹이 같이 쓴다.
 * 서버(climbs.stats.parse_month)와 같은 형식이고 기본값은 Asia/Seoul 기준 이번 달.
 */

const MONTH_RE = /^\d{4}-(0[1-9]|1[0-2])$/

export const isValidMonth = (value: string | null | undefined): value is string =>
  !!value && MONTH_RE.test(value)

/** en-CA 로케일은 YYYY-MM 순서로 찍는다 */
const seoulMonth = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Seoul',
  year: 'numeric',
  month: '2-digit',
})

/** 이번 달 (Asia/Seoul) — 서버 기본값과 같다 */
export function currentMonth(now: Date = new Date()): string {
  return seoulMonth.format(now)
}

/** ?month= 값이 없거나 이상하면 이번 달 */
export function monthFromParams(params: URLSearchParams): string {
  const value = params.get('month')
  return isValidMonth(value) ? value : currentMonth()
}

/** delta 달 만큼 앞뒤로 (연도 넘김 처리) */
export function shiftMonth(month: string, delta: number): string {
  const [year, mon] = month.split('-').map(Number)
  const index = year * 12 + (mon - 1) + delta
  const y = Math.floor(index / 12)
  const m = (index % 12) + 1
  return `${y}-${String(m).padStart(2, '0')}`
}

const monthLabel = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long' })

/** "2026-08" → "2026년 8월" */
export function formatMonth(month: string): string {
  const [year, mon] = month.split('-').map(Number)
  // 월 중간의 정오 — 시간대와 무관하게 같은 달로 찍힌다
  return monthLabel.format(new Date(year, mon - 1, 15, 12))
}
