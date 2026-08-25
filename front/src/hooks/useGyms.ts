import { useQuery } from '@tanstack/react-query'

import { fetchGym, fetchGyms, type GymListParams } from '@/api/gyms'

export function useGyms(params: GymListParams = {}) {
  return useQuery({
    queryKey: ['gyms', params],
    queryFn: () => fetchGyms(params),
  })
}

export function useGym(id: number) {
  return useQuery({
    queryKey: ['gyms', id],
    queryFn: () => fetchGym(id),
    enabled: Number.isFinite(id),
  })
}
