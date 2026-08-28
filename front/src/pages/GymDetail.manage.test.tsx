import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import GymDetail from '@/pages/GymDetail'
import { GYM } from '@/test/betaFixtures'
import { ME, renderWithProviders } from '@/test/render'
import { API, http, ok, page, server } from '@/test/server'

function renderDetail() {
  return renderWithProviders(<GymDetail />, { route: '/gyms/1', path: '/gyms/:id', user: ME })
}

describe('GymDetail 관리 링크', () => {
  beforeEach(() => {
    server.use(http.get(API('/gyms/1/reviews/'), () => page([], null)))
  })

  it('is_manager 가 true 면 헤더에 "관리" 링크가 뜬다', async () => {
    server.use(http.get(API('/gyms/1/'), () => ok({ ...GYM, is_manager: true })))
    renderDetail()
    await screen.findByRole('heading', { name: '더클라임 강남' })
    expect(screen.getByRole('link', { name: '관리' })).toHaveAttribute('href', '/gyms/1/manage')
  })

  it('is_manager 가 false 면 "관리" 링크가 없다', async () => {
    server.use(http.get(API('/gyms/1/'), () => ok({ ...GYM, is_manager: false })))
    renderDetail()
    await screen.findByRole('heading', { name: '더클라임 강남' })
    expect(screen.queryByRole('link', { name: '관리' })).not.toBeInTheDocument()
  })
})
