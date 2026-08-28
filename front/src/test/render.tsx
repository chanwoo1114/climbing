/**
 * 컴포넌트 테스트용 render — QueryClient + MemoryRouter + (선택) 로그인 상태.
 *
 *   renderWithProviders(<Profile />, { route: '/profile', user: ME })
 *   renderWithProviders(<UserProfile />, { route: '/users/7', path: '/users/:id' })
 *
 * 로그인 상태는 authStore.setSession 으로 만들고, ['me'] 쿼리 캐시도 미리 채워
 * 페이지가 useMe() 를 불러도 네트워크 없이 바로 렌더된다 (필요하면 msw 로 /users/me/ 도 흉내낼 것).
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'

import type { Me } from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'

export const ME: Me = {
  id: 1,
  email: 'me@example.com',
  nickname: '나',
  bio: '',
  image: '',
  homeGym: null,
  homeGymName: null,
  mainCrew: null,
  emailVerifiedAt: '2026-01-01T00:00:00Z',
  createdAt: '2026-01-01T00:00:00Z',
}

interface Options extends Omit<RenderOptions, 'wrapper'> {
  /** 시작 경로 (기본 '/') */
  route?: string
  /** 라우트 패턴 — useParams 를 쓰는 페이지면 '/users/:id' 처럼 넘긴다 (기본: route 그대로) */
  path?: string
  /** 로그인 사용자. 넘기면 authStore 가 authenticated 가 되고 ['me'] 캐시가 채워진다 */
  user?: Me | null
  queryClient?: QueryClient
}

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  })
}

export function renderWithProviders(ui: ReactElement, options: Options = {}) {
  const { route = '/', path = route, user = null, queryClient, ...rest } = options
  const client = queryClient ?? createTestQueryClient()

  if (user) {
    useAuthStore.getState().setSession('test-access-token', undefined, {
      id: user.id,
      email: user.email,
      nickname: user.nickname,
    })
    client.setQueryData(['me'], user)
  }

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path={path} element={children} />
            {/* 페이지가 navigate() 로 이동했을 때 어디로 갔는지 확인할 수 있게 */}
            <Route path="*" element={<LocationEcho />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }

  return {
    user: userEvent.setup(),
    queryClient: client,
    ...render(ui, { wrapper: Wrapper, ...rest }),
  }
}

function LocationEcho() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}
