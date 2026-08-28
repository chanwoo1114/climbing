import { api } from '@/api/client'
import type { ClimbLog } from '@/api/climbs'
import { cursorFromLink, type CursorPage, type RawCursorPage } from '@/api/gyms'

// --- 읽기 모델 ---

/** GET users/{id}/ (accounts.PublicProfileSerializer). 이메일은 내려오지 않는다 */
export interface UserProfile {
  id: number
  nickname: string
  bio: string
  image: string | null
  homeGym: { id: number; name: string } | null
  /** 대표 크루. 없으면 null */
  mainCrew: { id: number; name: string } | null
  followerCount: number
  followingCount: number
  /** 요청자가 이 회원을 팔로우 중인지 */
  isFollowing: boolean
  isMe: boolean
  createdAt: string
}

/** 팔로워·팔로잉·검색 목록 항목 (social.UserSummarySerializer) */
export interface UserSummary {
  id: number
  nickname: string
  image: string | null
  isFollowing: boolean
}

function toPage<T>(data: RawCursorPage<T>): CursorPage<T> {
  return { results: data.results, nextCursor: cursorFromLink(data.nextCursor) }
}

// --- 프로필 ---

export async function fetchUser(id: number): Promise<UserProfile> {
  const { data } = await api.get<UserProfile>(`/users/${id}/`)
  return data
}

// --- 팔로우 (멱등: POST 201 / DELETE 204, 자기 자신은 400) ---

export async function followUser(id: number): Promise<void> {
  await api.post(`/users/${id}/follow/`)
}

export async function unfollowUser(id: number): Promise<void> {
  await api.delete(`/users/${id}/follow/`)
}

// --- 목록 (최근 팔로우 순 커서) ---

export async function fetchFollowers(
  id: number,
  cursor?: string,
): Promise<CursorPage<UserSummary>> {
  const { data } = await api.get<RawCursorPage<UserSummary>>(`/users/${id}/followers/`, {
    params: cursor ? { cursor } : undefined,
  })
  return toPage(data)
}

export async function fetchFollowing(
  id: number,
  cursor?: string,
): Promise<CursorPage<UserSummary>> {
  const { data } = await api.get<RawCursorPage<UserSummary>>(`/users/${id}/following/`, {
    params: cursor ? { cursor } : undefined,
  })
  return toPage(data)
}

/** 닉네임 부분 일치. q 는 1자 이상, 페이지당 최대 20건 */
export async function searchUsers(q: string, cursor?: string): Promise<CursorPage<UserSummary>> {
  const { data } = await api.get<RawCursorPage<UserSummary>>('/users/search/', {
    params: { q, ...(cursor ? { cursor } : {}) },
  })
  return toPage(data)
}

// --- 통계 (GET users/{id}/stats/ — climbs.stats) ---

/** "YYYY-MM" 한 달치 집계 */
export interface UserStatsMonth {
  month: string
  totalCount: number
  successCount: number
}

/** 암장 × 난이도별 집계. difficulty.color 는 DB 값 — 그대로 렌더링한다 */
export interface UserStatsDifficulty {
  gym: { id: number; name: string }
  difficulty: { id: number; name: string; color: string; order: number }
  totalCount: number
  successCount: number
  /** 0~100, 소수 1자리 */
  successRate: number
}

export interface UserStatsGym {
  gym: { id: number; name: string }
  totalCount: number
  successCount: number
}

/**
 * 회원 등반 통계. 본인이면 전체 기록, 타인이면 공개 기록만 집계된다 (서버가 정한다).
 * byMonth 는 최근 12개월, 오래된 달부터, 기록 없는 달은 0 으로 채워져 온다.
 */
export interface UserStats {
  totalCount: number
  successCount: number
  /** 0~100, 소수 1자리 */
  successRate: number
  gymCount: number
  /** 시도 횟수를 적은 기록이 없으면 null */
  avgAttempts: number | null
  thisMonth: UserStatsMonth
  byMonth: UserStatsMonth[]
  byDifficulty: UserStatsDifficulty[]
  topGyms: UserStatsGym[]
}

export async function fetchUserStats(id: number): Promise<UserStats> {
  const { data } = await api.get<UserStats>(`/users/${id}/stats/`)
  return data
}

/** 회원의 기록 — 본인이면 비공개 포함, 타인이면 공개 기록만 (서버가 거른다) */
export async function fetchUserLogs(id: number, cursor?: string): Promise<CursorPage<ClimbLog>> {
  const { data } = await api.get<RawCursorPage<ClimbLog>>(`/users/${id}/logs/`, {
    params: cursor ? { cursor } : undefined,
  })
  return toPage(data)
}
