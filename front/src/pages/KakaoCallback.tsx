import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { getErrorCode, getErrorMessage } from '@/api/client'
import { useKakaoCallback } from '@/hooks/useAuth'
import { clearKakaoRoundTrip, readKakaoRoundTrip } from '@/lib/kakaoLogin'

/**
 * 카카오 인가 페이지에서 돌아오는 곳 (/auth/kakao/callback?code=...&state=...).
 * 열리자마자 code 를 서버에 넘겨 우리 토큰으로 바꾼다 — VerifyEmail 과 같은 이유로 query.
 *
 * - ?error=access_denied : 사용자가 카카오 화면에서 취소
 * - state 불일치         : 저장해 둔 state 가 없거나 다름 → 위조·만료로 보고 처음부터 다시
 * - 성공                 : 신규 가입이면 /profile(닉네임 확인), 아니면 로그인 전 경로로
 */
export default function KakaoCallback() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const code = params.get('code') ?? ''
  const state = params.get('state') ?? ''
  const cancelled = params.get('error') !== null

  // 왕복 전에 맡겨둔 값은 첫 렌더에서 한 번만 읽는다.
  // StrictMode 의 가짜 리마운트에도 state 는 유지되므로 아래에서 지워도 안전하다.
  const [trip] = useState(readKakaoRoundTrip)
  const stateMismatch = !cancelled && (!state || !trip || trip.state !== state)
  const ready = !cancelled && !stateMismatch && !!code

  const callback = useKakaoCallback(ready ? code : '', ready ? state : '')

  // 결과가 정해지면 저장값을 비운다 (성공·실패 모두 재사용 불가)
  const settled = cancelled || stateMismatch || callback.isSuccess || callback.isError
  useEffect(() => {
    if (settled) clearKakaoRoundTrip()
  }, [settled])

  const isNew = callback.data?.isNew
  const from = trip?.from ?? '/'
  useEffect(() => {
    if (!callback.isSuccess) return
    if (isNew) navigate('/profile', { replace: true, state: { welcome: 'kakao' } })
    else navigate(from, { replace: true })
  }, [callback.isSuccess, isNew, from, navigate])

  let body
  if (cancelled) {
    body = (
      <Status
        tone="ink"
        title="카카오 로그인을 취소했어요"
        detail="다른 방법으로 로그인하거나 다시 시도할 수 있어요."
      />
    )
  } else if (stateMismatch || !code) {
    body = (
      <Status
        tone="danger"
        title="로그인을 이어갈 수 없어요"
        detail="로그인 요청이 만료되었거나 올바르지 않습니다. 로그인 화면에서 다시 시도해 주세요."
      />
    )
  } else if (callback.isError) {
    body = <Status tone="danger" title="카카오로 로그인하지 못했어요" detail={describe(callback.error)} />
  } else if (callback.isSuccess) {
    body = <Status tone="moss" title="로그인 완료" detail="잠시 후 이동합니다." />
  } else {
    body = <Status tone="ink" title="카카오 계정 확인 중…" detail="잠시만 기다려 주세요." />
  }

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <div className="rounded-card border border-chalk-300 bg-white p-6">{body}</div>
      <p className="mt-4 text-center text-sm text-ink-400">
        <Link to="/login" className="inline-flex min-h-11 items-center font-medium text-hold-600 hover:underline">
          로그인으로 돌아가기
        </Link>
      </p>
    </div>
  )
}

/** 서버 error.code → 사용자 문장. 서버 메시지가 충분한 코드는 그대로 쓴다 */
function describe(error: unknown): string {
  switch (getErrorCode(error)) {
    case 'invalid_state':
      return '로그인 요청이 만료되었거나 올바르지 않습니다. 로그인 화면에서 다시 시도해 주세요.'
    case 'email_conflict':
      return '이미 같은 이메일로 가입된 계정이 있어요. 비밀번호로 로그인해 주세요.'
    case 'user_inactive':
      return '사용할 수 없는 계정이에요. 문의가 필요하면 관리자에게 연락해 주세요.'
    case 'throttled':
      return '시도가 너무 잦아요. 잠시 후 다시 시도해 주세요.'
    default:
      // kakao_error(502)·kakao_not_configured(503) 등은 서버 문구가 그대로 쓸 만하다
      return getErrorMessage(error, '카카오 로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.')
  }
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
}: {
  tone: keyof typeof TITLE
  title: string
  detail: string
}) {
  return (
    <div role={tone === 'danger' ? 'alert' : 'status'} className="space-y-2">
      <h1 className={`text-xl font-semibold ${TITLE[tone]}`}>{title}</h1>
      <p className="text-sm text-pretty text-ink-600">{detail}</p>
    </div>
  )
}
