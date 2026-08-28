import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import PostList from '@/pages/PostList'
import { ME, renderWithProviders } from '@/test/render'
import { API, http, page, server } from '@/test/server'

/** 게시글 목록 요청의 쿼리 문자열을 순서대로 모은다 */
function capturePostRequests() {
  const seen: URLSearchParams[] = []
  server.use(
    http.get(API('/posts/'), ({ request }) => {
      seen.push(new URL(request.url).searchParams)
      return page([])
    }),
  )
  return seen
}

describe('PostList search', () => {
  it('debounces typing into ?q= and sends q with the request', async () => {
    const seen = capturePostRequests()
    const { user } = renderWithProviders(<PostList />, { route: '/posts', user: ME })

    const input = await screen.findByRole('searchbox', { name: '검색' })
    await user.type(input, '볼더링')

    await waitFor(() => {
      expect(seen.some((params) => params.get('q') === '볼더링')).toBe(true)
    })
    // 검색어 있는 빈 목록은 검색 전용 빈 상태
    expect(await screen.findByText("'볼더링' 검색 결과가 없어요")).toBeInTheDocument()
  })

  it('combines q with the category filter and clears only q', async () => {
    const seen = capturePostRequests()
    const { user } = renderWithProviders(<PostList />, {
      route: '/posts?category=recruit&q=볼더링',
      path: '/posts',
      user: ME,
    })

    await waitFor(() => {
      expect(
        seen.some((params) => params.get('q') === '볼더링' && params.get('category') === 'recruit'),
      ).toBe(true)
    })
    const input = screen.getByRole('searchbox', { name: '검색' })
    expect(input).toHaveValue('볼더링')

    await user.click(screen.getByRole('button', { name: '검색어 지우기' }))

    await waitFor(() => {
      const last = seen[seen.length - 1]
      expect(last.get('q')).toBeNull()
      expect(last.get('category')).toBe('recruit')
    })
    expect(input).toHaveValue('')
    expect(screen.queryByText(/검색 결과가 없어요/)).not.toBeInTheDocument()
  })
})
