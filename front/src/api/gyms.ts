import { api } from '@/api/client'

export interface GymSummary {
  id: number
  name: string
  address: string
  lat: number
  lng: number
  distanceM: number | null
  thumbnail: string | null
}

export interface GymDifficulty {
  id: number
  name: string
  color: string
  order: number
}

export interface GymDetail extends Omit<GymSummary, 'distanceM' | 'thumbnail'> {
  description: string
  phone: string
  website: string
  images: { id: number; image: string; order: number }[]
  prices: { id: number; name: string; price: number; note: string }[]
  facilities: { id: number; name: string }[]
  difficulties: GymDifficulty[]
}

/** 지도 클러스터용 최소 필드 — 전국을 한 번에 받는다 */
export interface GymPoint {
  id: number
  name: string
  lat: number
  lng: number
}

export interface GymListParams {
  bbox?: string // minLng,minLat,maxLng,maxLat
  lat?: number
  lng?: number
  radius?: number // meters
}

export async function fetchGyms(params: GymListParams = {}): Promise<GymSummary[]> {
  const { data } = await api.get<GymSummary[]>('/gyms/', { params })
  return data
}

export async function fetchGym(id: number): Promise<GymDetail> {
  const { data } = await api.get<GymDetail>(`/gyms/${id}/`)
  return data
}

export async function fetchGymPoints(): Promise<GymPoint[]> {
  const { data } = await api.get<GymPoint[]>('/gyms/points/')
  return data
}
