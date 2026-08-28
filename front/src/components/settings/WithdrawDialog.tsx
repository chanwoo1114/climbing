import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { getErrorCode, getErrorMessage, getFieldError } from '@/api/client'
import Button from '@/components/common/Button'
import TextField from '@/components/common/TextField'
import type { FieldCheck } from '@/lib/validation'

const IDLE: FieldCheck = { state: 'idle', message: '' }

/**
 * 회원 탈퇴 확인 — ConfirmDialog 와 같은 네이티브 <dialog> 규칙(포커스 가두기·Esc·진행 중 잠금)에
 * 비밀번호 입력칸이 들어간 폼 버전. 소셜 전용 계정은 비밀번호가 없으므로 비워서 보낼 수 있고,
 * 필요한 계정이면 서버가 fields.password 로 알려준다.
 */
export default function WithdrawDialog({
  open,
  pending,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean
  pending: boolean
  /** 마지막 탈퇴 시도의 오류 (useWithdraw().error) */
  error: unknown
  onConfirm: (password: string) => void
  onCancel: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descriptionId = useId()
  const [password, setPassword] = useState('')

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) {
      setPassword('')
      dialog.showModal()
    } else if (!open && dialog.open) {
      dialog.close()
    }
  }, [open])

  const passwordError = getFieldError(error, 'password')
  const passwordCheck: FieldCheck = passwordError
    ? { state: 'invalid', message: passwordError }
    : IDLE
  const crewOwner = getErrorCode(error) === 'crew_owner'
  const generalError = error && !passwordError ? getErrorMessage(error, '탈퇴하지 못했습니다.') : null

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (pending) return
    onConfirm(password)
  }

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onClose={onCancel}
      onCancel={(e) => {
        if (pending) e.preventDefault()
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-sm rounded-card border border-chalk-300 bg-white p-6 text-ink-600 backdrop:bg-ink-700/40"
    >
      <form onSubmit={onSubmit} noValidate>
        <h2 id={titleId} className="text-base font-semibold text-ink-700">
          정말 탈퇴할까요?
        </h2>
        <p id={descriptionId} className="mt-1 text-sm text-pretty text-ink-500">
          기록·댓글·팔로우가 모두 삭제되며 되돌릴 수 없습니다.
        </p>
        <div className="mt-4">
          <TextField
            label="비밀번호 확인"
            name="withdrawPassword"
            type="password"
            autoComplete="current-password"
            placeholder="소셜 로그인만 쓰는 계정이면 비워 두세요"
            value={password}
            check={passwordCheck}
            disabled={pending}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {generalError && (
          <p
            role="alert"
            className="mt-3 rounded-xl bg-danger-100 px-3 py-2 text-sm text-pretty text-danger-600"
          >
            {generalError}
            {crewOwner && (
              <>
                {' '}
                <Link to="/crews" className="font-medium underline underline-offset-2">
                  내 크루 보기
                </Link>
              </>
            )}
          </p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          {/* 기본 포커스는 취소 — Enter 연타로 실행되지 않게 */}
          <Button variant="secondary" onClick={onCancel} disabled={pending} autoFocus>
            취소
          </Button>
          <Button type="submit" variant="danger" disabled={pending}>
            {pending ? '탈퇴 중…' : '탈퇴하기'}
          </Button>
        </div>
      </form>
    </dialog>
  )
}
