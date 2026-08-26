import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router'

import { router } from '@/routes'
import { useAuthStore } from '@/stores/authStore'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
})

// 새로고침해도 로그인이 유지되도록, 렌더 전에 저장된 refresh 토큰으로 세션을 복원한다.
// 기다리지 않는다 — 복원 중에는 status === 'booting' 이고 화면이 알아서 반응한다.
void useAuthStore.getState().bootstrap()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
