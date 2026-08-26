import { Link, Navigate, useLocation } from 'react-router'

import { getErrorMessage } from '@/api/client'
import Button from '@/components/common/Button'
import { useResendVerification } from '@/hooks/useAuth'

/** 가입 직후 — 인증 메일을 확인하라는 안내. Signup 이 state 로 이메일을 넘긴다. */
export default function SignupSent() {
  const location = useLocation()
  const email = (location.state as { email?: string } | null)?.email
  const resend = useResendVerification()

  // 주소를 직접 쳐서 들어오면 안내할 이메일이 없다.
  if (!email) return <Navigate to="/signup" replace />

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <h1 className="mb-6 text-2xl font-semibold text-ink-700">인증 메일을 보냈어요</h1>
      <div className="space-y-4 rounded-card border border-chalk-300 bg-white p-6">
        <p className="text-sm text-pretty text-ink-600">
          <span className="font-medium text-ink-700">{email}</span> 으로 인증 링크를
          보냈습니다. 메일의 링크를 누르면 가입이 완료되고 로그인할 수 있어요.
        </p>
        <p className="text-xs text-ink-400">
          메일이 안 보이면 스팸함을 확인해 주세요. 링크는 24시간 동안 유효합니다.
        </p>

        {resend.isSuccess ? (
          <p role="status" className="rounded-xl bg-moss-100 px-3 py-2 text-sm text-moss-500">
            인증 메일을 다시 보냈습니다.
          </p>
        ) : (
          <Button
            variant="secondary"
            full
            onClick={() => resend.mutate(email)}
            disabled={resend.isPending}
          >
            {resend.isPending ? '보내는 중…' : '인증 메일 다시 보내기'}
          </Button>
        )}
        {resend.isError && (
          <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
            {getErrorMessage(resend.error, '메일을 보내지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
        )}
      </div>
      <p className="mt-4 text-center text-sm text-ink-400">
        인증을 마쳤나요?{' '}
        <Link to="/login" className="font-medium text-hold-600 hover:underline">
          로그인
        </Link>
      </p>
    </div>
  )
}
