import { useEffect, useState, type FormEvent } from 'react'

import { getErrorMessage, getFieldError } from '@/api/client'
import type { GymDetail, GymManager } from '@/api/gyms'
import type { UserSummary } from '@/api/users'
import Avatar from '@/components/common/Avatar'
import Button from '@/components/common/Button'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import TextField from '@/components/common/TextField'
import { Card, Empty, ErrorBanner, sinceDate } from '@/components/gyms/manage/ManageBits'
import { useMe } from '@/hooks/useAuth'
import { useAddGymManager, useGymManagers, useRemoveGymManager } from '@/hooks/useGyms'
import { useSearchUsers } from '@/hooks/useUsers'
import { useToastStore } from '@/stores/toastStore'

const DEBOUNCE_MS = 300
const NOTE_MAX_LENGTH = 100

/** 관리자 — 목록·해제(마지막 관리자는 서버가 409 로 막는다)·닉네임 검색으로 추가 */
export default function ManagerSection({ gym }: { gym: GymDetail }) {
  const managers = useGymManagers(gym.id)
  const { data: me } = useMe()

  let body
  if (managers.isPending) {
    body = (
      <p role="status" className="text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  } else if (managers.isError || !managers.data) {
    body = <ErrorBanner>관리자 목록을 불러오지 못했습니다. 잠시 후 새로고침해 주세요.</ErrorBanner>
  } else if (managers.data.length === 0) {
    body = <Empty>관리자가 없어요</Empty>
  } else {
    body = (
      <ul className="divide-y divide-chalk-200">
        {managers.data.map((manager) => (
          <ManagerRow
            key={manager.id}
            gymId={gym.id}
            manager={manager}
            isMe={manager.user.id === me?.id}
          />
        ))}
      </ul>
    )
  }

  return (
    <Card
      id="manage-managers"
      title="관리자"
      description="관리자는 이 화면에서 암장 정보를 고칠 수 있어요. 마지막 한 명은 뺄 수 없어요."
    >
      {body}
      <AddManager
        gymId={gym.id}
        existingIds={new Set((managers.data ?? []).map((manager) => manager.user.id))}
      />
    </Card>
  )
}

function ManagerRow({
  gymId,
  manager,
  isMe,
}: {
  gymId: number
  manager: GymManager
  isMe: boolean
}) {
  const remove = useRemoveGymManager(gymId)
  const [confirm, setConfirm] = useState(false)

  const onRemove = () => {
    remove.mutate(manager.user.id, { onSettled: () => setConfirm(false) })
  }

  return (
    <li className="py-3">
      <div className="flex items-center gap-3">
        <Avatar user={manager.user} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-ink-700">
            {manager.user.nickname}
            {isMe && <span className="ml-1 text-xs font-normal text-ink-400">(나)</span>}
          </p>
          <p className="text-xs text-pretty break-words text-ink-400">
            {manager.note && <span>{manager.note} · </span>}
            <time dateTime={manager.createdAt} className="tabular-nums">
              {sinceDate.format(new Date(manager.createdAt))}
            </time>
            부터
          </p>
        </div>
        <Button
          variant="secondary"
          aria-label={`${manager.user.nickname} 삭제`}
          onClick={() => {
            remove.reset()
            setConfirm(true)
          }}
          disabled={remove.isPending}
        >
          삭제
        </Button>
      </div>
      {remove.isError && (
        <div className="mt-2">
          {/* 409 last_manager 등 — 서버 메시지를 그대로 보여준다 */}
          <ErrorBanner>
            {getErrorMessage(remove.error, '관리자를 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </ErrorBanner>
        </div>
      )}
      <ConfirmDialog
        open={confirm}
        title={`'${manager.user.nickname}' 님을 관리자에서 뺄까요?`}
        description={
          isMe
            ? '나를 빼면 더 이상 이 암장을 관리할 수 없어요.'
            : '이 회원은 더 이상 암장 정보를 고칠 수 없어요.'
        }
        confirmLabel="삭제"
        pendingLabel="삭제 중…"
        pending={remove.isPending}
        onConfirm={onRemove}
        onCancel={() => setConfirm(false)}
      />
    </li>
  )
}

/**
 * 닉네임 검색(300ms 디바운스) → 회원 선택 → 메모(선택) → 추가.
 * 이미 관리자인 회원은 검색 결과에서 뺀다.
 */
function AddManager({ gymId, existingIds }: { gymId: number; existingIds: Set<number> }) {
  const add = useAddGymManager(gymId)
  const pushToast = useToastStore((s) => s.push)
  const [input, setInput] = useState('')
  const [q, setQ] = useState('')
  const [picked, setPicked] = useState<UserSummary | null>(null)
  const [note, setNote] = useState('')

  useEffect(() => {
    const next = input.trim()
    if (next === q) return
    const timer = setTimeout(() => setQ(next), DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [input, q])

  const results = useSearchUsers(picked ? '' : q)
  const candidates = (results.data?.pages.flatMap((page) => page.results) ?? []).filter(
    (user) => !existingIds.has(user.id),
  )

  const onPick = (user: UserSummary) => {
    if (add.isError) add.reset()
    setPicked(user)
  }
  const onUnpick = () => {
    if (add.isError) add.reset()
    setPicked(null)
    setNote('')
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!picked || add.isPending) return
    add.mutate(
      { userId: picked.id, note: note.trim() },
      {
        onSuccess: (manager) => {
          pushToast({ title: `'${manager.user.nickname}' 님을 관리자로 추가했습니다.` })
          setPicked(null)
          setNote('')
          setInput('')
          setQ('')
        },
      },
    )
  }

  const noteError = getFieldError(add.error, 'note')
  const generalError =
    add.error && !noteError
      ? getErrorMessage(add.error, '관리자를 추가하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      : null

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      aria-labelledby="add-manager-heading"
      className="space-y-3 border-t border-chalk-200 pt-4"
    >
      <h3 id="add-manager-heading" className="text-sm font-semibold text-ink-700">
        관리자 추가
      </h3>

      {picked ? (
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-xl bg-chalk-100 px-3 py-2">
            <Avatar user={picked} size="sm" />
            <p className="min-w-0 flex-1 truncate text-sm font-medium text-ink-700">
              {picked.nickname}
            </p>
            <Button variant="secondary" onClick={onUnpick} disabled={add.isPending}>
              다른 회원 선택
            </Button>
          </div>
          <TextField
            label="메모 (선택)"
            id="manager-note"
            name="manager-note"
            autoComplete="off"
            placeholder="예) 점장"
            maxLength={NOTE_MAX_LENGTH}
            value={note}
            check={noteError ? { state: 'invalid', message: noteError } : undefined}
            onChange={(e) => {
              if (add.isError) add.reset()
              setNote(e.target.value)
            }}
            disabled={add.isPending}
          />
          {generalError && <ErrorBanner>{generalError}</ErrorBanner>}
          <div className="flex justify-end">
            {/* 이 섹션의 유일한 primary CTA */}
            <Button type="submit" disabled={add.isPending}>
              {add.isPending ? '추가 중…' : '관리자로 추가'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <TextField
            label="닉네임 검색"
            id="manager-search"
            name="manager-search"
            type="search"
            autoComplete="off"
            spellCheck={false}
            placeholder="닉네임을 입력하세요"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          {q && results.isPending && (
            <p role="status" className="text-sm text-ink-400">
              검색 중…
            </p>
          )}
          {results.isError && (
            <ErrorBanner>
              {getErrorMessage(results.error, '검색에 실패했습니다. 잠시 후 다시 시도해 주세요.')}
            </ErrorBanner>
          )}
          {q && results.data && candidates.length === 0 && (
            <p role="status" className="text-sm text-pretty break-words text-ink-400">
              '{q}'에 해당하는 회원이 없어요
            </p>
          )}
          {candidates.length > 0 && (
            <ul aria-label="검색 결과" className="divide-y divide-chalk-200 rounded-xl border border-chalk-200">
              {candidates.map((user) => (
                <li key={user.id} className="flex items-center gap-3 px-3 py-2">
                  <Avatar user={user} size="sm" />
                  <p className="min-w-0 flex-1 truncate text-sm text-ink-700">{user.nickname}</p>
                  <Button
                    variant="secondary"
                    aria-label={`${user.nickname} 선택`}
                    onClick={() => onPick(user)}
                  >
                    선택
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {results.hasNextPage && (
            <Button
              variant="secondary"
              full
              onClick={() => results.fetchNextPage()}
              disabled={results.isFetchingNextPage}
            >
              {results.isFetchingNextPage ? '불러오는 중…' : '더 보기'}
            </Button>
          )}
          {generalError && <ErrorBanner>{generalError}</ErrorBanner>}
        </div>
      )}
    </form>
  )
}
