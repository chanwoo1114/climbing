import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import ManagedGyms from '@/pages/ManagedGyms'
import { ME, renderWithProviders } from '@/test/render'
import { API, http, ok, server } from '@/test/server'

const MANAGED = [
  {
    id: 1,
    name: '더클라임 강남',
    address: '서울 강남구',
    lat: 37.5,
    lng: 127.0,
    distance_m: null,
    thumbnail: null,
  },
  {
    id: 2,
    name: '클라이밍파크 홍대',
    address: '서울 마포구',
    lat: 37.55,
    lng: 126.92,
    distance_m: null,
    thumbnail: 'https://cdn.test/gyms/2.jpg',
  },
]

function renderPage() {
  return renderWithProviders(<ManagedGyms />, { route: '/gyms/managed', user: ME })
}

describe('ManagedGyms', () => {
  it('관리하는 암장을 이름·주소와 함께 관리 화면 링크로 보여준다', async () => {
    server.use(http.get(API('/gyms/managed/'), () => ok(MANAGED)))
    renderPage()
    const first = await screen.findByRole('link', { name: /더클라임 강남/ })
    expect(first).toHaveAttribute('href', '/gyms/1/manage')
    expect(first).toHaveTextContent('서울 강남구')
    expect(screen.getByRole('link', { name: /클라이밍파크 홍대/ })).toHaveAttribute(
      'href',
      '/gyms/2/manage',
    )
  })

  it('관리하는 암장이 없으면 빈 상태를 보여준다', async () => {
    server.use(http.get(API('/gyms/managed/'), () => ok([])))
    renderPage()
    expect(await screen.findByText('관리하는 암장이 없어요')).toBeInTheDocument()
    expect(screen.getByText('운영자에게 관리자 지정을 요청하세요.')).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})
