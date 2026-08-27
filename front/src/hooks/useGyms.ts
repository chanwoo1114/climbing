import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { fetchGym, fetchGymPoints, fetchGyms, type GymListParams } from '@/api/gyms'

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
