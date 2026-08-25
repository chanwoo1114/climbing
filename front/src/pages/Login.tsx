import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import TextField from '@/components/common/TextField'
import { useLogin } from '@/hooks/useAuth'
import {
  checkEmail,
  EMAIL_MAX_LENGTH,
  PASSWORD_MAX_LENGTH,
  type FieldCheck,
} from '@/lib/validation'

export default function Login() {
  const navigate = useNavigate()
  const login = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  // 로그인은 형식만 가볍게 본다. 자격 증명 판정은 서버 몫.
  const emailCheck = checkEmail(email)
  const canSubmit = emailCheck.state === 'valid' && password.length > 0

  // 인증 실패(401)는 어느 필드가 틀렸는지 알려주지 않는 게 원칙이라
  // 두 입력칸을 함께 빨갛게 표시하고 메시지는 배너로만 보여준다.
  const failed = login.isError
  const credentialCheck: FieldCheck | undefined = failed
    ? { state: 'invalid', message: '' }
    : undefined

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || login.isPending) return
    login.mutate({ email, password }, { onSuccess: () => navigate('/') })
  }

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <h1 className="mb-6 text-2xl font-semibold text-ink-700">로그인</h1>
      <form
        onSubmit={onSubmit}
        noValidate
        className="space-y-4 rounded-[14px] border border-chalk-300 bg-white p-6"
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
          onChange={(e) => setEmail(e.target.value)}
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
          onChange={(e) => setPassword(e.target.value)}
        />

        {failed && (
          <p
            role="alert"
            className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600"
          >
            {login.error instanceof Error && login.error.message
              ? login.error.message
              : '이메일 또는 비밀번호가 올바르지 않습니다.'}
          </p>
        )}

        <button
          type="submit"
          disabled={!canSubmit || login.isPending}
          className="w-full rounded-xl bg-terra-500 py-2.5 font-medium text-white hover:bg-terra-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {login.isPending ? '로그인 중…' : '로그인'}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-ink-400">
        아직 계정이 없나요?{' '}
        <Link to="/signup" className="font-medium text-terra-600 hover:underline">
          회원가입
        </Link>
      </p>
    </div>
  )
}
