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
  /** 삭제되지 않은 리뷰 전체 기준 (서버 집계) */
  reviewCount: number
  ratingAvg: number | null
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

// --- 리뷰 ---

/** accounts.UserSerializer 공개 필드 */
export interface ReviewAuthor {
  id: number
  email: string
  nickname: string
  createdAt: string
}

export interface GymReview {
  id: number
  user: ReviewAuthor
  /** 1~5 */
  rating: number
  content: string
  createdAt: string
}

export interface GymReviewInput {
  rating: number
  content: string
}

/** 커서 페이지 — 서버(common.pagination)의 next_cursor 는 전체 URL 이라 cursor 값만 뽑아 둔다 */
export interface CursorPage<T> {
  results: T[]
  /** 다음 페이지 cursor 값. null 이면 끝 */
  nextCursor: string | null
}

export interface RawCursorPage<T> {
  results: T[]
  nextCursor: string | null
  previousCursor: string | null
}

/** 서버가 준 next_cursor(전체 URL)에서 cursor 값만 뽑는다. 다른 도메인 API(climbs 등)도 같이 쓴다 */
export function cursorFromLink(link: string | null): string | null {
  if (!link) return null
  try {
    return new URL(link, window.location.origin).searchParams.get('cursor')
  } catch {
    return null
  }
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

/** 암장 난이도 목록 (공개, 페이지네이션 없음) — 기록 작성 폼의 난이도 선택지 */
export async function fetchGymDifficulties(gymId: number): Promise<GymDifficulty[]> {
  const { data } = await api.get<GymDifficulty[]>(`/gyms/${gymId}/difficulties/`)
  return [...data].sort((a, b) => a.order - b.order)
}

export async function fetchGymReviews(
  gymId: number,
  cursor?: string,
): Promise<CursorPage<GymReview>> {
  const { data } = await api.get<RawCursorPage<GymReview>>(`/gyms/${gymId}/reviews/`, {
    params: cursor ? { cursor } : undefined,
  })
  return { results: data.results, nextCursor: cursorFromLink(data.nextCursor) }
}

export async function createGymReview(gymId: number, input: GymReviewInput): Promise<GymReview> {
  const { data } = await api.post<GymReview>(`/gyms/${gymId}/reviews/`, input)
  return data
}
