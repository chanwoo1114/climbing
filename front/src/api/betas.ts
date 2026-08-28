import type { LogGym, LogUser } from '@/api/climbs'
import { api } from '@/api/client'
import { cursorFromLink, type CursorPage, type GymDifficulty, type RawCursorPage } from '@/api/gyms'

// --- 읽기 모델 (backend climbs.serializers.ClimbBetaSerializer) ---

/** 베타 영상 — 특정 암장·섹터·난이도 문제의 풀이 영상. 읽기는 공개, 쓰기는 본인만 */
export interface ClimbBeta {
  id: number
  user: LogUser
  gym: LogGym
  /** 색은 토큰이 아니라 암장이 정한 값(GymDifficulty.color) 그대로 렌더링한다 */
  difficulty: GymDifficulty | null
  sector: string
  title: string
  description: string
  videoUrl: string
  /** 없으면 빈 문자열 */
  thumbnailUrl: string
  /** 연결된 내 등반 기록 id */
  climbLogId: number | null
  viewCount: number
  createdAt: string
  isMine: boolean
}

export interface BetaSector {
  sector: string
  count: number
}

/**
 * POST gyms/{id}/betas/ 입력. PATCH 는 Partial — 단 video_url 은 생성 때만 받는다
 * (수정 요청에 video_url 이 있으면 서버가 400).
 */
export interface BetaWrite {
  title: string
  videoUrl?: string
  sector?: string
  difficulty?: number | null
  description?: string
  thumbnailUrl?: string
  climbLog?: number | null
}

export interface BetaListParams {
  /** 대소문자 무시 정확히 일치 */
  sector?: string
  /** GymDifficulty id */
  difficulty?: number
  /** 제목 부분 일치 */
  q?: string
}

export const BETA_TITLE_MAX_LENGTH = 100
export const BETA_SECTOR_MAX_LENGTH = 50
export const BETA_DESCRIPTION_MAX_LENGTH = 1000

function toPage<T>(data: RawCursorPage<T>): CursorPage<T> {
  return { results: data.results, nextCursor: cursorFromLink(data.nextCursor) }
}

export async function fetchGymBetas(
  gymId: number,
  params: BetaListParams = {},
  cursor?: string,
): Promise<CursorPage<ClimbBeta>> {
  const { data } = await api.get<RawCursorPage<ClimbBeta>>(`/gyms/${gymId}/betas/`, {
    params: { ...params, ...(cursor ? { cursor } : {}) },
  })
  return toPage(data)
}

/** 암장의 섹터 목록 (영상 수 많은 순) — 필터 칩과 작성 폼의 자동완성 후보 */
export async function fetchBetaSectors(gymId: number): Promise<BetaSector[]> {
  const { data } = await api.get<BetaSector[]>(`/gyms/${gymId}/betas/sectors/`)
  return data
}

/** 조회할 때마다 서버가 view_count 를 올린다 */
export async function fetchBeta(id: number): Promise<ClimbBeta> {
  const { data } = await api.get<ClimbBeta>(`/betas/${id}/`)
  return data
}

export async function createBeta(gymId: number, input: BetaWrite): Promise<ClimbBeta> {
  const { data } = await api.post<ClimbBeta>(`/gyms/${gymId}/betas/`, input)
  return data
}

export async function updateBeta(
  id: number,
  input: Partial<Omit<BetaWrite, 'videoUrl'>>,
): Promise<ClimbBeta> {
  const { data } = await api.patch<ClimbBeta>(`/betas/${id}/`, input)
  return data
}

export async function deleteBeta(id: number): Promise<void> {
  await api.delete(`/betas/${id}/`)
}
