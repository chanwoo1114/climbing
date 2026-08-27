import { api } from '@/api/client'
import { cursorFromLink, type CursorPage, type RawCursorPage } from '@/api/gyms'

// --- 읽기 모델 (backend climbs.serializers.ClimbLogSerializer) ---

/** 피드 카드용 작성자 요약. image 는 프로필 이미지 URL, 없으면 null */
export interface LogUser {
  id: number
  nickname: string
  image: string | null
}

export interface LogGym {
  id: number
  name: string
}

/** 색은 토큰이 아니라 암장이 정한 값(GymDifficulty.color) 그대로 렌더링한다 */
export interface LogDifficulty {
  id: number
  name: string
  color: string
}

export interface ClimbLog {
  id: number
  user: LogUser
  gym: LogGym
  difficulty: LogDifficulty | null
  isSuccess: boolean
  attempts: number
  memo: string
  /** presigned 업로드 후 저장된 공개 URL. 없으면 빈 문자열 */
  videoUrl: string
  /** YYYY-MM-DD */
  climbedAt: string
  isShared: boolean
  likeCount: number
  commentCount: number
  isLiked: boolean
  createdAt: string
}

/** POST logs/ 입력 (ClimbLogWriteSerializer). PATCH 는 Partial */
export interface ClimbLogInput {
  gym: number
  difficulty: number | null
  isSuccess: boolean
  attempts: number
  memo: string
  videoUrl: string
  climbedAt: string
  isShared: boolean
}

export interface ClimbLogComment {
  id: number
  user: LogUser
  content: string
  /** 1단계 답글이면 부모 댓글 id */
  parent: number | null
  createdAt: string
}

export interface ClimbLogCommentInput {
  content: string
  parent?: number | null
}

export type FeedScope = 'explore' | 'following'
export const FEED_SCOPES: readonly FeedScope[] = ['explore', 'following']

export interface MyLogsParams {
  gym?: number
  isSuccess?: boolean
}

export const MEMO_MAX_LENGTH = 1000
export const COMMENT_MAX_LENGTH = 500

function toPage<T>(data: RawCursorPage<T>): CursorPage<T> {
  return { results: data.results, nextCursor: cursorFromLink(data.nextCursor) }
}

// --- 피드 / 내 기록 ---

export async function fetchFeed(scope: FeedScope, cursor?: string): Promise<CursorPage<ClimbLog>> {
  const { data } = await api.get<RawCursorPage<ClimbLog>>('/feed/', {
    params: { scope, ...(cursor ? { cursor } : {}) },
  })
  return toPage(data)
}

export async function fetchMyLogs(
  params: MyLogsParams = {},
  cursor?: string,
): Promise<CursorPage<ClimbLog>> {
  const { data } = await api.get<RawCursorPage<ClimbLog>>('/logs/', {
    params: { ...params, ...(cursor ? { cursor } : {}) },
  })
  return toPage(data)
}

// --- 기록 CRUD ---

export async function fetchLog(id: number): Promise<ClimbLog> {
  const { data } = await api.get<ClimbLog>(`/logs/${id}/`)
  return data
}

export async function createLog(input: ClimbLogInput): Promise<ClimbLog> {
  const { data } = await api.post<ClimbLog>('/logs/', input)
  return data
}

export async function updateLog(id: number, input: Partial<ClimbLogInput>): Promise<ClimbLog> {
  const { data } = await api.patch<ClimbLog>(`/logs/${id}/`, input)
  return data
}

export async function deleteLog(id: number): Promise<void> {
  await api.delete(`/logs/${id}/`)
}

// --- 좋아요 (204, 멱등) ---

export async function likeLog(id: number): Promise<void> {
  await api.post(`/logs/${id}/like/`)
}

export async function unlikeLog(id: number): Promise<void> {
  await api.delete(`/logs/${id}/like/`)
}

// --- 댓글 (오래된 순 커서) ---

export async function fetchLogComments(
  logId: number,
  cursor?: string,
): Promise<CursorPage<ClimbLogComment>> {
  const { data } = await api.get<RawCursorPage<ClimbLogComment>>(`/logs/${logId}/comments/`, {
    params: cursor ? { cursor } : undefined,
  })
  return toPage(data)
}

export async function createLogComment(
  logId: number,
  input: ClimbLogCommentInput,
): Promise<ClimbLogComment> {
  const { data } = await api.post<ClimbLogComment>(`/logs/${logId}/comments/`, input)
  return data
}

export async function deleteLogComment(logId: number, commentId: number): Promise<void> {
  await api.delete(`/logs/${logId}/comments/${commentId}/`)
}
