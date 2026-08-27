import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router'

import { MESSAGE_MAX_LENGTH, type ChatMessage, type ChatRoomDetail } from '@/api/chat'
import { getErrorCode, getErrorMessage } from '@/api/client'
import Avatar from '@/components/common/Avatar'
import Button from '@/components/common/Button'
import TextArea from '@/components/common/TextArea'
import { useMe } from '@/hooks/useAuth'
import {
  appendMessage,
  applyReadReceipt,
  flattenMessages,
  messagesKey,
  roomKey,
  useLeaveRoom,
  useMarkRead,
  useMessages,
  useRoom,
  useSendMessage,
} from '@/hooks/useChat'
import { useChatSocket } from '@/hooks/useChatSocket'
import { GroupIcon, roomTitle } from '@/pages/ChatRooms'

const timeFormat = new Intl.DateTimeFormat('ko-KR', { timeStyle: 'short' })
const dayFormat = new Intl.DateTimeFormat('ko-KR', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'short',
})
const count = new Intl.NumberFormat('ko-KR')

/** 이 안이면 "바닥에 붙어 있다"고 보고 새 메시지가 오면 따라 내려간다 */
const NEAR_BOTTOM_PX = 80
/** 입력칸 자동 높이 상한 — 본문 4줄(24px) + 상하 패딩 + 보더 */
const COMPOSER_MAX_PX = 118
/** 입력 중 표시가 사라지기까지 */
const TYPING_TTL_MS = 3000

export default function ChatRoom() {
  const { id } = useParams()
  const roomId = Number(id)
  const validId = Number.isInteger(roomId) && roomId > 0
  const { data: me } = useMe()
  const room = useRoom(validId ? roomId : NaN)

  if (!validId || (room.isError && getErrorCode(room.error) === 'http_404')) {
    return (
      <div role="alert" className="py-10 text-center">
        <p className="text-sm text-danger-500">채팅방을 찾을 수 없어요</p>
        <Link
          to="/chat"
          className="mt-2 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
        >
          채팅 목록으로
        </Link>
      </div>
    )
  }
  if (room.isPending || !me) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (room.isError || !room.data) {
    return (
      <div role="alert" className="py-10 text-center">
        <p className="text-sm text-pretty text-danger-500">
          {getErrorMessage(room.error, '채팅방을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
        <Button variant="secondary" className="mt-3" onClick={() => room.refetch()}>
          다시 시도
        </Button>
      </div>
    )
  }
  return <RoomView room={room.data} meId={me.id} />
}

function RoomView({ room, meId }: { room: ChatRoomDetail; meId: number }) {
  const roomId = room.id
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const title = roomTitle(room)

  // --- 메시지 ---
  const messagesQuery = useMessages(roomId)
  const messages = flattenMessages(messagesQuery.data)
  const newestId = messages.length > 0 ? messages[messages.length - 1].id : null

  // --- 입력 중 표시 (3초 지나면 지운다) ---
  const [typing, setTyping] = useState<{ id: number; nickname: string }[]>([])
  const typingTimers = useRef(new Map<number, ReturnType<typeof setTimeout>>())
  const onTyping = useCallback(
    (user: { id: number; nickname: string }) => {
      if (user.id === meId) return
      const timers = typingTimers.current
      const existing = timers.get(user.id)
      if (existing) clearTimeout(existing)
      timers.set(
        user.id,
        setTimeout(() => {
          timers.delete(user.id)
          setTyping((list) => list.filter((u) => u.id !== user.id))
        }, TYPING_TTL_MS),
      )
      setTyping((list) => (list.some((u) => u.id === user.id) ? list : [...list, user]))
    },
    [meId],
  )
  useEffect(() => {
    const timers = typingTimers.current
    return () => timers.forEach((t) => clearTimeout(t))
  }, [])

  // --- 소켓 (유일한 WebSocket 접근점) ---
  const [socketError, setSocketError] = useState<string | null>(null)
  const socket = useChatSocket(roomId, {
    onMessage: (message) => {
      appendMessage(queryClient, message, meId)
      const senderId = message.sender?.id
      if (senderId !== undefined) setTyping((list) => list.filter((u) => u.id !== senderId))
    },
    onRead: ({ userId, messageId }) =>
      applyReadReceipt(queryClient, roomId, userId, messageId, meId),
    onTyping,
    onError: (e) => setSocketError(e.message),
  })

  const send = useSendMessage(
    roomId,
    (content) => socket.send({ type: 'message', content }),
    meId,
  )
  const markRead = useMarkRead(roomId, meId)
  const leave = useLeaveRoom(roomId)

  // 소켓이 (다시) 열리면 끊긴 사이 놓친 메시지·읽음 위치를 서버에서 받아온다.
  // 첫 로딩과 겹치면(이미 받는 중) 건너뛴다.
  useEffect(() => {
    if (socket.status !== 'open') return
    for (const key of [messagesKey(roomId), roomKey(roomId)]) {
      if (queryClient.getQueryState(key)?.fetchStatus !== 'fetching') {
        queryClient.invalidateQueries({ queryKey: key, exact: true })
      }
    }
  }, [socket.status, roomId, queryClient])

  // --- 읽음 처리: 탭이 보일 때 가장 최근 메시지까지 ---
  const lastMarkedRef = useRef(room.lastReadMessageId ?? 0)
  const { mutate: mutateMarkRead } = markRead
  useEffect(() => {
    const tryMark = () => {
      if (document.visibilityState !== 'visible') return
      if (newestId === null || newestId <= lastMarkedRef.current) return
      lastMarkedRef.current = newestId
      mutateMarkRead(newestId)
    }
    tryMark()
    document.addEventListener('visibilitychange', tryMark)
    return () => document.removeEventListener('visibilitychange', tryMark)
  }, [newestId, mutateMarkRead])

  // --- 스크롤: 바닥 근처면 새 메시지를 따라가고, 위로 불러올 땐 위치를 유지한다 ---
  const listRef = useRef<HTMLDivElement>(null)
  const stickToBottomRef = useRef(true)
  const prependRef = useRef<{ scrollHeight: number; scrollTop: number } | null>(null)

  const onListScroll = () => {
    const el = listRef.current
    if (!el) return
    stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX
  }

  const loadOlder = () => {
    const el = listRef.current
    if (el) prependRef.current = { scrollHeight: el.scrollHeight, scrollTop: el.scrollTop }
    messagesQuery.fetchNextPage()
  }

  useLayoutEffect(() => {
    const el = listRef.current
    if (!el) return
    if (prependRef.current) {
      el.scrollTop = prependRef.current.scrollTop + (el.scrollHeight - prependRef.current.scrollHeight)
      prependRef.current = null
      return
    }
    if (stickToBottomRef.current) el.scrollTop = el.scrollHeight
  }, [messages.length, newestId, typing.length])

  // --- 나가기 (그룹만) ---
  const [confirmLeave, setConfirmLeave] = useState(false)
  const onLeave = () => leave.mutate(undefined, { onSuccess: () => navigate('/chat') })

  // --- 입력 ---
  const onSend = (content: string) => {
    setSocketError(null)
    stickToBottomRef.current = true
    send.mutate(content)
  }

  const peer = room.isGroup ? null : room.members.find((m) => m.user.id !== meId)
  const peerLastRead = peer?.lastReadMessageId ?? 0
  const myLastMessageId = [...messages].reverse().find((m) => m.sender?.id === meId)?.id ?? null

  return (
    <div className="mx-auto flex h-[calc(100dvh-6rem)] min-h-80 max-w-xl flex-col">
      <header className="flex items-center gap-2 pb-3">
        <Link
          to="/chat"
          aria-label="채팅 목록으로"
          className="-ml-2 inline-flex size-11 shrink-0 items-center justify-center rounded-xl text-ink-500 transition-colors duration-150 hover:text-ink-700"
        >
          <svg
            aria-hidden
            viewBox="0 0 24 24"
            className="size-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M15 5l-7 7 7 7" />
          </svg>
        </Link>
        {room.isGroup ? (
          <GroupIcon className="size-8" />
        ) : (
          <Avatar user={room.peer ?? { nickname: title, image: null }} size="sm" />
        )}
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-semibold text-ink-700">{title}</h1>
          {room.isGroup && (
            <p className="text-xs text-ink-400">
              참여 <span className="tabular-nums">{count.format(room.memberCount)}</span>명
            </p>
          )}
        </div>
        {room.isGroup && (
          <Button variant="secondary" className="text-sm" onClick={() => setConfirmLeave(true)}>
            나가기
          </Button>
        )}
      </header>

      {socket.status !== 'open' && (
        <p
          role={socket.error ? 'alert' : 'status'}
          className={`mb-2 rounded-xl px-3 py-1.5 text-center text-xs text-pretty ${
            socket.error ? 'bg-danger-100 text-danger-600' : 'bg-slate-100 text-slate-500'
          }`}
        >
          {socket.error ??
            (socket.status === 'connecting'
              ? '실시간 연결 중…'
              : '실시간 연결이 끊겼어요. 메시지는 계속 보낼 수 있어요.')}
        </p>
      )}

      <div
        ref={listRef}
        onScroll={onListScroll}
        role="log"
        aria-label="메시지"
        className="min-h-0 flex-1 overflow-y-auto rounded-card border border-chalk-300 bg-white px-3 py-3"
      >
        {messagesQuery.hasNextPage && (
          <div className="mb-3 flex justify-center">
            <Button
              variant="secondary"
              className="min-h-9 px-3 text-xs"
              onClick={loadOlder}
              disabled={messagesQuery.isFetchingNextPage}
            >
              {messagesQuery.isFetchingNextPage ? '불러오는 중…' : '이전 메시지'}
            </Button>
          </div>
        )}

        {messagesQuery.isPending && (
          <p role="status" className="py-10 text-center text-sm text-ink-400">
            메시지를 불러오는 중…
          </p>
        )}
        {messagesQuery.isError && (
          <div role="alert" className="py-10 text-center">
            <p className="text-sm text-pretty text-danger-500">
              {getErrorMessage(messagesQuery.error, '메시지를 불러오지 못했습니다.')}
            </p>
            <Button variant="secondary" className="mt-3" onClick={() => messagesQuery.refetch()}>
              다시 시도
            </Button>
          </div>
        )}
        {messagesQuery.data && messages.length === 0 && (
          <p className="py-10 text-center text-sm text-pretty text-ink-400">
            아직 메시지가 없어요. 첫 인사를 건네보세요.
          </p>
        )}

        {/* 불러온 페이지만 그린다 (가상화 라이브러리 없음 — 페이지 단위로 DOM 이 늘어난다) */}
        {messages.length > 0 && (
          <ol className="space-y-1">
            {messages.map((message, index) => {
              const prev = index > 0 ? messages[index - 1] : null
              const dayChanged = !prev || !sameDay(prev.createdAt, message.createdAt)
              const showMeta =
                dayChanged ||
                !prev ||
                prev.type === 'system' ||
                prev.sender?.id !== message.sender?.id
              return (
                <li key={message.id}>
                  {dayChanged && <DaySeparator iso={message.createdAt} />}
                  <MessageRow
                    message={message}
                    mine={message.sender?.id === meId}
                    showMeta={showMeta}
                    read={
                      !room.isGroup &&
                      message.id === myLastMessageId &&
                      peerLastRead >= message.id
                    }
                  />
                </li>
              )
            })}
          </ol>
        )}
      </div>

      <p role="status" className="min-h-5 px-1 pt-1 text-xs text-ink-400">
        {typing.length > 0 && `${typing.map((u) => u.nickname).join(', ')}님이 입력 중…`}
      </p>

      <Composer
        onSend={onSend}
        onTyping={socket.sendTyping}
        pending={send.isPending}
        error={
          socketError ??
          (send.isError ? getErrorMessage(send.error, '메시지를 보내지 못했어요.') : null)
        }
      />

      <LeaveDialog
        open={confirmLeave}
        pending={leave.isPending}
        error={leave.isError ? getErrorMessage(leave.error, '나가지 못했어요.') : null}
        onConfirm={onLeave}
        onCancel={() => setConfirmLeave(false)}
      />
    </div>
  )
}

function sameDay(a: string, b: string): boolean {
  const da = new Date(a)
  const db = new Date(b)
  return (
    da.getFullYear() === db.getFullYear() &&
    da.getMonth() === db.getMonth() &&
    da.getDate() === db.getDate()
  )
}

function DaySeparator({ iso }: { iso: string }) {
  return (
    <div className="my-3 flex items-center gap-3 text-xs text-ink-400">
      <span aria-hidden className="h-px flex-1 bg-chalk-300" />
      <time dateTime={iso}>{dayFormat.format(new Date(iso))}</time>
      <span aria-hidden className="h-px flex-1 bg-chalk-300" />
    </div>
  )
}

function MessageRow({
  message,
  mine,
  showMeta,
  read,
}: {
  message: ChatMessage
  mine: boolean
  showMeta: boolean
  read: boolean
}) {
  if (message.type === 'system' || !message.sender) {
    return (
      <p className="my-2 text-center text-xs text-pretty text-ink-400">{message.content}</p>
    )
  }
  const time = (
    <time
      dateTime={message.createdAt}
      className="mb-0.5 shrink-0 text-xs text-ink-400 tabular-nums"
    >
      {timeFormat.format(new Date(message.createdAt))}
    </time>
  )
  if (mine) {
    return (
      <div className="flex flex-col items-end">
        <div className="flex max-w-[80%] items-end gap-1.5">
          {time}
          <p className="rounded-xl bg-hold-100 px-3 py-2 text-sm break-words whitespace-pre-wrap text-ink-700">
            {message.content}
          </p>
        </div>
        {read && <span className="mt-0.5 pr-1 text-xs text-ink-400">읽음</span>}
      </div>
    )
  }
  return (
    <div className={`flex items-end gap-2 ${showMeta ? 'mt-2' : ''}`}>
      {showMeta ? (
        <Avatar user={message.sender} size="sm" />
      ) : (
        <span aria-hidden className="size-8 shrink-0" />
      )}
      <div className="flex min-w-0 max-w-[80%] flex-col items-start">
        {showMeta && (
          <span className="mb-0.5 max-w-full truncate px-1 text-xs text-ink-500">
            {message.sender.nickname}
          </span>
        )}
        <div className="flex max-w-full items-end gap-1.5">
          <p className="min-w-0 rounded-xl border border-chalk-300 bg-white px-3 py-2 text-sm break-words whitespace-pre-wrap text-ink-700">
            {message.content}
          </p>
          {time}
        </div>
      </div>
    </div>
  )
}

/**
 * 입력칸 — 1~4줄로 자라고, Enter 는 전송 / Shift+Enter 는 줄바꿈.
 * 한글 조합 중 Enter(isComposing) 는 전송하지 않는다.
 */
function Composer({
  onSend,
  onTyping,
  pending,
  error,
}: {
  onSend: (content: string) => void
  onTyping: () => void
  pending: boolean
  error: string | null
}) {
  const [draft, setDraft] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const canSend = draft.trim().length > 0 && !pending

  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, COMPOSER_MAX_PX)}px`
    el.style.overflowY = el.scrollHeight > COMPOSER_MAX_PX ? 'auto' : 'hidden'
  }, [draft])

  const submit = () => {
    const content = draft.trim()
    if (!content || pending) return
    onSend(content)
    setDraft('')
    textareaRef.current?.focus()
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    submit()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Enter' || e.shiftKey || e.nativeEvent.isComposing) return
    e.preventDefault()
    submit()
  }

  return (
    <form onSubmit={onSubmit} className="mt-1">
      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1">
          <TextArea
            ref={textareaRef}
            label="메시지"
            hideLabel
            name="content"
            rows={1}
            maxLength={MESSAGE_MAX_LENGTH}
            showCount={draft.length >= MESSAGE_MAX_LENGTH - 200}
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value)
              if (e.target.value.trim()) onTyping()
            }}
            onKeyDown={onKeyDown}
            placeholder="메시지를 입력하세요"
            autoComplete="off"
            enterKeyHint="send"
            // 공용 TextArea 의 min-h-28·resize-y 를 자동 높이 조절이 덮는다
            style={{ minHeight: '2.75rem', resize: 'none' }}
          />
        </div>
        {/* 이 페이지의 유일한 primary CTA */}
        <Button type="submit" disabled={!canSend} className="mb-1 shrink-0">
          {pending ? '전송 중…' : '보내기'}
        </Button>
      </div>
      {error && (
        <p role="alert" className="mt-1 rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {error}
        </p>
      )}
    </form>
  )
}

/** 그룹 방 나가기 확인 — 네이티브 <dialog> 가 포커스 가두기·Esc·배경을 맡는다 */
function LeaveDialog({
  open,
  pending,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean
  pending: boolean
  error: string | null
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
      aria-labelledby="leave-title"
      aria-describedby="leave-description"
      onClose={onCancel}
      onCancel={(e) => {
        if (pending) e.preventDefault()
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-sm rounded-card border border-chalk-300 bg-white p-6 text-ink-600 backdrop:bg-ink-700/40"
    >
      <h2 id="leave-title" className="text-base font-semibold text-ink-700">
        채팅방을 나갈까요?
      </h2>
      <p id="leave-description" className="mt-1 text-sm text-pretty text-ink-500">
        나가면 이 방의 대화를 더 이상 볼 수 없어요.
      </p>
      {error && (
        <p role="alert" className="mt-3 rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {error}
        </p>
      )}
      <div className="mt-5 flex justify-end gap-2">
        {/* 기본 포커스는 취소 — Enter 연타로 나가지지 않게 */}
        <Button variant="secondary" onClick={onCancel} disabled={pending} autoFocus>
          취소
        </Button>
        <Button variant="danger" onClick={onConfirm} disabled={pending}>
          {pending ? '나가는 중…' : '나가기'}
        </Button>
      </div>
    </dialog>
  )
}
