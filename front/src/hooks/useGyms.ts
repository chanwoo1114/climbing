import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { fetchGym, fetchGyms, type GymListParams } from '@/api/gyms'

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
