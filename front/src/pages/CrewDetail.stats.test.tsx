/**
 * 크루 상세 "통계" 탭 — ?tab=stats&month= 로 열고, 타일·크루원 랭킹·월 이동·403·빈 상태를 본다.
 */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import CrewDetail from '@/pages/CrewDetail'
import { ME, renderWithProviders } from '@/test/render'
import { API, fail, http, ok, server } from '@/test/server'

const CREW = {
  id: 1,
  name: '볼더팀',
  description: '',
  image: '',
  home_gym: null,
  owner: { id: 9, nickname: 'alpha' },
  join_type: 'instant',
  member_count: 3,
  max_members: 30,
  my_status: 'member',
  is_feed_public: false,
  chat_room_id: 5,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const STATS = {
  month: '2026-08',
  member_count: 3,
  active_member_count: 2,
  log_count: 1234,
  success_count: 7,
  success_rate: 58.3,
  gym_count: 2,
  ranking: [
    { rank: 1, user: { id: 2, nickname: 'bravo', image: null }, log_count: 6, success_count: 4 },
    { rank: 1, user: { id: 1, nickname: '나', image: null }, log_count: 5, success_count: 4 },
    { rank: 3, user: { id: 3, nickname: 'charlie', image: null }, log_count: 1, success_count: 0 },
  ],
}

function mockCrew() {
  server.use(http.get(API('/crews/1/'), () => ok(CREW)))
}

function renderStats(route = '/crews/1?tab=stats&month=2026-08') {
  return renderWithProviders(<CrewDetail />, { route, path: '/crews/:id', user: ME })
}

const rankingSection = () =>
  screen.getByRole('heading', { name: /크루원 랭킹/ }).closest('section') as HTMLElement

describe('CrewDetail stats tab', () => {
  it('renders stat tiles and the member ranking for the month in the URL', async () => {
    mockCrew()
    const seen: string[] = []
    server.use(
      http.get(API('/crews/1/stats/'), ({ request }) => {
        seen.push(request.url)
        return ok(STATS)
      }),
    )
    renderStats()

    expect(await screen.findByRole('heading', { name: '2026년 8월 활동' })).toBeInTheDocument()
    // 제목·월 선택은 바로 뜨고 타일·랭킹은 응답 뒤에
    await screen.findByRole('heading', { name: /크루원 랭킹/ })
    expect(new URL(seen[0]).searchParams.get('month')).toBe('2026-08')

    // 타일 — Intl 포맷 (천 단위 구분) + 성공률 소수 1자리
    expect(screen.getByText('완등').nextElementSibling).toHaveTextContent('7')
    expect(screen.getByText('기록').nextElementSibling).toHaveTextContent('1,234')
    expect(screen.getByText('성공률').nextElementSibling).toHaveTextContent('58.3%')
    expect(screen.getByText('활동 크루원').nextElementSibling).toHaveTextContent('2/ 3')
    expect(screen.getByText('암장 수').nextElementSibling).toHaveTextContent('2')

    // 랭킹 — 동점은 같은 순위 (1 / 1 / 3), 닉네임은 프로필 링크, 나는 표시
    const ranking = within(rankingSection())
    expect(ranking.getAllByText(/^\d+위$/).map((el) => el.textContent)).toEqual([
      '1위',
      '1위',
      '3위',
    ])
    expect(ranking.getByRole('link', { name: 'bravo' })).toHaveAttribute('href', '/users/2')
    const me = ranking.getByRole('listitem', { current: true })
    expect(me).toHaveTextContent('나')
    expect(me).toHaveTextContent('완등 4')

    // 통계 탭이 활성
    expect(screen.getByRole('link', { name: '통계' })).toHaveAttribute('aria-current', 'page')
  })

  it('re-queries with the new month when the picker changes', async () => {
    mockCrew()
    const seen: string[] = []
    server.use(
      http.get(API('/crews/1/stats/'), ({ request }) => {
        seen.push(request.url)
        const month = new URL(request.url).searchParams.get('month')
        return ok({ ...STATS, month, ranking: [] })
      }),
    )
    const { user } = renderStats()
    await screen.findByRole('heading', { name: '2026년 8월 활동' })

    await user.click(screen.getByRole('button', { name: '이전 달' }))
    expect(await screen.findByRole('heading', { name: '2026년 7월 활동' })).toBeInTheDocument()
    await waitFor(() =>
      expect(new URL(seen[seen.length - 1]).searchParams.get('month')).toBe('2026-07'),
    )

    // <input type="month"> 로 직접 고르기
    fireEvent.change(screen.getByLabelText(/^월 선택/), { target: { value: '2026-03' } })
    expect(await screen.findByRole('heading', { name: '2026년 3월 활동' })).toBeInTheDocument()
    await waitFor(() =>
      expect(new URL(seen[seen.length - 1]).searchParams.get('month')).toBe('2026-03'),
    )
    expect(seen).toHaveLength(3)
  })

  it('shows a members-only alert on 403', async () => {
    mockCrew()
    server.use(
      http.get(API('/crews/1/stats/'), () =>
        fail(403, 'permission_denied', '크루원만 볼 수 있습니다.'),
      ),
    )
    renderStats()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('크루원만 볼 수 있어요')
  })

  it('shows the empty state when nobody logged anything this month', async () => {
    mockCrew()
    server.use(
      http.get(API('/crews/1/stats/'), () =>
        ok({
          ...STATS,
          active_member_count: 0,
          log_count: 0,
          success_count: 0,
          success_rate: 0,
          gym_count: 0,
          ranking: [],
        }),
      ),
    )
    renderStats()
    expect(await screen.findByText('이 달 기록이 없어요')).toBeInTheDocument()
    expect(screen.getByText('성공률').nextElementSibling).toHaveTextContent('0%')
  })

  it('shows a loading skeleton while the stats are pending', async () => {
    mockCrew()
    server.use(
      http.get(API('/crews/1/stats/'), async () => {
        await new Promise((resolve) => setTimeout(resolve, 50))
        return ok(STATS)
      }),
    )
    renderStats()
    expect(await screen.findByText('통계를 불러오는 중…')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /크루원 랭킹/ })).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: /크루원 랭킹/ })).toBeInTheDocument()
    expect(screen.queryByText('통계를 불러오는 중…')).not.toBeInTheDocument()
  })
})
