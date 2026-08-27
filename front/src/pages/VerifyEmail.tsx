import { Link, useSearchParams } from 'react-router'

import { getErrorMessage } from '@/api/client'
import { useVerifyEmail } from '@/hooks/useAuth'

/** 인증 메일 링크(/verify-email?token=...) 도착 페이지 — 열리자마자 토큰을 확인한다. */
export default function VerifyEmail() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  // 페이지가 열리면 바로 토큰을 검증한다 (query 라 StrictMode 리마운트에도 안전)
  const verify = useVerifyEmail(token)

  let body
  if (!token) {
    body = <Status tone="danger" title="잘못된 링크예요" detail="인증 토큰이 없습니다. 메일의 링크를 다시 눌러 주세요." />
  } else if (verify.isSuccess) {
    body = (
      <Status
        tone="moss"
        title="이메일 인증 완료"
        detail={`${verify.data.email} 인증이 끝났습니다. 이제 로그인할 수 있어요.`}
      />
    )
  } else if (verify.isError) {
    body = (
      <Status
        tone="danger"
        title="인증하지 못했어요"
        detail={getErrorMessage(verify.error, '링크가 유효하지 않거나 만료되었습니다.')}
        hint="로그인 화면에서 인증 메일을 다시 받을 수 있습니다."
      />
    )
  } else {
    body = <Status tone="ink" title="인증 확인 중…" detail="잠시만 기다려 주세요." />
  }

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <div className="rounded-card border border-chalk-300 bg-white p-6">{body}</div>
      <p className="mt-4 text-center text-sm text-ink-400">
        <Link to="/login" className="font-medium text-hold-600 hover:underline">
          로그인으로 이동
        </Link>
      </p>
    </div>
  )
}

const TITLE = {
  moss: 'text-moss-500',
  danger: 'text-danger-600',
  ink: 'text-ink-700',
} as const

function Status({
  tone,
  title,
  detail,
  hint,
}: {
  tone: keyof typeof TITLE
  title: string
  detail: string
  hint?: string
}) {
  // 결과가 바뀔 때 스크린리더에 알린다 — 오류는 즉시, 나머지는 조용히
  return (
    <div role={tone === 'danger' ? 'alert' : 'status'} className="space-y-2">
      <h1 className={`text-xl font-semibold ${TITLE[tone]}`}>{title}</h1>
      <p className="text-sm text-pretty text-ink-600">{detail}</p>
      {hint && <p className="text-xs text-ink-400">{hint}</p>}
    </div>
  )
}
