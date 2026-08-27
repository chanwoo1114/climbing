import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { getErrorCode, getErrorMessage, getFieldError } from '@/api/client'
import {
  JOIN_TYPE_LABEL,
  PARTICIPATION_STATUS_LABEL,
  POST_COMMENT_MAX_LENGTH,
  isRecruitmentFull,
  recruitmentErrorMessage,
  type Participation,
  type ParticipationStatus,
  type Post,
  type PostComment,
  type Recruitment,
} from '@/api/posts'
import { formatRelativeDate } from '@/components/climbs/LogCard'
import Avatar from '@/components/common/Avatar'
import Button from '@/components/common/Button'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import TextArea from '@/components/common/TextArea'
import {
  CategoryBadge,
  RecruitmentStatusBadge,
  count,
  formatMeetAtLong,
  memberCount,
} from '@/components/community/PostBits'
import { useMe } from '@/hooks/useAuth'
import {
  useCancelParticipation,
  useCloseRecruitment,
  useCreatePostComment,
  useDeletePost,
  useDeletePostComment,
  useJoinRecruitment,
  useParticipants,
  usePost,
  usePostComments,
  useSetParticipantStatus,
} from '@/hooks/usePosts'

// 글자가 작은 인라인 액션(답글·삭제·취소)도 44px 터치 영역을 갖는다
const TEXT_ACTION =
  'inline-flex min-h-11 items-center px-2 text-xs font-medium transition-colors duration-150'

export default function PostDetail() {
  const { id } = useParams()
  const postId = Number(id)
  const validId = Number.isInteger(postId) && postId > 0
  const { data: post, isPending, isError, error } = usePost(validId ? postId : NaN)

  if (!validId || (isError && getErrorCode(error) === 'http_404')) {
    return <NotFound message="게시글을 찾을 수 없어요. 삭제된 글일 수 있어요." />
  }
  if (isPending) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (isError || !post) {
    return <NotFound message="게시글을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." />
  }
  return <PostDetailView post={post} />
}

function NotFound({ message }: { message: string }) {
  return (
    <div role="alert" className="py-10 text-center">
      <p className="text-sm text-pretty text-danger-500">{message}</p>
      <Link
        to="/posts"
        className="mt-2 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
      >
        게시판으로 돌아가기
      </Link>
    </div>
  )
}

function PostDetailView({ post }: { post: Post }) {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const remove = useDeletePost()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const myId = me?.id ?? null
  const isAuthor = myId === post.user.id
  const recruitment = post.recruitment

  // hold-500 은 화면당 하나 — "참여하기" 가 보이는 동안엔 댓글 제출이 secondary 로 물러난다
  const joinIsPrimary =
    recruitment !== null &&
    !isAuthor &&
    recruitment.status === 'open' &&
    recruitment.myParticipationStatus === null

  const onDelete = () => {
    remove.mutate(post.id, {
      onSuccess: () => navigate('/posts', { replace: true }),
    })
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Link
          to="/posts"
          className="-ml-2 inline-flex min-h-11 items-center px-2 text-sm font-medium text-ink-500 hover:text-ink-700"
        >
          <span aria-hidden className="mr-1">
            ←
          </span>
          게시판
        </Link>
        {isAuthor && (
          <div className="flex items-center gap-1">
            <Link
              to={`/posts/${post.id}/edit`}
              className={`${TEXT_ACTION} text-sm text-ink-500 hover:text-ink-700`}
            >
              수정
            </Link>
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className={`${TEXT_ACTION} -mr-2 text-sm text-danger-500 hover:text-danger-600`}
            >
              삭제
            </button>
          </div>
        )}
      </div>

      <article
        aria-labelledby="post-title"
        className="rounded-card border border-chalk-300 bg-white p-4 md:p-5"
      >
        <div className="flex items-center gap-2">
          <CategoryBadge category={post.category} />
          {recruitment && <RecruitmentStatusBadge recruitment={recruitment} />}
        </div>
        <h1 id="post-title" className="mt-2 text-xl font-semibold break-words text-ink-700">
          {post.title}
        </h1>

        <header className="mt-3 flex items-center gap-3">
          {/* 아바타는 닉네임 링크와 같은 곳으로 가는 터치 영역 — 키보드 탭 순서에선 닉네임만 */}
          <Link to={`/users/${post.user.id}`} tabIndex={-1} className="-m-0.5 shrink-0 rounded-full p-0.5">
            <Avatar user={post.user} />
          </Link>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink-700">
              <Link to={`/users/${post.user.id}`} className="hover:underline">
                {post.user.nickname}
              </Link>
            </p>
            <p className="flex flex-wrap items-center gap-x-2 text-xs text-ink-400">
              <time dateTime={post.createdAt}>{formatRelativeDate(post.createdAt)}</time>
              <span className="tabular-nums">조회 {count.format(post.viewCount)}</span>
            </p>
          </div>
          {post.gym && (
            <Link
              to={`/gyms/${post.gym.id}`}
              className="inline-flex min-h-11 max-w-[40%] items-center truncate text-sm font-medium text-hold-600 hover:underline"
            >
              {post.gym.name}
            </Link>
          )}
        </header>

        <p className="mt-4 text-sm leading-relaxed whitespace-pre-wrap break-words text-ink-600">
          {post.content}
        </p>

        {post.images.length > 0 && (
          <ul aria-label="첨부 이미지" className="-mx-4 mt-4 flex gap-2 overflow-x-auto px-4 md:-mx-5 md:px-5">
            {post.images.map((url, index) => (
              <li key={`${index}-${url}`} className="shrink-0">
                <a href={url} target="_blank" rel="noreferrer" className="block rounded-xl">
                  <img
                    src={url}
                    alt={`첨부 이미지 ${index + 1}`}
                    loading="lazy"
                    className="h-40 max-w-64 rounded-xl bg-chalk-200 object-cover"
                  />
                </a>
              </li>
            ))}
          </ul>
        )}
      </article>

      {remove.isError && (
        <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {getErrorMessage(remove.error, '게시글을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
      )}

      {recruitment && (
        <RecruitmentPanel
          postId={post.id}
          recruitment={recruitment}
          isAuthor={isAuthor}
          joinIsPrimary={joinIsPrimary}
        />
      )}

      <Comments post={post} myId={myId} submitVariant={joinIsPrimary ? 'secondary' : 'primary'} />

      <ConfirmDialog
        open={confirmDelete}
        title="이 게시글을 삭제할까요?"
        description={
          recruitment
            ? '모집 정보와 댓글도 함께 사라지며 되돌릴 수 없어요.'
            : '댓글도 함께 사라지며 되돌릴 수 없어요.'
        }
        confirmLabel="삭제"
        pendingLabel="삭제 중…"
        pending={remove.isPending}
        onConfirm={onDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  )
}

// --- 모집 ---

function RecruitmentPanel({
  postId,
  recruitment,
  isAuthor,
  joinIsPrimary,
}: {
  postId: number
  recruitment: Recruitment
  isAuthor: boolean
  joinIsPrimary: boolean
}) {
  const join = useJoinRecruitment(postId)
  const cancel = useCancelParticipation(postId)
  const close = useCloseRecruitment(postId)
  const [confirmClose, setConfirmClose] = useState(false)

  const open = recruitment.status === 'open'
  const full = isRecruitmentFull(recruitment)
  const mine = recruitment.myParticipationStatus
  const members = memberCount(recruitment)
  const ratio = Math.min(1, members / recruitment.capacity)
  const canOpenChat =
    recruitment.chatRoomId !== null && (isAuthor || mine === 'approved')

  // 마지막으로 실패한 액션의 메시지만 보여준다
  const actionError =
    (join.isError && recruitmentErrorMessage(join.error, '참여 신청을 하지 못했습니다.')) ||
    (cancel.isError && recruitmentErrorMessage(cancel.error, '참여를 취소하지 못했습니다.')) ||
    (close.isError && recruitmentErrorMessage(close.error, '모집을 마감하지 못했습니다.')) ||
    null
  const busy = join.isPending || cancel.isPending || close.isPending

  return (
    <section
      aria-labelledby="recruitment-heading"
      className="space-y-4 rounded-card border border-chalk-300 bg-white p-4 md:p-5"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 id="recruitment-heading" className="text-base font-semibold text-ink-700">
          투어 모집
        </h2>
        <RecruitmentStatusBadge recruitment={recruitment} />
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-ink-400">암장</dt>
        <dd className="min-w-0">
          <Link
            to={`/gyms/${recruitment.gym.id}`}
            className="-my-2 inline-flex min-h-11 max-w-full items-center truncate font-medium text-hold-600 hover:underline"
          >
            {recruitment.gym.name}
          </Link>
        </dd>
        {recruitment.crew && (
          <>
            <dt className="text-ink-400">주최 크루</dt>
            <dd className="min-w-0">
              <Link
                to={`/crews/${recruitment.crew.id}`}
                className="-my-2 inline-flex min-h-11 max-w-full items-center truncate font-medium text-hold-600 hover:underline"
              >
                {recruitment.crew.name}
              </Link>
            </dd>
          </>
        )}
        <dt className="text-ink-400">모임 일시</dt>
        <dd className="text-ink-600 tabular-nums">
          <time dateTime={recruitment.meetAt}>{formatMeetAtLong(recruitment.meetAt)}</time>
        </dd>
        <dt className="text-ink-400">참여 방식</dt>
        <dd className="text-ink-600">
          {JOIN_TYPE_LABEL[recruitment.joinType]}
          <span className="ml-1 text-xs text-ink-400">
            {recruitment.joinType === 'instant' ? '— 신청 즉시 확정' : '— 작성자가 승인'}
          </span>
        </dd>
        <dt className="text-ink-400">인원</dt>
        <dd>
          <span className="text-ink-600 tabular-nums">
            {count.format(members)}/{count.format(recruitment.capacity)}명
          </span>
          <span className="ml-1 text-xs text-ink-400">(작성자 포함)</span>
          <div
            role="progressbar"
            aria-label="모집 인원"
            aria-valuemin={0}
            aria-valuemax={recruitment.capacity}
            aria-valuenow={members}
            className="mt-1.5 h-1.5 w-full max-w-60 overflow-hidden rounded-full bg-chalk-200"
          >
            <div
              className="h-full origin-left rounded-full bg-ochre-400 transition-transform duration-150 ease-out"
              style={{ transform: `scaleX(${ratio})` }}
            />
          </div>
        </dd>
      </dl>

      {/* 상태별 액션 */}
      <div className="flex flex-wrap items-center gap-2">
        {isAuthor ? (
          open ? (
            <Button variant="secondary" onClick={() => setConfirmClose(true)} disabled={busy}>
              모집 마감
            </Button>
          ) : (
            <Button variant="secondary" disabled>
              {recruitment.status === 'closed' ? '마감됨' : '취소됨'}
            </Button>
          )
        ) : mine === 'pending' ? (
          <>
            <span role="status" className="text-sm font-medium text-ink-600">
              승인 대기중
            </span>
            {open && (
              <Button variant="secondary" onClick={() => cancel.mutate()} disabled={busy}>
                {cancel.isPending ? '취소하는 중…' : '신청 취소'}
              </Button>
            )}
          </>
        ) : mine === 'approved' ? (
          <>
            <span role="status" className="text-sm font-medium text-moss-500">
              참여 확정
            </span>
            {open && (
              <Button variant="secondary" onClick={() => cancel.mutate()} disabled={busy}>
                {cancel.isPending ? '취소하는 중…' : '참여 취소'}
              </Button>
            )}
          </>
        ) : mine === 'rejected' ? (
          <span role="status" className="text-sm font-medium text-ink-500">
            참여가 거절됐어요
          </span>
        ) : open ? (
          // 이 페이지의 유일한 primary CTA (joinIsPrimary 일 때)
          <Button
            variant={joinIsPrimary ? 'primary' : 'secondary'}
            onClick={() => join.mutate()}
            disabled={busy || full}
          >
            {join.isPending
              ? '신청하는 중…'
              : full
                ? '정원 마감'
                : recruitment.joinType === 'instant'
                  ? '참여하기'
                  : '참여 신청하기'}
          </Button>
        ) : (
          <Button variant="secondary" disabled>
            마감
          </Button>
        )}

        {canOpenChat && (
          <Link
            to={`/chat/rooms/${recruitment.chatRoomId}`}
            className="inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
          >
            채팅방 열기
          </Link>
        )}
      </div>

      {actionError && (
        <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {actionError}
        </p>
      )}
      {recruitment.status === 'closed' && !canOpenChat && mine === 'pending' && (
        <p role="status" className="text-xs text-pretty text-ink-400">
          마감된 모집이라 더 이상 승인되지 않아요.
        </p>
      )}

      <Participants postId={postId} recruitment={recruitment} isAuthor={isAuthor} />

      <ConfirmDialog
        open={confirmClose}
        title="모집을 마감할까요?"
        description="마감하면 더 이상 참여 신청을 받지 않고, 확정된 참여자들과 채팅방이 열려요. 되돌릴 수 없어요."
        confirmLabel="마감"
        pendingLabel="마감하는 중…"
        variant="primary"
        pending={close.isPending}
        onConfirm={() => close.mutate(undefined, { onSuccess: () => setConfirmClose(false) })}
        onCancel={() => setConfirmClose(false)}
      />
    </section>
  )
}

const PARTICIPATION_CLASS: Record<ParticipationStatus, string> = {
  pending: 'bg-ochre-100 text-ochre-500',
  approved: 'bg-moss-100 text-moss-500',
  rejected: 'bg-chalk-200 text-ink-500',
  canceled: 'bg-chalk-200 text-ink-500',
}

/** 참여자 목록 — 작성자는 전체 상태(승인/거절 가능), 나머지는 확정된 사람만 본다 */
function Participants({
  postId,
  recruitment,
  isAuthor,
}: {
  postId: number
  recruitment: Recruitment
  isAuthor: boolean
}) {
  const participants = useParticipants(postId)
  const rows = participants.data?.pages.flatMap((page) => page.results) ?? []
  const setStatus = useSetParticipantStatus(postId)
  const canDecide = isAuthor && recruitment.status === 'open'
  const decidingUserId = setStatus.isPending ? setStatus.variables?.userId : undefined

  return (
    <div>
      <h3 className="text-sm font-medium text-ink-500">
        {isAuthor ? '참여 신청' : '확정된 참여자'}{' '}
        {participants.data && (
          <span className="font-normal text-ink-400 tabular-nums">{count.format(rows.length)}명</span>
        )}
      </h3>

      {participants.isPending && (
        <p role="status" className="mt-2 text-sm text-ink-400">
          참여자를 불러오는 중…
        </p>
      )}
      {participants.isError && (
        <p role="alert" className="mt-2 text-sm text-danger-500">
          참여자 목록을 불러오지 못했습니다.
        </p>
      )}
      {participants.data && rows.length === 0 && (
        <p className="mt-2 text-sm text-pretty text-ink-400">
          {isAuthor ? '아직 신청한 사람이 없어요.' : '아직 확정된 참여자가 없어요.'}
        </p>
      )}

      {rows.length > 0 && (
        <ul className="mt-2 divide-y divide-chalk-200">
          {rows.map((row) => (
            <li key={row.id} className="flex items-center gap-3 py-2">
              <ParticipantRow
                participation={row}
                showStatus={isAuthor}
                decidable={canDecide && row.status === 'pending'}
                deciding={decidingUserId === row.user.id}
                disabled={setStatus.isPending}
                onDecide={(status) => setStatus.mutate({ userId: row.user.id, status })}
              />
            </li>
          ))}
        </ul>
      )}

      {participants.hasNextPage && (
        <Button
          variant="secondary"
          full
          className="mt-2"
          onClick={() => participants.fetchNextPage()}
          disabled={participants.isFetchingNextPage}
        >
          {participants.isFetchingNextPage ? '불러오는 중…' : '참여자 더 보기'}
        </Button>
      )}
      {setStatus.isError && (
        <p role="alert" className="mt-2 rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {recruitmentErrorMessage(setStatus.error, '처리하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
      )}
    </div>
  )
}

function ParticipantRow({
  participation,
  showStatus,
  decidable,
  deciding,
  disabled,
  onDecide,
}: {
  participation: Participation
  showStatus: boolean
  decidable: boolean
  deciding: boolean
  disabled: boolean
  onDecide: (status: 'approved' | 'rejected') => void
}) {
  const { user, status } = participation
  return (
    <>
      <Link to={`/users/${user.id}`} tabIndex={-1} className="-m-1.5 shrink-0 rounded-full p-1.5">
        <Avatar user={user} size="sm" />
      </Link>
      <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink-700">
        <Link to={`/users/${user.id}`} className="hover:underline">
          {user.nickname}
        </Link>
      </span>
      {showStatus && (
        <span
          className={`shrink-0 rounded-xl px-2 py-0.5 text-xs font-medium ${PARTICIPATION_CLASS[status]}`}
        >
          {PARTICIPATION_STATUS_LABEL[status]}
        </span>
      )}
      {decidable && (
        <span className="flex shrink-0 items-center gap-1">
          <Button
            variant="secondary"
            className="text-sm"
            onClick={() => onDecide('approved')}
            disabled={disabled}
          >
            {deciding ? '처리 중…' : '승인'}
          </Button>
          <Button
            variant="secondary"
            className="text-sm"
            onClick={() => onDecide('rejected')}
            disabled={disabled}
          >
            거절
          </Button>
        </span>
      )}
    </>
  )
}

// --- 댓글 ---

interface Thread {
  comment: PostComment
  replies: PostComment[]
}

/**
 * 오래된 순 목록을 1단계 스레드로 묶는다. 부모는 항상 답글보다 먼저 만들어졌으니
 * 먼저 등장한다. 부모가 삭제돼 목록에 없는 답글은 최상위로 올린다.
 */
function toThreads(comments: PostComment[]): Thread[] {
  const threads: Thread[] = []
  const byId = new Map<number, Thread>()
  for (const comment of comments) {
    const parent = comment.parent === null ? undefined : byId.get(comment.parent)
    if (parent) {
      parent.replies.push(comment)
    } else {
      const thread = { comment, replies: [] }
      byId.set(comment.id, thread)
      threads.push(thread)
    }
  }
  return threads
}

function Comments({
  post,
  myId,
  submitVariant,
}: {
  post: Post
  myId: number | null
  submitVariant: 'primary' | 'secondary'
}) {
  const comments = usePostComments(post.id)
  const loaded = comments.data?.pages.flatMap((page) => page.results) ?? []
  const threads = toThreads(loaded)
  const [replyTo, setReplyTo] = useState<PostComment | null>(null)
  const [pendingDelete, setPendingDelete] = useState<PostComment | null>(null)
  const remove = useDeletePostComment(post.id)

  const onDelete = () => {
    if (!pendingDelete) return
    remove.mutate(pendingDelete.id, {
      onSuccess: () => {
        if (replyTo?.id === pendingDelete.id) setReplyTo(null)
        setPendingDelete(null)
      },
    })
  }

  return (
    <section id="comments" aria-labelledby="comments-heading" className="scroll-mt-4 space-y-3">
      <h2 id="comments-heading" className="text-base font-semibold text-ink-700">
        댓글{' '}
        <span className="font-medium text-ink-400 tabular-nums">
          {count.format(post.commentCount)}개
        </span>
      </h2>

      {comments.isPending && (
        <p role="status" className="text-sm text-ink-400">
          댓글을 불러오는 중…
        </p>
      )}
      {comments.isError && (
        <p role="alert" className="text-sm text-danger-500">
          댓글을 불러오지 못했습니다. 잠시 후 새로고침해 주세요.
        </p>
      )}
      {comments.data && threads.length === 0 && (
        <div className="rounded-card border border-chalk-300 bg-white p-6 text-center">
          <p className="text-sm font-medium text-ink-600">아직 댓글이 없어요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">첫 댓글을 남겨보세요.</p>
        </div>
      )}
      {threads.length > 0 && (
        <ul className="space-y-2">
          {threads.map(({ comment, replies }) => (
            <li key={comment.id} className="rounded-card border border-chalk-300 bg-white p-4">
              <CommentItem
                comment={comment}
                mine={comment.user.id === myId}
                onReply={() => setReplyTo(comment)}
                onDelete={() => setPendingDelete(comment)}
              />
              {replies.length > 0 && (
                <ul className="mt-2 space-y-2 border-l-2 border-chalk-200 pl-3">
                  {replies.map((reply) => (
                    <li key={reply.id}>
                      <CommentItem
                        comment={reply}
                        mine={reply.user.id === myId}
                        onDelete={() => setPendingDelete(reply)}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
      {comments.hasNextPage && (
        <Button
          variant="secondary"
          full
          onClick={() => comments.fetchNextPage()}
          disabled={comments.isFetchingNextPage}
        >
          {comments.isFetchingNextPage ? '불러오는 중…' : '댓글 더 보기'}
        </Button>
      )}
      {remove.isError && (
        <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {getErrorMessage(remove.error, '댓글을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
      )}

      <CommentForm
        postId={post.id}
        replyTo={replyTo}
        onCancelReply={() => setReplyTo(null)}
        submitVariant={submitVariant}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="이 댓글을 삭제할까요?"
        description={
          pendingDelete && pendingDelete.parent === null
            ? '달린 답글도 함께 사라지며 되돌릴 수 없어요.'
            : '삭제한 댓글은 되돌릴 수 없어요.'
        }
        confirmLabel="삭제"
        pendingLabel="삭제 중…"
        pending={remove.isPending}
        onConfirm={onDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </section>
  )
}

function CommentItem({
  comment,
  mine,
  onReply,
  onDelete,
}: {
  comment: PostComment
  mine: boolean
  /** 최상위 댓글에만 — 답글에는 다시 답글을 달 수 없다 (서버 규칙) */
  onReply?: () => void
  onDelete: () => void
}) {
  return (
    <article className="flex gap-3">
      <Link
        to={`/users/${comment.user.id}`}
        tabIndex={-1}
        className="-m-1.5 self-start rounded-full p-1.5"
      >
        <Avatar user={comment.user} size="sm" />
      </Link>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="min-w-0 truncate text-sm font-medium text-ink-700">
            <Link to={`/users/${comment.user.id}`} className="hover:underline">
              {comment.user.nickname}
            </Link>
          </span>
          <time
            dateTime={comment.createdAt}
            className="shrink-0 text-xs text-ink-400 tabular-nums"
          >
            {formatRelativeDate(comment.createdAt)}
          </time>
        </div>
        <p className="mt-0.5 text-sm whitespace-pre-line text-pretty break-words text-ink-600">
          {comment.content}
        </p>
        <div className="-mb-3 -ml-2 flex items-center">
          {onReply && (
            <button
              type="button"
              onClick={onReply}
              className={`${TEXT_ACTION} text-ink-400 hover:text-ink-600`}
            >
              답글
            </button>
          )}
          {mine && (
            <button
              type="button"
              onClick={onDelete}
              className={`${TEXT_ACTION} text-danger-500 hover:text-danger-600`}
            >
              삭제
            </button>
          )}
        </div>
      </div>
    </article>
  )
}

function CommentForm({
  postId,
  replyTo,
  onCancelReply,
  submitVariant,
}: {
  postId: number
  replyTo: PostComment | null
  onCancelReply: () => void
  submitVariant: 'primary' | 'secondary'
}) {
  const create = useCreatePostComment(postId)
  const [content, setContent] = useState('')
  const formRef = useRef<HTMLFormElement>(null)

  // "답글" 을 누르면 입력칸으로 포커스를 옮긴다
  useEffect(() => {
    if (replyTo) formRef.current?.querySelector('textarea')?.focus()
  }, [replyTo])

  const error = create.error
  const contentError = getFieldError(error, 'content')
  const parentError = getFieldError(error, 'parent')
  const generalError =
    error && !contentError && !parentError
      ? getErrorMessage(error, '댓글을 남기지 못했습니다. 잠시 후 다시 시도해 주세요.')
      : null

  const trimmed = content.trim()
  const canSubmit = trimmed.length > 0 && content.length <= POST_COMMENT_MAX_LENGTH
  const pending = create.isPending

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || pending) return
    create.mutate(
      { content: trimmed, parent: replyTo?.id ?? null },
      {
        onSuccess: () => {
          setContent('')
          onCancelReply()
        },
      },
    )
  }

  return (
    <form
      ref={formRef}
      onSubmit={onSubmit}
      noValidate
      className="space-y-3 rounded-card border border-chalk-300 bg-white p-4"
    >
      {replyTo && (
        <p
          role="status"
          className="flex items-center justify-between gap-2 rounded-xl bg-chalk-100 px-3 py-1 text-xs text-ink-500"
        >
          <span className="min-w-0 truncate">
            <span className="font-medium text-ink-700">{replyTo.user.nickname}</span>님에게 답글
          </span>
          <button
            type="button"
            onClick={onCancelReply}
            className={`${TEXT_ACTION} -mr-2 shrink-0 text-ink-400 hover:text-ink-600`}
          >
            취소
          </button>
        </p>
      )}
      <TextArea
        label={replyTo ? '답글' : '댓글'}
        name="content"
        placeholder={replyTo ? '답글을 남겨보세요' : '댓글을 남겨보세요'}
        maxLength={POST_COMMENT_MAX_LENGTH}
        showCount
        value={content}
        check={
          contentError || parentError
            ? { state: 'invalid', message: contentError ?? parentError ?? '' }
            : undefined
        }
        onChange={(e) => {
          if (create.isError) create.reset()
          setContent(e.target.value)
        }}
        disabled={pending}
      />
      {generalError && (
        <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {generalError}
        </p>
      )}
      {/* "참여하기" 가 없는 화면에선 이 버튼이 유일한 primary CTA */}
      <Button type="submit" variant={submitVariant} full disabled={!canSubmit || pending}>
        {pending ? '남기는 중…' : replyTo ? '답글 남기기' : '댓글 남기기'}
      </Button>
    </form>
  )
}
