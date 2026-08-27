import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  createGymReview,
  fetchGym,
  fetchGymPoints,
  fetchGymReviews,
  fetchGyms,
  type GymListParams,
  type GymReviewInput,
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
