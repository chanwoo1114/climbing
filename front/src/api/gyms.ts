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
  /** 요청자가 이 암장의 관리자인지 (비로그인이면 false) */
  isManager: boolean
}

// --- 암장 관리 (관리자 전용 — 권한 실패는 403 "암장 관리자만 할 수 있습니다.") ---

export type GymImage = GymDetail['images'][number]
export type GymPrice = GymDetail['prices'][number]
export type GymFacility = GymDetail['facilities'][number]

/** PATCH gyms/{id}/ — 보낸 필드만 바뀐다 */
export interface GymUpdateInput {
  name?: string
  description?: string
  address?: string
  phone?: string
  website?: string
}

export interface GymDifficultyInput {
  name: string
  /** "#rrggbb" (소문자로 맞춰 보낸다) */
  color: string
  order: number
}

export interface GymPriceInput {
  name: string
  /** 원 단위 정수 */
  price: number
  note?: string
}

export interface GymManager {
  id: number
  user: { id: number; nickname: string; image: string | null }
  note: string
  createdAt: string
}

export interface GymManagerInput {
  userId: number
  note?: string
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

// --- 암장 관리 API ---

/** 내가 관리하는 암장 — 지도 목록 항목과 같은 모양, distance_m 은 null */
export async function fetchManagedGyms(): Promise<GymSummary[]> {
  const { data } = await api.get<GymSummary[]>('/gyms/managed/')
  return data
}

export async function updateGym(id: number, input: GymUpdateInput): Promise<GymDetail> {
  const { data } = await api.patch<GymDetail>(`/gyms/${id}/`, input)
  return data
}

export async function createDifficulty(
  gymId: number,
  input: GymDifficultyInput,
): Promise<GymDifficulty> {
  const { data } = await api.post<GymDifficulty>(`/gyms/${gymId}/difficulties/`, input)
  return data
}

export async function updateDifficulty(
  gymId: number,
  difficultyId: number,
  input: Partial<GymDifficultyInput>,
): Promise<GymDifficulty> {
  const { data } = await api.patch<GymDifficulty>(
    `/gyms/${gymId}/difficulties/${difficultyId}/`,
    input,
  )
  return data
}

export async function deleteDifficulty(gymId: number, difficultyId: number): Promise<void> {
  await api.delete(`/gyms/${gymId}/difficulties/${difficultyId}/`)
}

/** 사진은 presigned 업로드(post_image)로 먼저 올리고 그 URL 을 등록한다 */
export async function addGymImage(
  gymId: number,
  input: { image: string; order?: number },
): Promise<GymImage> {
  const { data } = await api.post<GymImage>(`/gyms/${gymId}/images/`, input)
  return data
}

export async function deleteGymImage(gymId: number, imageId: number): Promise<void> {
  await api.delete(`/gyms/${gymId}/images/${imageId}/`)
}

/** 전체 id 를 새 순서대로 — 모르는/중복 id 는 400 fields.ids */
export async function reorderGymImages(gymId: number, ids: number[]): Promise<GymImage[]> {
  const { data } = await api.put<GymImage[]>(`/gyms/${gymId}/images/order/`, { ids })
  return data
}

/** 가격표 전체 교체 — 빈 배열이면 모두 지운다 */
export async function replaceGymPrices(
  gymId: number,
  items: GymPriceInput[],
): Promise<GymPrice[]> {
  const { data } = await api.put<GymPrice[]>(`/gyms/${gymId}/prices/`, items)
  return data
}

/** 편의시설 전체 교체 */
export async function replaceGymFacilities(
  gymId: number,
  items: { name: string }[],
): Promise<GymFacility[]> {
  const { data } = await api.put<GymFacility[]>(`/gyms/${gymId}/facilities/`, items)
  return data
}

export async function fetchGymManagers(gymId: number): Promise<GymManager[]> {
  const { data } = await api.get<GymManager[]>(`/gyms/${gymId}/managers/`)
  return data
}

/** 이미 관리자면 200 으로 그대로 돌아온다. 없는 회원은 404 */
export async function addGymManager(gymId: number, input: GymManagerInput): Promise<GymManager> {
  const { data } = await api.post<GymManager>(`/gyms/${gymId}/managers/`, input)
  return data
}

/** 마지막 관리자는 409 last_manager */
export async function removeGymManager(gymId: number, userId: number): Promise<void> {
  await api.delete(`/gyms/${gymId}/managers/${userId}/`)
}
