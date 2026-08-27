import { getErrorCode, getErrorMessage, api } from '@/api/client'
import { cursorFromLink, type CursorPage, type RawCursorPage } from '@/api/gyms'

// --- 읽기 모델 (backend community.serializers) ---

export type PostCategory = 'free' | 'recruit'
export const POST_CATEGORIES: readonly PostCategory[] = ['free', 'recruit']
export const CATEGORY_LABEL: Record<PostCategory, string> = { free: '자유', recruit: '모집' }

export type JoinType = 'instant' | 'approval'
export const JOIN_TYPE_LABEL: Record<JoinType, string> = { instant: '선착순', approval: '승인제' }

export type RecruitmentStatus = 'open' | 'closed' | 'canceled'
export const RECRUITMENT_STATUS_LABEL: Record<RecruitmentStatus, string> = {
  open: '모집중',
  closed: '마감',
  canceled: '취소',
}

export type ParticipationStatus = 'pending' | 'approved' | 'rejected' | 'canceled'
export const PARTICIPATION_STATUS_LABEL: Record<ParticipationStatus, string> = {
  pending: '대기',
  approved: '승인',
  rejected: '거절',
  canceled: '취소',
}

/** 작성자/참여자 요약. image 는 프로필 이미지 URL, 없으면 null */
export interface PostUser {
  id: number
  nickname: string
  image: string | null
}

export interface PostGym {
  id: number
  name: string
}

/**
 * 모집 정보. capacity 는 작성자 포함 정원, approvedCount 는 작성자 제외 승인 인원.
 * 가득 참 = approvedCount + 1 >= capacity (services.is_full 과 같은 규칙)
 */
export interface Recruitment {
  id: number
  gym: PostGym
  /** ISO datetime */
  meetAt: string
  capacity: number
  joinType: JoinType
  status: RecruitmentStatus
  approvedCount: number
  myParticipationStatus: ParticipationStatus | null
  /** 마감 시 생성된 채팅방. 마감 전엔 null */
  chatRoomId: number | null
  /** 크루 주최 모집이면 그 크루. 개인 모집은 null */
  crew: { id: number; name: string } | null
}

interface PostBase {
  id: number
  user: PostUser
  category: PostCategory
  title: string
  gym: PostGym | null
  /** 첨부 이미지 공개 URL (presigned 업로드 결과), 노출 순서대로 */
  images: string[]
  commentCount: number
  viewCount: number
  /** category=recruit 일 때만 */
  recruitment: Recruitment | null
  createdAt: string
  updatedAt: string
}

/** 목록 항목 — 본문 대신 200자 preview */
export interface PostSummary extends PostBase {
  preview: string
}

/** 상세 — 본문 전체 */
export interface Post extends PostBase {
  content: string
}

export interface PostComment {
  id: number
  user: PostUser
  content: string
  /** 1단계 답글이면 부모 댓글 id */
  parent: number | null
  createdAt: string
}

export interface Participation {
  id: number
  user: PostUser
  status: ParticipationStatus
  createdAt: string
}

// --- 입력 (PostWriteSerializer / RecruitmentWriteSerializer) ---

export interface RecruitmentInput {
  gym: number
  /** 크루 주최 모집 — 요청자가 그 크루의 활동 멤버여야 한다 (400 not_crew_member) */
  crew?: number | null
  /** ISO datetime, 현재 이후 */
  meetAt: string
  capacity: number
  joinType: JoinType
}

export interface PostInput {
  category: PostCategory
  title: string
  content: string
  gym?: number | null
  images?: string[]
  /** 모집글에는 필수, 자유글에는 금지 */
  recruitment?: RecruitmentInput
}

/** PATCH — category 는 바꿀 수 없다. recruitment 는 바뀐 필드만 보내도 된다 */
export type PostUpdate = Partial<Omit<PostInput, 'category' | 'recruitment'>> & {
  recruitment?: Partial<RecruitmentInput>
}

export interface PostCommentInput {
  content: string
  parent?: number | null
}

export interface PostListParams {
  category?: PostCategory
  gym?: number
}

export const TITLE_MAX_LENGTH = 100
export const CONTENT_MAX_LENGTH = 5000
export const POST_COMMENT_MAX_LENGTH = 500
export const MAX_POST_IMAGES = 10
export const RECRUIT_CAPACITY_MIN = 2
export const RECRUIT_CAPACITY_MAX = 50
/** backend UPLOAD_KINDS["post_image"] 와 동일하게 유지 — 서버가 최종 판정 */
export const POST_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const

export function isRecruitmentFull(recruitment: Recruitment): boolean {
  return recruitment.approvedCount + 1 >= recruitment.capacity
}

/** 서버 error.code(community.exceptions) → 사용자에게 보여줄 문장 */
const RECRUITMENT_ERRORS: Record<string, string> = {
  recruitment_full: '정원이 모두 찼어요.',
  recruitment_closed: '이미 마감된 모집이에요.',
  already_joined: '이미 참여 신청한 모집이에요.',
  own_recruitment: '내가 만든 모집에는 참여할 수 없어요.',
  not_participating: '참여 중인 모집이 아니에요.',
}

export function recruitmentErrorMessage(error: unknown, fallback: string): string {
  const code = getErrorCode(error)
  return (code && RECRUITMENT_ERRORS[code]) || getErrorMessage(error, fallback)
}

function toPage<T>(data: RawCursorPage<T>): CursorPage<T> {
  return { results: data.results, nextCursor: cursorFromLink(data.nextCursor) }
}

// --- 게시글 ---

export async function fetchPosts(
  params: PostListParams = {},
  cursor?: string,
): Promise<CursorPage<PostSummary>> {
  const { data } = await api.get<RawCursorPage<PostSummary>>('/posts/', {
    params: { ...params, ...(cursor ? { cursor } : {}) },
  })
  return toPage(data)
}

export async function fetchPost(id: number): Promise<Post> {
  const { data } = await api.get<Post>(`/posts/${id}/`)
  return data
}

export async function createPost(input: PostInput): Promise<Post> {
  const { data } = await api.post<Post>('/posts/', input)
  return data
}

export async function updatePost(id: number, input: PostUpdate): Promise<Post> {
  const { data } = await api.patch<Post>(`/posts/${id}/`, input)
  return data
}

export async function deletePost(id: number): Promise<void> {
  await api.delete(`/posts/${id}/`)
}

// --- 댓글 (오래된 순 커서) ---

export async function fetchPostComments(
  postId: number,
  cursor?: string,
): Promise<CursorPage<PostComment>> {
  const { data } = await api.get<RawCursorPage<PostComment>>(`/posts/${postId}/comments/`, {
    params: cursor ? { cursor } : undefined,
  })
  return toPage(data)
}

export async function createPostComment(
  postId: number,
  input: PostCommentInput,
): Promise<PostComment> {
  const { data } = await api.post<PostComment>(`/posts/${postId}/comments/`, input)
  return data
}

export async function deletePostComment(postId: number, commentId: number): Promise<void> {
  await api.delete(`/posts/${postId}/comments/${commentId}/`)
}

// --- 모집 참여 ---

/** 선착순은 바로 approved, 승인제는 pending 으로 돌아온다 (201) */
export async function joinRecruitment(postId: number): Promise<Participation> {
  const { data } = await api.post<Participation>(`/posts/${postId}/recruitment/join/`)
  return data
}

export async function cancelParticipation(postId: number): Promise<void> {
  await api.delete(`/posts/${postId}/recruitment/cancel/`)
}

/** 작성자는 전체 상태, 나머지는 approved 만 내려온다 (오래된 순 커서) */
export async function fetchParticipants(
  postId: number,
  cursor?: string,
): Promise<CursorPage<Participation>> {
  const { data } = await api.get<RawCursorPage<Participation>>(
    `/posts/${postId}/recruitment/participants/`,
    { params: cursor ? { cursor } : undefined },
  )
  return toPage(data)
}

export async function setParticipantStatus(
  postId: number,
  userId: number,
  status: 'approved' | 'rejected',
): Promise<Participation> {
  const { data } = await api.patch<Participation>(
    `/posts/${postId}/recruitment/participants/${userId}/`,
    { status },
  )
  return data
}

/** 작성자 수동 마감 → 갱신된 recruitment 를 돌려준다 */
export async function closeRecruitment(postId: number): Promise<Recruitment> {
  const { data } = await api.post<Recruitment>(`/posts/${postId}/recruitment/close/`)
  return data
}
