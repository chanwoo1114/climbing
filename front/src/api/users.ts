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

/** 회원의 기록 — 본인이면 비공개 포함, 타인이면 공개 기록만 (서버가 거른다) */
export async function fetchUserLogs(id: number, cursor?: string): Promise<CursorPage<ClimbLog>> {
  const { data } = await api.get<RawCursorPage<ClimbLog>>(`/users/${id}/logs/`, {
    params: cursor ? { cursor } : undefined,
  })
  return toPage(data)
}
