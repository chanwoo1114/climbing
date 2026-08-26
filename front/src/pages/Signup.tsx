import { useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import { getFieldError } from '@/api/client'
import Button from '@/components/common/Button'
import PasswordRuleList from '@/components/common/PasswordRuleList'
import TextField from '@/components/common/TextField'
import { useRegister } from '@/hooks/useAuth'
import {
  checkEmail,
  checkNickname,
  checkPassword,
  checkPasswordConfirm,
  EMAIL_MAX_LENGTH,
  PASSWORD_MAX_LENGTH,
  type FieldCheck,
} from '@/lib/validation'

export default function Signup() {
  const navigate = useNavigate()
  const registerMutation = useRegister()

  const [email, setEmail] = useState('')
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')

  const error = registerMutation.error

  // 서버가 돌려준 필드 오류가 있으면 클라이언트 검증 결과보다 우선한다.
  const withServerError = (check: FieldCheck, field: string): FieldCheck => {
    const serverMessage = getFieldError(error, field)
    return serverMessage ? { state: 'invalid', message: serverMessage } : check
  }

  const emailCheck = withServerError(checkEmail(email), 'email')
  const nicknameCheck = withServerError(checkNickname(nickname), 'nickname')
  const passwordCheck = withServerError(
    checkPassword(password, { email, nickname }),
    'password',
  )
  const confirmCheck = checkPasswordConfirm(password, passwordConfirm)

  const canSubmit = useMemo(
    () =>
      checkEmail(email).state === 'valid' &&
      checkNickname(nickname).state === 'valid' &&
      checkPassword(password, { email, nickname }).state === 'valid' &&
      confirmCheck.state === 'valid',
    [email, nickname, password, confirmCheck.state],
  )

  const pending = registerMutation.isPending

  // 입력을 고치기 시작하면 이전 서버 오류(빨간 메시지)를 지운다.
  const edit =
    (setter: (value: string) => void) => (e: { target: { value: string } }) => {
      if (registerMutation.isError) registerMutation.reset()
      setter(e.target.value)
    }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || pending) return
    registerMutation.mutate(
      { email, nickname, password },
      {
        // 이메일 인증 전에는 로그인할 수 없으므로 "메일 확인" 안내로 보낸다.
        onSuccess: () =>
          navigate('/signup/sent', { replace: true, state: { email } }),
      },
    )
  }

  // 필드별로 표시된 오류는 아래 공통 배너에서 중복 노출하지 않는다.
  const generalError =
    error &&
    !getFieldError(error, 'email') &&
    !getFieldError(error, 'nickname') &&
    !getFieldError(error, 'password')
      ? error.message
      : null

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <h1 className="mb-6 text-2xl font-semibold text-ink-700">회원가입</h1>
      <form
        onSubmit={onSubmit}
        noValidate
        className="space-y-4 rounded-card border border-chalk-300 bg-white p-6"
      >
        <TextField
          label="이메일"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="climber@example.com"
          required
          maxLength={EMAIL_MAX_LENGTH}
          value={email}
          check={emailCheck}
          onChange={edit(setEmail)}
        />
        <TextField
          label="닉네임"
          name="nickname"
          autoComplete="nickname"
          spellCheck={false}
          placeholder="2~30자, 한글·영문·숫자"
          required
          maxLength={30}
          value={nickname}
          check={nicknameCheck}
          onChange={edit(setNickname)}
        />
        <div>
          <TextField
            label="비밀번호"
            name="password"
            type="password"
            autoComplete="new-password"
            placeholder="8~16자, 영문·숫자·특수문자 2종 조합"
            required
            maxLength={PASSWORD_MAX_LENGTH}
            value={password}
            check={
              // 조건별 상세는 아래 체크리스트가 담당 — 필드에는 상태(색)만 표시
              passwordCheck.state === 'idle'
                ? passwordCheck
                : { ...passwordCheck, message: getFieldError(error, 'password') ?? '' }
            }
            onChange={edit(setPassword)}
          />
          <PasswordRuleList password={password} context={{ email, nickname }} />
        </div>
        <TextField
          label="비밀번호 확인"
          name="passwordConfirm"
          type="password"
          autoComplete="new-password"
          required
          value={passwordConfirm}
          check={confirmCheck}
          onChange={edit(setPasswordConfirm)}
        />

        {generalError && (
          <p
            role="alert"
            className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600"
          >
            {generalError}
          </p>
        )}

        <Button type="submit" full disabled={!canSubmit || pending}>
          {pending ? '가입 중…' : '회원가입'}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-ink-400">
        이미 계정이 있나요?{' '}
        <Link to="/login" className="font-medium text-hold-600 hover:underline">
          로그인
        </Link>
      </p>
    </div>
  )
}
