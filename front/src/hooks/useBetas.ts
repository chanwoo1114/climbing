import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createBeta,
  deleteBeta,
  fetchBeta,
  fetchBetaSectors,
  fetchGymBetas,
  updateBeta,
  type BetaListParams,
  type BetaWrite,
} from '@/api/betas'

/**
 * 쿼리 키
 * - ['betas', 'gym', gymId, params]     암장의 베타 목록 (무한)
 * - ['betas', 'gym', gymId, 'sectors']  암장의 섹터 목록
 * - ['betas', id]                       베타 상세
 * ['betas', 'gym', gymId] 를 무효화하면 목록과 섹터가 한 번에 다시 받아진다.
 */
const gymBetasKey = (gymId: number, params: BetaListParams) =>
  ['betas', 'gym', gymId, params] as const
const sectorsKey = (gymId: number) => ['betas', 'gym', gymId, 'sectors'] as const
const betaKey = (id: number) => ['betas', id] as const

// --- 조회 ---

export function useGymBetas(gymId: number, params: BetaListParams = {}, enabled = true) {
  return useInfiniteQuery({
    queryKey: gymBetasKey(gymId, params),
    queryFn: ({ pageParam }) => fetchGymBetas(gymId, params, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    enabled: enabled && Number.isFinite(gymId),
  })
}

export function useBetaSectors(gymId: number, enabled = true) {
  return useQuery({
    queryKey: sectorsKey(gymId),
    queryFn: () => fetchBetaSectors(gymId),
    enabled: enabled && Number.isFinite(gymId),
  })
}

export function useBeta(id: number) {
  return useQuery({
    queryKey: betaKey(id),
    queryFn: () => fetchBeta(id),
    enabled: Number.isFinite(id),
  })
}

// --- CRUD ---

export function useCreateBeta(gymId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: BetaWrite) => createBeta(gymId, input),
    onSuccess: (beta) => {
      // 상세로 바로 이동하므로 응답을 캐시에 미리 넣어 두면 로딩 없이 뜬다
      queryClient.setQueryData(betaKey(beta.id), beta)
      queryClient.invalidateQueries({ queryKey: ['betas', 'gym', gymId] })
    },
  })
}

export function useUpdateBeta(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: Partial<Omit<BetaWrite, 'videoUrl'>>) => updateBeta(id, input),
    onSuccess: (beta) => {
      queryClient.setQueryData(betaKey(beta.id), beta)
      queryClient.invalidateQueries({ queryKey: ['betas', 'gym', beta.gym.id] })
    },
  })
}

export function useDeleteBeta() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: number; gymId: number }) => deleteBeta(id),
    onSuccess: (_, { id, gymId }) => {
      queryClient.removeQueries({ queryKey: betaKey(id) })
      queryClient.invalidateQueries({ queryKey: ['betas', 'gym', gymId] })
    },
  })
}
