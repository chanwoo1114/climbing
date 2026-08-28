import { screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import GymDetail from '@/pages/GymDetail'
import { BETA, GYM } from '@/test/betaFixtures'
import { renderWithProviders } from '@/test/render'
import { API, http, ok, page, server } from '@/test/server'

const SECTORS = [
  { sector: 'A벽', count: 3 },
  { sector: '오버행', count: 1 },
]

function renderBetasTab(search = '?tab=betas') {
  return renderWithProviders(<GymDetail />, { route: `/gyms/1${search}`, path: '/gyms/:id' })
}

describe('GymDetail 베타 탭', () => {
  /** 목록 요청마다 ?sector= 값을 기록한다 */
  let sectorsRequested: (string | null)[]

  beforeEach(() => {
    sectorsRequested = []
    server.use(
      http.get(API('/gyms/1/'), () => ok(GYM)),
      http.get(API('/gyms/1/betas/sectors/'), () => ok(SECTORS)),
      http.get(API('/gyms/1/betas/'), ({ request }) => {
        sectorsRequested.push(new URL(request.url).searchParams.get('sector'))
        return page([BETA], null)
      }),
    )
  })

  it('카드에 제목·난이도 색·섹터·조회수를 보여준다', async () => {
    renderBetasTab()
    const card = await screen.findByRole('link', { name: /하이스텝 베타/ })
    expect(within(card).getByText('A벽')).toBeInTheDocument()
    expect(within(card).getByText('조회 1,234')).toBeInTheDocument()
    // 난이도 색은 토큰이 아니라 DB 값(GymDifficulty.color)
    const dot = within(card).getByText('파랑').previousElementSibling
    expect(dot).toHaveStyle({ backgroundColor: '#1e40af' })
    // 베타 탭이 활성
    expect(screen.getByRole('link', { name: '베타' })).toHaveAttribute('aria-current', 'page')
  })

  it('섹터 칩을 누르면 ?sector= 가 붙고 목록 요청에 sector 가 실린다', async () => {
    const { user } = renderBetasTab()
    const chip = await screen.findByRole('link', { name: /^A벽\s*3$/ })
    expect(chip).not.toHaveAttribute('aria-current')
    await user.click(chip)
    await waitFor(() => expect(sectorsRequested).toContain('A벽'))
    expect(screen.getByRole('link', { name: /^A벽\s*3$/ })).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('link', { name: /^A벽\s*3$/ })).toHaveAttribute(
      'href',
      '/gyms/1?tab=betas&sector=A%EB%B2%BD',
    )
  })

  it('URL 의 ?sector= 로 처음부터 걸러서 요청한다', async () => {
    renderBetasTab('?tab=betas&sector=오버행')
    await screen.findByRole('link', { name: /하이스텝 베타/ })
    expect(sectorsRequested).toEqual(['오버행'])
  })

  it('베타가 없으면 빈 상태를 보여준다', async () => {
    server.use(http.get(API('/gyms/1/betas/'), () => page([], null)))
    renderBetasTab()
    expect(await screen.findByText('아직 베타 영상이 없어요')).toBeInTheDocument()
  })

  it('비로그인 사용자가 "베타 올리기"를 누르면 로그인으로 보낸다', async () => {
    const { user } = renderBetasTab()
    await user.click(await screen.findByRole('button', { name: '베타 올리기' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/login')
  })

  it('정보 탭에서는 베타 목록을 요청하지 않는다', async () => {
    renderWithProviders(<GymDetail />, { route: '/gyms/1', path: '/gyms/:id' })
    server.use(http.get(API('/gyms/1/reviews/'), () => page([], null)))
    expect(await screen.findByRole('heading', { name: '더클라임 강남' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '정보' })).toHaveAttribute('aria-current', 'page')
    expect(sectorsRequested).toEqual([])
  })
})
