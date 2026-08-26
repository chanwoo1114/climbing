import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { getErrorCode, getErrorMessage, getFieldError } from '@/api/client'
import Button from '@/components/common/Button'
import PasswordRuleList from '@/components/common/PasswordRuleList'
import TextField from '@/components/common/TextField'
import { useConfirmPasswordReset } from '@/hooks/useAuth'
import {
  checkPassword,
  checkPasswordConfirm,
  PASSWORD_MAX_LENGTH,
  type FieldCheck,
} from '@/lib/validation'

/** 재설정 메일 링크(/reset-password?uid=...&token=...) 도착 페이지. */
export default function ResetPassword() {
  const [params] = useSearchParams()
  const uid = params.get('uid') ?? ''
  const token = params.get('token') ?? ''
  const confirm = useConfirmPasswordReset()

  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')

  // 이메일·닉네임은 이 화면에서 모르므로 유사도 검사는 서버 몫 — 서버 오류를 필드에 표시.
  const serverPasswordError = getFieldError(confirm.error, 'password')
  const passwordCheck: FieldCheck = serverPasswordError
    ? { state: 'invalid', message: serverPasswordError }
    : checkPassword(password)
  const confirmCheck = checkPasswordConfirm(password, passwordConfirm)
  const canSubmit =
    checkPassword(password).state === 'valid' && confirmCheck.state === 'valid'

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || confirm.isPending) return
    confirm.mutate({ uid, token, password })
  }

  const edit = (setter: (v: string) => void) => (e: { target: { value: string } }) => {
    if (confirm.isError) confirm.reset()
    setter(e.target.value)
  }

  const linkInvalid = !uid || !token || getErrorCode(confirm.error) === 'invalid_token'
  const generalError = confirm.isError && !serverPasswordError && !linkInvalid

  let content
  if (confirm.isSuccess) {
    content = (
      <div role="status" className="space-y-2 rounded-card border border-chalk-300 bg-white p-6">
        <h2 className="text-xl font-semibold text-moss-500">비밀번호를 바꿨어요</h2>
        <p className="text-sm text-ink-600">
          새 비밀번호로 로그인해 주세요. 다른 기기의 로그인은 모두 해제되었습니다.
        </p>
      </div>
    )
  } else if (linkInvalid) {
    content = (
      <div role="alert" className="space-y-2 rounded-card border border-chalk-300 bg-white p-6">
        <h2 className="text-xl font-semibold text-danger-600">링크를 사용할 수 없어요</h2>
        <p className="text-sm text-ink-600">
          {confirm.isError
            ? getErrorMessage(confirm.error, '링크가 유효하지 않거나 만료되었습니다.')
            : '재설정 링크가 올바르지 않습니다. 메일의 링크를 다시 눌러 주세요.'}
        </p>
        <Link
          to="/forgot-password"
          className="inline-block text-sm font-medium text-hold-600 hover:underline"
        >
          재설정 링크 다시 받기
        </Link>
      </div>
    )
  } else {
    content = (
      <form
        onSubmit={onSubmit}
        noValidate
        className="space-y-4 rounded-card border border-chalk-300 bg-white p-6"
      >
        <div>
          <TextField
            label="새 비밀번호"
            name="password"
            type="password"
            autoComplete="new-password"
            placeholder="8~16자, 영문·숫자·특수문자 2종 조합"
            required
            maxLength={PASSWORD_MAX_LENGTH}
            value={password}
            check={
              passwordCheck.state === 'idle'
                ? passwordCheck
                : { ...passwordCheck, message: serverPasswordError ?? '' }
            }
            onChange={edit(setPassword)}
          />
          <PasswordRuleList password={password} context={{}} />
        </div>
        <TextField
          label="새 비밀번호 확인"
          name="passwordConfirm"
          type="password"
          autoComplete="new-password"
          required
          value={passwordConfirm}
          check={confirmCheck}
          onChange={edit(setPasswordConfirm)}
        />
        {generalError && (
          <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
            {getErrorMessage(confirm.error, '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
        )}
        <Button type="submit" full disabled={!canSubmit || confirm.isPending}>
          {confirm.isPending ? '변경 중…' : '비밀번호 변경'}
        </Button>
      </form>
    )
  }

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <h1 className="mb-6 text-2xl font-semibold text-ink-700">새 비밀번호 설정</h1>
      {content}
      <p className="mt-4 text-center text-sm text-ink-400">
        <Link to="/login" className="font-medium text-hold-600 hover:underline">
          로그인으로 이동
        </Link>
      </p>
    </div>
  )
}
