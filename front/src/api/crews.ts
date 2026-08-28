import { getErrorCode, getErrorMessage, api } from '@/api/client'
import type { ClimbLog } from '@/api/climbs'
import { cursorFromLink, type CursorPage, type RawCursorPage } from '@/api/gyms'
import type { JoinType, PostSummary } from '@/api/posts'

// --- 읽기 모델 (backend crews.serializers) ---

export type CrewRole = 'owner' | 'staff' | 'member'
export const CREW_ROLE_LABEL: Record<CrewRole, string> = {
  owner: '크루장',
  staff: '운영진',
  member: '크루원',
}

/** 내 상태 — 활동 중이면 역할, 승인 대기면 pending, 미소속이면 null */
export type CrewMyStatus = CrewRole | 'pending'
export const CREW_MY_STATUS_LABEL: Record<CrewMyStatus, string> = {
  ...CREW_ROLE_LABEL,
  pending: '승인 대기',
}

/** 모집(recruit)의 선착순/승인제와 값은 같지만 크루에서는 "즉시 가입" 으로 읽힌다 */
export type CrewJoinType = JoinType
export const CREW_JOIN_TYPE_LABEL: Record<CrewJoinType, string> = {
  instant: '즉시 가입',
  approval: '승인제',
}

export type CrewMemberStatus = 'pending' | 'active'

export interface CrewRef {
  id: number
  name: string
}

export interface CrewOwner {
  id: number
  nickname: string
}

export interface CrewUser {
  id: number
  nickname: string
  image: string | null
}

/** 목록 항목 — description 은 100자 preview */
export interface CrewSummary {
  id: number
  name: string
  description: string
  /** 대표 이미지 공개 URL. 없으면 빈 문자열 */
  image: string
  homeGym: CrewRef | null
  owner: CrewOwner
  joinType: CrewJoinType
  /** 활동 중인 크루원 수 (크루장 포함) */
  memberCount: number
  maxMembers: number
  myStatus: CrewMyStatus | null
  createdAt: string
}

/** 상세 — 전체 소개 + 피드 공개 여부. chatRoomId 는 활동 중인 크루원에게만 */
export interface Crew extends CrewSummary {
  isFeedPublic: boolean
  chatRoomId: number | null
  updatedAt: string
}

export interface CrewMember {
  id: number
  user: CrewUser
  role: CrewRole
  status: CrewMemberStatus
  /** 활동 시작 시각. 승인 대기 중이면 null */
  joinedAt: string | null
  createdAt: string
}

// --- 입력 (CrewWriteSerializer) ---

export interface CrewInput {
  name: string
  description?: string
  image?: string
  homeGym?: number | null
  joinType: CrewJoinType
  maxMembers: number
  isFeedPublic: boolean
}

export type CrewUpdate = Partial<CrewInput>

export interface CrewListParams {
  q?: string
  gym?: number
  /** 홈짐 주소에 포함된 지역명 (예: 강남구) */
  region?: string
}

// --- 통계 / 랭킹 (crews.stats — 읽기 전용) ---

/** 크루원 활동 랭킹 한 줄. 동점은 같은 rank (1, 1, 3) */
export interface CrewMemberRank {
  rank: number
  user: CrewUser
  logCount: number
  successCount: number
}

/** 크루 월간 통계 — 활동 중 크루원들의 공개 기록만 집계 */
export interface CrewStats {
  /** YYYY-MM */
  month: string
  /** 활동 중 크루원 수 */
  memberCount: number
  /** 이 달 기록이 있는 크루원 수 */
  activeMemberCount: number
  logCount: number
  successCount: number
  /** 0~100, 소수 1자리 */
  successRate: number
  gymCount: number
  /** 완등 수 순 상위 10명 */
  ranking: CrewMemberRank[]
}

export interface RankedCrew {
  id: number
  name: string
  image: string | null
  homeGym: CrewRef | null
}

/** 전체 크루 랭킹 한 줄. 동점은 같은 rank */
export interface CrewRank {
  rank: number
  crew: RankedCrew
  memberCount: number
  logCount: number
  successCount: number
}

export const CREW_RANKING_DEFAULT_LIMIT = 20

/** backend crews.models 상수와 동일하게 유지 — 서버가 최종 판정 */
export const CREW_NAME_MAX_LENGTH = 30
export const CREW_DESCRIPTION_MAX_LENGTH = 2000
export const CREW_MAX_MEMBERS_MIN = 2
export const CREW_MAX_MEMBERS_MAX = 200
export const CREW_MAX_MEMBERS_DEFAULT = 30

export const isCrewFull = (crew: Pick<CrewSummary, 'memberCount' | 'maxMembers'>) =>
  crew.memberCount >= crew.maxMembers

/** 활동 중인 크루원(크루장·운영진·크루원) 인지 */
export const isActiveStatus = (status: CrewMyStatus | null): status is CrewRole =>
  status === 'owner' || status === 'staff' || status === 'member'

/** 크루장·운영진 — 수정·승인·강퇴 권한 */
export const isManagerStatus = (status: CrewMyStatus | null) =>
  status === 'owner' || status === 'staff'

/** 서버 error.code(crews.exceptions) → 사용자에게 보여줄 문장 */
const CREW_ERRORS: Record<string, string> = {
  crew_full: '크루 정원이 모두 찼어요.',
  already_member: '이미 가입했거나 승인 대기 중인 크루예요.',
  owner_cannot_leave: '크루장을 위임한 뒤 나갈 수 있어요.',
  not_crew_member: '가입한 크루가 아니에요.',
  cannot_change_owner: '크루장의 역할은 바꿀 수 없어요.',
  permission_denied: '권한이 없어요.',
}

export function crewErrorMessage(error: unknown, fallback: string): string {
  const code = getErrorCode(error)
  return (code && CREW_ERRORS[code]) || getErrorMessage(error, fallback)
}

function toPage<T>(data: RawCursorPage<T>): CursorPage<T> {
  return { results: data.results, nextCursor: cursorFromLink(data.nextCursor) }
}

// --- 크루 ---

export async function fetchCrews(
  params: CrewListParams = {},
  cursor?: string,
): Promise<CursorPage<CrewSummary>> {
  const { data } = await api.get<RawCursorPage<CrewSummary>>('/crews/', {
    params: { ...params, ...(cursor ? { cursor } : {}) },
  })
  return toPage(data)
}

export async function fetchCrew(id: number): Promise<Crew> {
  const { data } = await api.get<Crew>(`/crews/${id}/`)
  return data
}

/** 생성하면 단톡방과 크루장 소속이 같이 만들어진다 (201, 상세 형태) */
export async function createCrew(input: CrewInput): Promise<Crew> {
  const { data } = await api.post<Crew>('/crews/', input)
  return data
}

/** 크루장·운영진만 (403) */
export async function updateCrew(id: number, input: CrewUpdate): Promise<Crew> {
  const { data } = await api.patch<Crew>(`/crews/${id}/`, input)
  return data
}

/** 크루장만 (403). soft delete, 단톡방은 남는다 */
export async function deleteCrew(id: number): Promise<void> {
  await api.delete(`/crews/${id}/`)
}

// --- 가입 / 탈퇴 ---

/** instant 는 status=active, approval 은 pending 으로 돌아온다 (201) */
export async function joinCrew(id: number): Promise<CrewMember> {
  const { data } = await api.post<CrewMember>(`/crews/${id}/join/`)
  return data
}

/** 활동 중이면 탈퇴, 승인 대기 중이면 신청 취소. 크루장은 400 owner_cannot_leave */
export async function leaveCrew(id: number): Promise<void> {
  await api.delete(`/crews/${id}/leave/`)
}

/**
 * 크루장 위임 — 크루장만 (403). 대상은 활동 중인 크루원이어야 한다 (400 fields.user_id).
 * 응답은 상세와 같은 형태: owner 가 대상으로, 호출자의 my_status 는 staff 로 바뀐다.
 */
export async function transferCrewOwner(id: number, userId: number): Promise<Crew> {
  const { data } = await api.post<Crew>(`/crews/${id}/transfer/`, { userId })
  return data
}

// --- 통계 / 랭킹 ---

/** 크루 월간 통계. 권한은 피드와 같다 — 비공개 피드면 크루원만 (403 permission_denied) */
export async function fetchCrewStats(id: number, month?: string): Promise<CrewStats> {
  const { data } = await api.get<CrewStats>(`/crews/${id}/stats/`, {
    params: month ? { month } : undefined,
  })
  return data
}

/** 전체 크루 랭킹 — 그 달 공개 완등 수 순. 페이지네이션 없음 */
export async function fetchCrewRanking(
  month?: string,
  limit: number = CREW_RANKING_DEFAULT_LIMIT,
): Promise<CrewRank[]> {
  const { data } = await api.get<CrewRank[]>('/crews/ranking/', {
    params: { limit, ...(month ? { month } : {}) },
  })
  return data
}

// --- 크루원 (가입 순 커서) ---

/** pending 목록은 크루장·운영진만 (403) */
export async function fetchCrewMembers(
  id: number,
  status: CrewMemberStatus,
  cursor?: string,
): Promise<CursorPage<CrewMember>> {
  const { data } = await api.get<RawCursorPage<CrewMember>>(`/crews/${id}/members/`, {
    params: { status, ...(cursor ? { cursor } : {}) },
  })
  return toPage(data)
}

/** 승인 대기 신청 승인/거절 — 크루장·운영진 */
export async function setCrewMemberStatus(
  id: number,
  userId: number,
  status: 'active' | 'rejected',
): Promise<CrewMember> {
  const { data } = await api.patch<CrewMember>(`/crews/${id}/members/${userId}/`, { status })
  return data
}

/** 역할 변경 — 크루장만. 크루장 본인은 400 cannot_change_owner */
export async function setCrewMemberRole(
  id: number,
  userId: number,
  role: 'staff' | 'member',
): Promise<CrewMember> {
  const { data } = await api.patch<CrewMember>(`/crews/${id}/members/${userId}/`, { role })
  return data
}

/** 강퇴 — 크루장·운영진 (운영진은 크루원만) */
export async function kickCrewMember(id: number, userId: number): Promise<void> {
  await api.delete(`/crews/${id}/members/${userId}/`)
}

// --- 피드 / 모집 ---

/** 활동 중인 크루원들의 공개 기록. 크루원이 아니고 is_feed_public 도 아니면 403 permission_denied */
export async function fetchCrewFeed(id: number, cursor?: string): Promise<CursorPage<ClimbLog>> {
  const { data } = await api.get<RawCursorPage<ClimbLog>>(`/crews/${id}/feed/`, {
    params: cursor ? { cursor } : undefined,
  })
  return toPage(data)
}

/** 크루 주최 모집글 (최신순) */
export async function fetchCrewRecruitments(
  id: number,
  cursor?: string,
): Promise<CursorPage<PostSummary>> {
  const { data } = await api.get<RawCursorPage<PostSummary>>(`/crews/${id}/recruitments/`, {
    params: cursor ? { cursor } : undefined,
  })
  return toPage(data)
}
