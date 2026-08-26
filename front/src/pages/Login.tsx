import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'

import { getErrorCode, getErrorMessage } from '@/api/client'
import Button from '@/components/common/Button'
import TextField from '@/components/common/TextField'
import { useLogin, useResendVerification } from '@/hooks/useAuth'
import {
  checkEmail,
  EMAIL_MAX_LENGTH,
  PASSWORD_MAX_LENGTH,
  type FieldCheck,
} from '@/lib/validation'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const login = useLogin()
  const resend = useResendVerification()
  // RequireAuth 가 보낸 경우 로그인 후 원래 경로로 돌아간다.
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  // 로그인은 형식만 가볍게 본다. 자격 증명 판정은 서버 몫.
  const emailCheck = checkEmail(email)
  const canSubmit = emailCheck.state === 'valid' && password.length > 0

  // 비밀번호는 맞는데 이메일 인증이 안 된 경우 — 오류가 아니라 안내로 보여준다.
  const unverified = getErrorCode(login.error) === 'email_not_verified'

  // 인증 실패(401)는 어느 필드가 틀렸는지 알려주지 않는 게 원칙이라
  // 두 입력칸을 함께 빨갛게 표시하고 메시지는 배너로만 보여준다.
  const failed = login.isError && !unverified
  const credentialCheck: FieldCheck | undefined = failed
    ? { state: 'invalid', message: '' }
    : undefined

  const edit = (setter: (v: string) => void) => (e: { target: { value: string } }) => {
    if (login.isError) login.reset()
    if (resend.isSuccess || resend.isError) resend.reset()
    setter(e.target.value)
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || login.isPending) return
    login.mutate({ email, password }, { onSuccess: () => navigate(from, { replace: true }) })
  }

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <h1 className="mb-6 text-2xl font-semibold text-ink-700">로그인</h1>
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
          check={credentialCheck ?? emailCheck}
          onChange={edit(setEmail)}
        />
        <TextField
          label="비밀번호"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          maxLength={PASSWORD_MAX_LENGTH}
          value={password}
          check={credentialCheck}
          onChange={edit(setPassword)}
        />

        {failed && (
          <p
            role="alert"
            className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600"
          >
            {getErrorMessage(login.error, '이메일 또는 비밀번호가 올바르지 않습니다.')}
          </p>
        )}

        {unverified && (
          <div className="space-y-2 rounded-xl bg-ochre-100 px-3 py-2 text-sm text-ink-700">
            <p>이메일 인증이 아직 안 됐어요. 메일함의 인증 링크를 눌러 주세요.</p>
            {resend.isSuccess ? (
              <p role="status" className="text-moss-500">인증 메일을 다시 보냈습니다.</p>
            ) : (
              <button
                type="button"
                onClick={() => resend.mutate(email)}
                disabled={resend.isPending}
                className="inline-flex min-h-10 items-center font-medium text-hold-600 hover:underline disabled:opacity-50"
              >
                {resend.isPending ? '보내는 중…' : '인증 메일 다시 보내기'}
              </button>
            )}
            {resend.isError && (
              <p role="alert" className="text-danger-600">
                {getErrorMessage(resend.error, '메일을 보내지 못했습니다. 잠시 후 다시 시도해 주세요.')}
              </p>
            )}
          </div>
        )}

        <Button type="submit" full disabled={!canSubmit || login.isPending}>
          {login.isPending ? '로그인 중…' : '로그인'}
        </Button>
      </form>
      <div className="mt-4 space-y-1 text-center text-sm text-ink-400">
        <p>
          <Link to="/forgot-password" className="hover:underline">
            비밀번호를 잊으셨나요?
          </Link>
        </p>
        <p>
          아직 계정이 없나요?{' '}
          <Link to="/signup" className="font-medium text-hold-600 hover:underline">
            회원가입
          </Link>
        </p>
      </div>
    </div>
  )
}
