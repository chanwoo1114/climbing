import { useEffect, useRef, useState, type FormEvent, type Ref } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'

import { COMMENT_MAX_LENGTH, type ClimbLog, type ClimbLogComment } from '@/api/climbs'
import { getErrorCode, getErrorMessage, getFieldError } from '@/api/client'
import AnalysisPanel from '@/components/analysis/AnalysisPanel'
import LogCard, { formatRelativeDate } from '@/components/climbs/LogCard'
import Avatar from '@/components/common/Avatar'
import Button from '@/components/common/Button'
import TextArea from '@/components/common/TextArea'
import { useMe } from '@/hooks/useAuth'
import {
  useCreateComment,
  useDeleteComment,
  useDeleteLog,
  useLog,
  useLogComments,
} from '@/hooks/useClimbs'

const count = new Intl.NumberFormat('ko-KR')

// 글자가 작은 인라인 액션(답글·삭제·취소)도 44px 터치 영역을 갖는다
const TEXT_ACTION =
  'inline-flex min-h-11 items-center px-2 text-xs font-medium transition-colors duration-150'

export default function LogDetail() {
  const { id } = useParams()
  const logId = Number(id)
  const validId = Number.isInteger(logId) && logId > 0
  const { data: log, isPending, isError, error } = useLog(validId ? logId : NaN)

  if (!validId || (isError && getErrorCode(error) === 'http_404')) {
    return <NotFound message="기록을 찾을 수 없어요. 삭제됐거나 비공개 기록일 수 있어요." />
  }
  if (isPending) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (isError || !log) {
    return <NotFound message="기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." />
  }
  return <LogDetailView log={log} />
}

function NotFound({ message }: { message: string }) {
  return (
    <div role="alert" className="py-10 text-center">
      <p className="text-sm text-pretty text-danger-500">{message}</p>
      <Link
        to="/feed"
        className="mt-2 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
      >
        피드로 돌아가기
      </Link>
    </div>
  )
}

function LogDetailView({ log }: { log: ClimbLog }) {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const location = useLocation()
  const remove = useDeleteLog()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const commentsRef = useRef<HTMLElement>(null)
  const isOwner = me?.id === log.user.id

  // 피드 카드의 댓글 수(#comments)로 들어오면 댓글 영역으로 내려간다
  useEffect(() => {
    if (location.hash === '#comments') {
      commentsRef.current?.scrollIntoView({ block: 'start' })
    }
  }, [location.hash])

  const onDelete = () => {
    remove.mutate(log.id, {
      onSuccess: () => navigate('/feed', { replace: true }),
    })
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Link
          to="/feed"
          className="-ml-2 inline-flex min-h-11 items-center px-2 text-sm font-medium text-ink-500 hover:text-ink-700"
        >
          <span aria-hidden className="mr-1">
            ←
          </span>
          피드
        </Link>
        {isOwner && (
          <div className="flex items-center gap-1">
            <Link
              to={`/logs/${log.id}/edit`}
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

      <LogCard log={log} variant="detail" />

      {/* AI 자세 분석 — 영상이 있는 기록에서만. 작성자가 요청하고, 결과는 공개 기록이면 누구나 본다 */}
      {log.videoUrl && <AnalysisPanel log={log} isOwner={isOwner} />}

      {remove.isError && (
        <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {getErrorMessage(remove.error, '기록을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
      )}

      <Comments ref={commentsRef} log={log} myId={me?.id ?? null} />

      <ConfirmDialog
        open={confirmDelete}
        title="이 기록을 삭제할까요?"
        description="좋아요와 댓글도 함께 사라지며 되돌릴 수 없어요."
        confirmLabel="삭제"
        pending={remove.isPending}
        onConfirm={onDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  )
}

// --- 댓글 ---

interface Thread {
  comment: ClimbLogComment
  replies: ClimbLogComment[]
}

/**
 * 오래된 순 목록을 1단계 스레드로 묶는다. 부모는 항상 답글보다 먼저 만들어졌으니
 * 먼저 등장한다. 부모가 삭제돼 목록에 없는 답글은 최상위로 올린다.
 */
function toThreads(comments: ClimbLogComment[]): Thread[] {
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
  ref,
  log,
  myId,
}: {
  ref: Ref<HTMLElement>
  log: ClimbLog
  myId: number | null
}) {
  const comments = useLogComments(log.id)
  const loaded = comments.data?.pages.flatMap((page) => page.results) ?? []
  const threads = toThreads(loaded)
  const [replyTo, setReplyTo] = useState<ClimbLogComment | null>(null)
  const [pendingDelete, setPendingDelete] = useState<ClimbLogComment | null>(null)
  const remove = useDeleteComment(log.id)

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
    <section
      ref={ref}
      id="comments"
      aria-labelledby="comments-heading"
      className="scroll-mt-4 space-y-3"
    >
      <h2 id="comments-heading" className="text-base font-semibold text-ink-700">
        댓글{' '}
        <span className="font-medium text-ink-400 tabular-nums">
          {count.format(log.commentCount)}개
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

      <CommentForm logId={log.id} replyTo={replyTo} onCancelReply={() => setReplyTo(null)} />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="이 댓글을 삭제할까요?"
        description="삭제한 댓글은 되돌릴 수 없어요."
        confirmLabel="삭제"
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
  comment: ClimbLogComment
  mine: boolean
  /** 최상위 댓글에만 — 답글에는 다시 답글을 달 수 없다 (서버 규칙) */
  onReply?: () => void
  onDelete: () => void
}) {
  return (
    <article className="flex gap-3">
      {/* 아바타는 닉네임 링크와 같은 곳으로 가는 44px 터치 영역 — 키보드 탭 순서에선 닉네임만 */}
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
  logId,
  replyTo,
  onCancelReply,
}: {
  logId: number
  replyTo: ClimbLogComment | null
  onCancelReply: () => void
}) {
  const create = useCreateComment(logId)
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
  const canSubmit = trimmed.length > 0 && content.length <= COMMENT_MAX_LENGTH
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
        placeholder={replyTo ? '답글을 남겨보세요' : '응원이나 베타 팁을 남겨보세요'}
        maxLength={COMMENT_MAX_LENGTH}
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
      {/* 이 페이지의 유일한 primary CTA */}
      <Button type="submit" full disabled={!canSubmit || pending}>
        {pending ? '남기는 중…' : replyTo ? '답글 남기기' : '댓글 남기기'}
      </Button>
    </form>
  )
}

// --- 삭제 확인 ---

/**
 * 파괴적 액션 확인 — 네이티브 <dialog> 가 포커스 가두기·Esc·바깥 배경을 맡는다.
 * 진행 중에는 Esc 로 닫히지 않게 막는다.
 */
function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  pending,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  pending: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    else if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby="confirm-title"
      aria-describedby="confirm-description"
      onClose={onCancel}
      onCancel={(e) => {
        if (pending) e.preventDefault()
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-sm rounded-card border border-chalk-300 bg-white p-6 text-ink-600 backdrop:bg-ink-700/40"
    >
      <h2 id="confirm-title" className="text-base font-semibold text-ink-700">
        {title}
      </h2>
      <p id="confirm-description" className="mt-1 text-sm text-pretty text-ink-500">
        {description}
      </p>
      <div className="mt-5 flex justify-end gap-2">
        {/* 기본 포커스는 취소 — Enter 연타로 지워지지 않게 */}
        <Button variant="secondary" onClick={onCancel} disabled={pending} autoFocus>
          취소
        </Button>
        <Button variant="danger" onClick={onConfirm} disabled={pending}>
          {pending ? '삭제 중…' : confirmLabel}
        </Button>
      </div>
    </dialog>
  )
}
