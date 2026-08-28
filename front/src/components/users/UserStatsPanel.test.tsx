import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import UserStatsPanel from '@/components/users/UserStatsPanel'
import { renderWithProviders } from '@/test/render'
import { API, fail, http, ok, server } from '@/test/server'

/** 서버 응답(snake_case) — 12개월, 오래된 달부터 */
const BY_MONTH = [
  '2025-09',
  '2025-10',
  '2025-11',
  '2025-12',
  '2026-01',
  '2026-02',
  '2026-03',
  '2026-04',
  '2026-05',
  '2026-06',
  '2026-07',
  '2026-08',
].map((month, i) => ({ month, total_count: i === 11 ? 3 : i % 2, success_count: i === 11 ? 2 : 0 }))

const STATS = {
  total_count: 12,
  success_count: 8,
  success_rate: 66.7,
  gym_count: 2,
  avg_attempts: 2.5,
  this_month: { month: '2026-08', total_count: 3, success_count: 2 },
  by_month: BY_MONTH,
  by_difficulty: [
    {
      gym: { id: 1, name: '더클라임 강남' },
      difficulty: { id: 10, name: 'V3', color: '#ff8800', order: 3 },
      total_count: 6,
      success_count: 4,
      success_rate: 66.7,
    },
    {
      gym: { id: 1, name: '더클라임 강남' },
      difficulty: { id: 11, name: 'V4', color: '#1122cc', order: 4 },
      total_count: 3,
      success_count: 1,
      success_rate: 33.3,
    },
    {
      gym: { id: 2, name: '피커스 신림' },
      difficulty: { id: 20, name: '초록', color: '#22aa44', order: 2 },
      total_count: 3,
      success_count: 3,
      success_rate: 100,
    },
  ],
  top_gyms: [
    { gym: { id: 1, name: '더클라임 강남' }, total_count: 9, success_count: 5 },
    { gym: { id: 2, name: '피커스 신림' }, total_count: 3, success_count: 3 },
  ],
}

const EMPTY = {
  total_count: 0,
  success_count: 0,
  success_rate: 0,
  gym_count: 0,
  avg_attempts: null,
  this_month: { month: '2026-08', total_count: 0, success_count: 0 },
  by_month: BY_MONTH.map((m) => ({ ...m, total_count: 0, success_count: 0 })),
  by_difficulty: [],
  top_gyms: [],
}

/** 요약 타일의 값(<dd>) — 같은 낱말이 범례에도 있어 <dt> 로 좁힌다 */
function tile(label: string) {
  return screen.getByText(label, { selector: 'dt' }).nextElementSibling
}

describe('UserStatsPanel', () => {
  it('renders the stat tiles with formatted values', async () => {
    server.use(http.get(API('/users/7/stats/'), () => ok(STATS)))
    renderWithProviders(<UserStatsPanel userId={7} />)

    expect(await screen.findByText('66.7%')).toBeInTheDocument()
    expect(tile('총 기록')).toHaveTextContent('12')
    expect(tile('완등')).toHaveTextContent('8')
    expect(tile('성공률')).toHaveTextContent('66.7%')
    expect(tile('방문 암장')).toHaveTextContent('2')
    expect(tile('평균 시도')).toHaveTextContent('2.5')
    // 이번 달 한 줄
    expect(screen.getByText('2026년 8월')).toBeInTheDocument()
  })

  it('shows "—" when avg_attempts is null', async () => {
    server.use(http.get(API('/users/7/stats/'), () => ok({ ...STATS, avg_attempts: null })))
    renderWithProviders(<UserStatsPanel userId={7} />)
    expect(await screen.findByText('평균 시도')).toBeInTheDocument()
    expect(tile('평균 시도')).toHaveTextContent('—')
  })

  it('draws 12 month bars, each with an accessible title', async () => {
    server.use(http.get(API('/users/7/stats/'), () => ok(STATS)))
    renderWithProviders(<UserStatsPanel userId={7} />)

    const chart = await screen.findByRole('img', { name: /월별 기록 추이/ })
    const titles = [...chart.querySelectorAll('title')].map((t) => t.textContent)
    expect(titles).toHaveLength(12)
    expect(titles[0]).toBe('2025년 9월 기록 0 · 완등 0')
    expect(titles[11]).toBe('2026년 8월 기록 3 · 완등 2')
    // 총계 막대는 chalk, 완등 막대는 hold 로 겹쳐 그린다
    expect(chart.querySelectorAll('path.fill-hold-500')).toHaveLength(1)
    expect(chart.querySelectorAll('path.fill-chalk-300').length).toBeGreaterThan(1)
  })

  it('renders difficulty rows grouped by gym using the DB color', async () => {
    server.use(http.get(API('/users/7/stats/'), () => ok(STATS)))
    renderWithProviders(<UserStatsPanel userId={7} />)

    expect(await screen.findByText('난이도 분포')).toBeInTheDocument()
    const dots = screen.getAllByTestId('difficulty-dot')
    expect(dots).toHaveLength(3)
    expect(dots[0]).toHaveStyle({ backgroundColor: '#ff8800' })
    expect(dots[2]).toHaveStyle({ backgroundColor: '#22aa44' })
    expect(screen.getByText('4/6 (66.7%)')).toBeInTheDocument()
    expect(screen.getByText('3/3 (100.0%)')).toBeInTheDocument()

    // 자주 간 암장은 암장 상세로 간다
    const gyms = screen.getByText('자주 간 암장').nextElementSibling as HTMLElement
    const links = within(gyms).getAllByRole('link')
    expect(links[0]).toHaveAttribute('href', '/gyms/1')
    expect(links[0]).toHaveTextContent('기록 9')
  })

  it('shows one empty state when there are no logs', async () => {
    server.use(http.get(API('/users/7/stats/'), () => ok(EMPTY)))
    renderWithProviders(<UserStatsPanel userId={7} />)

    expect(await screen.findByText('아직 기록이 없어요')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByText('난이도 분포')).not.toBeInTheDocument()
  })

  it('renders an alert with retry on server error', async () => {
    server.use(http.get(API('/users/7/stats/'), () => fail(500, 'server_error', '서버 오류')))
    renderWithProviders(<UserStatsPanel userId={7} />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('서버 오류')
    expect(within(alert).getByRole('button', { name: '다시 시도' })).toBeInTheDocument()
  })
})
