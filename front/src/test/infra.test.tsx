/**
 * 테스트 인프라 자체 검증 — providers/msw/jest-dom/userEvent 가 함께 동작하는지.
 * 새 컴포넌트 테스트를 쓸 때 이 파일을 본보기로 삼는다.
 */
import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { api, getFieldError } from '@/api/client'
import { API, fail, http, ok, page, server } from '@/test/server'
import { ME, renderWithProviders } from '@/test/render'
import { useAuthStore } from '@/stores/authStore'
import { useQuery } from '@tanstack/react-query'

function Hello() {
  const { data } = useQuery({
    queryKey: ['hello'],
    queryFn: async () => (await api.get<{ greeting: string }>('/hello/')).data,
  })
  return <p role="status">{data ? data.greeting : '불러오는 중'}</p>
}

describe('test infra', () => {
  it('renders with providers and resolves msw responses (snake → camel)', async () => {
    server.use(http.get(API('/hello/'), () => ok({ greeting: '안녕' })))
    renderWithProviders(<Hello />)
    expect(await screen.findByText('안녕')).toHaveAttribute('role', 'status')
  })

  it('seeds a logged-in session when user is given', () => {
    renderWithProviders(<p>x</p>, { user: ME })
    expect(useAuthStore.getState().status).toBe('authenticated')
    expect(useAuthStore.getState().accessToken).toBe('test-access-token')
  })

  it('rejects with field errors through the axios interceptor', async () => {
    server.use(
      http.post(API('/things/'), () =>
        fail(400, 'invalid', '입력을 확인해 주세요.', { name: ['이름을 입력해 주세요.'] }),
      ),
    )
    await expect(api.post('/things/', { name: '' })).rejects.toSatisfy((error: unknown) => {
      return getFieldError(error, 'name') === '이름을 입력해 주세요.'
    })
  })

  it('page() builds a next_cursor link the client can parse', async () => {
    server.use(http.get(API('/items/'), () => page([{ id: 1 }], 'abc')))
    const { data } = await api.get<{ results: { id: number }[]; nextCursor: string }>('/items/')
    expect(data.results).toEqual([{ id: 1 }])
    expect(data.nextCursor).toContain('cursor=abc')
  })
})
