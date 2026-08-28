/**
 * /crews/ranking — 월별 크루 랭킹. 순위 순 목록·크루 링크·빈 상태·?month= 전달.
 */
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import CrewRanking from '@/pages/CrewRanking'
import { ME, renderWithProviders } from '@/test/render'
import { API, http, ok, server } from '@/test/server'

const row = (rank: number, id: number, name: string, successCount: number) => ({
  rank,
  crew: { id, name, image: null, home_gym: id === 5 ? { id: 3, name: '더클라임 강남' } : null },
  member_count: 10 + id,
  log_count: successCount * 2,
  success_count: successCount,
})

const RANKING = [row(1, 5, '알파', 42), row(2, 6, '베타', 30), row(3, 7, '감마', 12), row(4, 8, '델타', 1)]

function renderRanking(route = '/crews/ranking?month=2026-07') {
  return renderWithProviders(<CrewRanking />, { route, path: '/crews/ranking', user: ME })
}

describe('CrewRanking', () => {
  it('renders crews in rank order with links, gym and counts', async () => {
    const seen: string[] = []
    server.use(
      http.get(API('/crews/ranking/'), ({ request }) => {
        seen.push(request.url)
        return ok(RANKING)
      }),
    )
    renderRanking()

    const list = await screen.findByRole('list', { name: '2026년 7월 크루 랭킹' })
    const cards = within(list).getAllByRole('article')
    expect(cards.map((card) => within(card).getByRole('heading').textContent)).toEqual([
      '알파',
      '베타',
      '감마',
      '델타',
    ])
    expect(within(cards[0]).getByRole('link', { name: '알파' })).toHaveAttribute('href', '/crews/5')
    expect(within(cards[0]).getByText('더클라임 강남')).toBeInTheDocument()
    expect(within(cards[0]).getByText('크루원 15명')).toBeInTheDocument()
    expect(within(cards[0]).getByText('완등').nextElementSibling).toHaveTextContent('42')
    expect(within(cards[0]).getByText('기록').nextElementSibling).toHaveTextContent('84')
    expect(within(cards[3]).getByText('4위')).toBeInTheDocument()

    // ?month= 가 그대로 서버로, limit 은 기본 20
    const params = new URL(seen[0]).searchParams
    expect(params.get('month')).toBe('2026-07')
    expect(params.get('limit')).toBe('20')
  })

  it('moves to the previous month through the picker', async () => {
    const seen: string[] = []
    server.use(
      http.get(API('/crews/ranking/'), ({ request }) => {
        seen.push(request.url)
        return ok(RANKING)
      }),
    )
    const { user } = renderRanking()
    await screen.findByRole('list', { name: '2026년 7월 크루 랭킹' })
    await user.click(screen.getByRole('button', { name: '이전 달' }))
    expect(await screen.findByRole('list', { name: '2026년 6월 크루 랭킹' })).toBeInTheDocument()
    await waitFor(() =>
      expect(new URL(seen[seen.length - 1]).searchParams.get('month')).toBe('2026-06'),
    )
  })

  it('shows the empty state when no crew has logs', async () => {
    server.use(http.get(API('/crews/ranking/'), () => ok([])))
    renderRanking()
    expect(await screen.findByText('이 달 기록이 있는 크루가 없어요')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '크루 둘러보기' })).toHaveAttribute('href', '/crews')
  })
})
