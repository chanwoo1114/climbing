import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from '@tanstack/react-query'

import type { CursorPage } from '@/api/gyms'
import {
  cancelParticipation,
  closeRecruitment,
  createPost,
  createPostComment,
  deletePost,
  deletePostComment,
  fetchParticipants,
  fetchPost,
  fetchPostComments,
  fetchPosts,
  joinRecruitment,
  setParticipantStatus,
  updatePost,
  type Participation,
  type Post,
  type PostCommentInput,
  type PostInput,
  type PostListParams,
  type PostSummary,
  type PostUpdate,
} from '@/api/posts'

/**
 * 쿼리 키
 * - ['posts', 'list', params]        목록 (무한) — category/gym 별
 * - ['posts', id]                    상세
 * - ['posts', id, 'comments']        댓글 (무한)
 * - ['posts', id, 'participants']    모집 참여자 (무한)
 * ['posts', id] 무효화에 댓글·참여자가 같이 딸려간다.
 */
const listKey = (params: PostListParams) => ['posts', 'list', params] as const
const postKey = (id: number) => ['posts', id] as const
const commentsKey = (id: number) => ['posts', id, 'comments'] as const
const participantsKey = (id: number) => ['posts', id, 'participants'] as const

/** 목록 캐시 전부 (category/gym 조합 무관) */
const POST_LISTS = { queryKey: ['posts', 'list'] }

type PostPages = InfiniteData<CursorPage<PostSummary>, string | undefined>

/** 같은 글이 목록·상세 캐시에 동시에 있을 수 있어 댓글 수 같은 값은 둘 다 고친다 */
function patchPostEverywhere(
  queryClient: QueryClient,
  id: number,
  patch: <T extends Pick<Post, 'commentCount'>>(post: T) => T,
) {
  queryClient.setQueriesData<PostPages>(
    POST_LISTS,
    (pages) =>
      pages && {
        ...pages,
        pages: pages.pages.map((page) => ({
          ...page,
          results: page.results.map((post) => (post.id === id ? patch(post) : post)),
        })),
      },
  )
  queryClient.setQueryData<Post>(postKey(id), (post) => post && patch(post))
}

// --- 조회 ---

export function usePosts(params: PostListParams = {}) {
  return useInfiniteQuery({
    queryKey: listKey(params),
    queryFn: ({ pageParam }) => fetchPosts(params, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  })
}

export function usePost(id: number) {
  return useQuery({
    queryKey: postKey(id),
    queryFn: () => fetchPost(id),
    enabled: Number.isFinite(id),
  })
}

// --- 게시글 CRUD ---

export function useCreatePost() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: PostInput) => createPost(input),
    onSuccess: (post) => {
      // 상세로 바로 이동하므로 응답을 캐시에 미리 넣어 두면 로딩 없이 뜬다
      queryClient.setQueryData(postKey(post.id), post)
      queryClient.invalidateQueries(POST_LISTS)
    },
  })
}

export function useUpdatePost(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: PostUpdate) => updatePost(id, input),
    onSuccess: (post) => {
      queryClient.setQueryData(postKey(post.id), post)
      queryClient.invalidateQueries(POST_LISTS)
    },
  })
}

export function useDeletePost() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deletePost(id),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: postKey(id) })
      queryClient.invalidateQueries(POST_LISTS)
    },
  })
}

// --- 댓글 ---

export function usePostComments(postId: number) {
  return useInfiniteQuery({
    queryKey: commentsKey(postId),
    queryFn: ({ pageParam }) => fetchPostComments(postId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    enabled: Number.isFinite(postId),
  })
}

export function useCreatePostComment(postId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: PostCommentInput) => createPostComment(postId, input),
    onSuccess: () => {
      patchPostEverywhere(queryClient, postId, (post) => ({
        ...post,
        commentCount: post.commentCount + 1,
      }))
      // 오래된 순이라 새 댓글은 마지막 페이지 뒤 — 목록을 다시 받는다
      queryClient.invalidateQueries({ queryKey: commentsKey(postId) })
    },
  })
}

export function useDeletePostComment(postId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (commentId: number) => deletePostComment(postId, commentId),
    onSuccess: () => {
      // 답글도 함께 지워지므로 정확한 수는 서버 집계에 맡기고 목록·상세를 다시 받는다
      queryClient.invalidateQueries({ queryKey: postKey(postId) })
      queryClient.invalidateQueries(POST_LISTS)
    },
  })
}

// --- 모집 ---

/** 참여자 목록. 작성자는 전체 상태, 나머지는 approved 만 온다 */
export function useParticipants(postId: number, enabled = true) {
  return useInfiniteQuery({
    queryKey: participantsKey(postId),
    queryFn: ({ pageParam }) => fetchParticipants(postId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    enabled: enabled && Number.isFinite(postId),
  })
}

/**
 * 참여/취소/승인/마감은 approved_count·my_participation_status·status 가 한꺼번에 바뀌고
 * 정원이 차면 서버가 자동 마감까지 하므로, 상세(+참여자)와 목록을 통째로 다시 받는다.
 */
function useRecruitmentMutation<TVariables, TData>(
  postId: number,
  mutationFn: (variables: TVariables) => Promise<TData>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: postKey(postId) })
      queryClient.invalidateQueries(POST_LISTS)
    },
  })
}

export function useJoinRecruitment(postId: number) {
  return useRecruitmentMutation<void, Participation>(postId, () => joinRecruitment(postId))
}

export function useCancelParticipation(postId: number) {
  return useRecruitmentMutation<void, void>(postId, () => cancelParticipation(postId))
}

export function useSetParticipantStatus(postId: number) {
  return useRecruitmentMutation(
    postId,
    ({ userId, status }: { userId: number; status: 'approved' | 'rejected' }) =>
      setParticipantStatus(postId, userId, status),
  )
}

export function useCloseRecruitment(postId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => closeRecruitment(postId),
    onSuccess: (recruitment) => {
      // 응답이 갱신된 recruitment 라 상세는 바로 바꾸고, 참여자·목록은 다시 받는다
      queryClient.setQueryData<Post>(postKey(postId), (post) => post && { ...post, recruitment })
      queryClient.invalidateQueries({ queryKey: participantsKey(postId) })
      queryClient.invalidateQueries(POST_LISTS)
    },
  })
}
