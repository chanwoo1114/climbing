/**
 * 크루 목록 지역 필터 — 입력이 디바운스 후 ?region= 에 반영되고 요청에도 실린다. 초기화로 전부 비운다.
 */
import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import CrewList from '@/pages/CrewList'
import { ME, renderWithProviders } from '@/test/render'
import { API, http, page, server } from '@/test/server'

const CREW = {
  id: 1,
  name: '강남 볼더러',
  description: '',
  image: '',
  home_gym: { id: 3, name: '더클라임 강남' },
  owner: { id: 9, nickname: 'alpha' },
  join_type: 'instant',
  member_count: 3,
  max_members: 30,
  my_status: null,
  created_at: '2026-01-01T00:00:00Z',
}

function mockList() {
  const seen: URLSearchParams[] = []
  server.use(
    http.get(API('/crews/'), ({ request }) => {
      const params = new URL(request.url).searchParams
      seen.push(params)
      return page(params.get('region') === '강남구' ? [CREW] : [])
    }),
  )
  return seen
}

describe('CrewList region filter', () => {
  it('debounces the region input into ?region= and the request', async () => {
    const seen = mockList()
    const { user } = renderWithProviders(<CrewList />, { route: '/crews', user: ME })

    expect(await screen.findByText('아직 크루가 없어요')).toBeInTheDocument()
    expect(seen[0].has('region')).toBe(false)
    expect(screen.queryByRole('button', { name: '초기화' })).not.toBeInTheDocument()

    await user.type(screen.getByLabelText('지역 (예: 강남구)'), '강남구')
    // 300ms 디바운스 뒤 URL → 새 쿼리 → 요청에 region 이 실린다
    await waitFor(() => expect(seen[seen.length - 1].get('region')).toBe('강남구'))
    expect(await screen.findByText('강남 볼더러')).toBeInTheDocument()
    // 필터가 URL 에 있으니 초기화가 뜬다
    expect(screen.getByRole('button', { name: '초기화' })).toBeInTheDocument()
    // 중간 글자마다 요청하지 않는다 (처음 1번 + 완성된 지역명 1번)
    expect(seen).toHaveLength(2)
  })

  it('combines region with the name query and clears everything with 초기화', async () => {
    const seen = mockList()
    const { user } = renderWithProviders(<CrewList />, {
      route: '/crews?q=볼더&region=강남구',
      path: '/crews',
      user: ME,
    })

    await waitFor(() => expect(seen).toHaveLength(1))
    expect(seen[0].get('q')).toBe('볼더')
    expect(seen[0].get('region')).toBe('강남구')
    expect(screen.getByLabelText('지역 (예: 강남구)')).toHaveValue('강남구')
    expect(screen.getByLabelText('크루 이름')).toHaveValue('볼더')

    await user.click(screen.getByRole('button', { name: '초기화' }))
    await waitFor(() => expect(seen).toHaveLength(2))
    expect(seen[1].has('q')).toBe(false)
    expect(seen[1].has('region')).toBe(false)
    expect(screen.getByLabelText('지역 (예: 강남구)')).toHaveValue('')
    expect(screen.getByLabelText('크루 이름')).toHaveValue('')
    expect(screen.queryByRole('button', { name: '초기화' })).not.toBeInTheDocument()
  })

  it('links to the monthly ranking from the header', async () => {
    mockList()
    renderWithProviders(<CrewList />, { route: '/crews', user: ME })
    expect(await screen.findByRole('link', { name: '이달의 랭킹' })).toHaveAttribute(
      'href',
      '/crews/ranking',
    )
  })
})
