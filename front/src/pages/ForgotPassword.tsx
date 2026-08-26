import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { getErrorMessage } from '@/api/client'
import Button from '@/components/common/Button'
import TextField from '@/components/common/TextField'
import { useRequestPasswordReset } from '@/hooks/useAuth'
import { checkEmail, EMAIL_MAX_LENGTH } from '@/lib/validation'

/** 비밀번호 재설정 메일 요청. 계정 유무는 알려주지 않는다. */
export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const request = useRequestPasswordReset()

  const emailCheck = checkEmail(email)
  const canSubmit = emailCheck.state === 'valid'

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || request.isPending) return
    request.mutate(email)
  }

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <h1 className="mb-6 text-2xl font-semibold text-ink-700">비밀번호 재설정</h1>

      {request.isSuccess ? (
        <div role="status" className="space-y-3 rounded-card border border-chalk-300 bg-white p-6">
          <p className="text-sm text-ink-600">
            <span className="font-medium text-ink-700">{email}</span> 이(가) 가입된
            계정이라면 재설정 링크를 보냈습니다. 메일함을 확인해 주세요.
          </p>
          <p className="text-xs text-ink-400">
            링크는 1시간 동안, 한 번만 사용할 수 있습니다. 메일이 안 보이면 스팸함도 확인해
            주세요.
          </p>
        </div>
      ) : (
        <form
          onSubmit={onSubmit}
          noValidate
          className="space-y-4 rounded-card border border-chalk-300 bg-white p-6"
        >
          <p className="text-sm text-pretty text-ink-500">
            가입한 이메일을 입력하면 새 비밀번호를 설정할 수 있는 링크를 보내드려요.
          </p>
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
            onChange={(e) => {
              if (request.isError) request.reset()
              setEmail(e.target.value)
            }}
          />
          {request.isError && (
            <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
              {getErrorMessage(request.error, '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
            </p>
          )}
          <Button type="submit" full disabled={!canSubmit || request.isPending}>
            {request.isPending ? '보내는 중…' : '재설정 링크 보내기'}
          </Button>
        </form>
      )}

      <p className="mt-4 text-center text-sm text-ink-400">
        <Link to="/login" className="font-medium text-hold-600 hover:underline">
          로그인으로 돌아가기
        </Link>
      </p>
    </div>
  )
}
