import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  addGymImage,
  addGymManager,
  createDifficulty,
  createGymReview,
  deleteDifficulty,
  deleteGymImage,
  fetchGym,
  fetchGymManagers,
  fetchGymPoints,
  fetchGymReviews,
  fetchGyms,
  fetchManagedGyms,
  removeGymManager,
  reorderGymImages,
  replaceGymFacilities,
  replaceGymPrices,
  updateDifficulty,
  updateGym,
  type GymDifficultyInput,
  type GymListParams,
  type GymManagerInput,
  type GymPriceInput,
  type GymReviewInput,
  type GymUpdateInput,
} from '@/api/gyms'

export function useGyms(params: GymListParams = {}, enabled = true) {
  return useQuery({
    queryKey: ['gyms', params],
    queryFn: () => fetchGyms(params),
    enabled,
    // 지도를 움직일 때마다 목록이 비었다 차는 깜빡임 대신 이전 결과를 유지한다
    placeholderData: keepPreviousData,
  })
}

export function useGym(id: number) {
  return useQuery({
    queryKey: ['gyms', id],
    queryFn: () => fetchGym(id),
    enabled: Number.isFinite(id),
  })
}

/** 마커/클러스터용 전국 좌표. 암장이 자주 바뀌지 않으니 한 세션 동안 재사용한다 */
export function useGymPoints() {
  return useQuery({
    queryKey: ['gyms', 'points'],
    queryFn: fetchGymPoints,
    staleTime: 60 * 60 * 1000,
  })
}

// --- 리뷰 ---

const reviewsKey = (gymId: number) => ['gyms', gymId, 'reviews'] as const

/** 커서 페이지네이션 — "더 보기"가 fetchNextPage() 를 부른다 */
export function useGymReviews(gymId: number) {
  return useInfiniteQuery({
    queryKey: reviewsKey(gymId),
    queryFn: ({ pageParam }) => fetchGymReviews(gymId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    enabled: Number.isFinite(gymId),
  })
}

export function useCreateGymReview(gymId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: GymReviewInput) => createGymReview(gymId, input),
    // 새 리뷰는 -created_at 정렬의 맨 앞이라 첫 페이지부터 다시 받는다
    // 목록과 함께 상세(review_count·rating_avg 집계)도 다시 받는다.
    // ['gyms', gymId] 는 상세 키이자 리뷰 키의 접두사라 한 번에 둘 다 무효화된다.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['gyms', gymId] }),
  })
}

// --- 암장 관리 (관리자 전용) ---
//
// 쿼리 키
// - ['gyms', 'managed']         내가 관리하는 암장 목록
// - ['gyms', gymId, 'managers'] 관리자 목록
// 모든 변경은 상세(['gyms', gymId] — 난이도·리뷰·관리자 키의 접두사)와 관리 목록을 함께 무효화한다.

const managedKey = ['gyms', 'managed'] as const
const managersKey = (gymId: number) => ['gyms', gymId, 'managers'] as const

export function useManagedGyms(enabled = true) {
  return useQuery({ queryKey: managedKey, queryFn: fetchManagedGyms, enabled })
}

export function useGymManagers(gymId: number) {
  return useQuery({
    queryKey: managersKey(gymId),
    queryFn: () => fetchGymManagers(gymId),
    enabled: Number.isFinite(gymId),
  })
}

/** 관리 변경 공통 — 상세 + 관리 목록 무효화 */
function useGymMutation<TVariables, TData>(
  gymId: number,
  mutationFn: (variables: TVariables) => Promise<TData>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gyms', gymId] })
      queryClient.invalidateQueries({ queryKey: managedKey })
    },
  })
}

export function useUpdateGym(gymId: number) {
  return useGymMutation(gymId, (input: GymUpdateInput) => updateGym(gymId, input))
}

export function useCreateDifficulty(gymId: number) {
  return useGymMutation(gymId, (input: GymDifficultyInput) => createDifficulty(gymId, input))
}

export function useUpdateDifficulty(gymId: number) {
  return useGymMutation(
    gymId,
    ({ difficultyId, ...input }: Partial<GymDifficultyInput> & { difficultyId: number }) =>
      updateDifficulty(gymId, difficultyId, input),
  )
}

export function useDeleteDifficulty(gymId: number) {
  return useGymMutation(gymId, (difficultyId: number) => deleteDifficulty(gymId, difficultyId))
}

export function useAddGymImage(gymId: number) {
  return useGymMutation(gymId, (input: { image: string; order?: number }) =>
    addGymImage(gymId, input),
  )
}

export function useDeleteGymImage(gymId: number) {
  return useGymMutation(gymId, (imageId: number) => deleteGymImage(gymId, imageId))
}

export function useReorderGymImages(gymId: number) {
  return useGymMutation(gymId, (ids: number[]) => reorderGymImages(gymId, ids))
}

export function useReplaceGymPrices(gymId: number) {
  return useGymMutation(gymId, (items: GymPriceInput[]) => replaceGymPrices(gymId, items))
}

export function useReplaceGymFacilities(gymId: number) {
  return useGymMutation(gymId, (items: { name: string }[]) => replaceGymFacilities(gymId, items))
}

export function useAddGymManager(gymId: number) {
  return useGymMutation(gymId, (input: GymManagerInput) => addGymManager(gymId, input))
}

export function useRemoveGymManager(gymId: number) {
  return useGymMutation(gymId, (userId: number) => removeGymManager(gymId, userId))
}
