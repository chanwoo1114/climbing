import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import UserProfile from '@/pages/UserProfile'
import { ME, renderWithProviders } from '@/test/render'
import { API, http, ok, page, server } from '@/test/server'

const USER = {
  id: 7,
  nickname: '초크러버',
  bio: '',
  image: null,
  home_gym: null,
  main_crew: null,
  follower_count: 3,
  following_count: 1,
  is_following: false,
  is_me: false,
  created_at: '2026-02-01T00:00:00Z',
}

const MONTHS = Array.from({ length: 12 }, (_, i) => ({
  month: `2026-${String(i + 1).padStart(2, '0')}`,
  total_count: 0,
  success_count: 0,
}))

const STATS = {
  total_count: 5,
  success_count: 2,
  success_rate: 40,
  gym_count: 1,
  avg_attempts: null,
  this_month: { month: '2026-08', total_count: 1, success_count: 1 },
  by_month: MONTHS,
  by_difficulty: [],
  top_gyms: [],
}

describe('UserProfile stats panel', () => {
  it('requests /users/7/stats/ and shows the panel under the header', async () => {
    let requested = false
    server.use(
      http.get(API('/users/7/'), () => ok(USER)),
      http.get(API('/users/7/logs/'), () => page([])),
      http.get(API('/users/7/stats/'), () => {
        requested = true
        return ok(STATS)
      }),
    )
    renderWithProviders(<UserProfile />, { route: '/users/7', path: '/users/:id', user: ME })

    expect(await screen.findByRole('heading', { name: '초크러버' })).toBeInTheDocument()
    expect(await screen.findByText('40.0%')).toBeInTheDocument()
    expect(requested).toBe(true)

    // 프로필 헤더 → 통계 → 기록 순서
    const headings = screen.getAllByRole('heading').map((h) => h.textContent)
    expect(headings.indexOf('초크러버')).toBeLessThan(headings.indexOf('통계'))
    expect(headings.indexOf('통계')).toBeLessThan(headings.indexOf('기록'))
  })
})
