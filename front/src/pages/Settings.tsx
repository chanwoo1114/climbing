import { useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router'

import { getErrorCode, getErrorMessage, getFieldError } from '@/api/client'
import Button from '@/components/common/Button'
import PasswordRuleList from '@/components/common/PasswordRuleList'
import Switch from '@/components/common/Switch'
import TextField from '@/components/common/TextField'
import WithdrawDialog from '@/components/settings/WithdrawDialog'
import { useChangePassword, useMe, useWithdraw } from '@/hooks/useAuth'
import { useNotificationSettings, useUpdateNotificationSettings } from '@/hooks/useNotifications'
import { usePushSubscription, type PushStatus } from '@/hooks/usePush'
import { useToastStore } from '@/stores/toastStore'
import {
  checkPassword,
  checkPasswordConfirm,
  checkRequired,
  PASSWORD_MAX_LENGTH,
  type FieldCheck,
} from '@/lib/validation'

const IDLE: FieldCheck = { state: 'idle', message: '' }

/** 계정 설정 — 알림 · 브라우저 푸시 · 비밀번호 변경 · 회원 탈퇴 */
export default function Settings() {
  return (
    <div className="mx-auto mt-4 max-w-sm space-y-4 md:mt-10">
      <h1 className="text-2xl font-semibold text-ink-700">설정</h1>
      <NotificationSection />
      <PushSection />
      <PasswordSection />
      <WithdrawSection />
    </div>
  )
}

function Card({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section
      aria-labelledby={id}
      className="space-y-3 rounded-card border border-chalk-300 bg-white p-6"
    >
      <h2 id={id} className="text-base font-semibold text-ink-700">
        {title}
      </h2>
      {children}
    </section>
  )
}

function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-pretty text-danger-600">
      {children}
    </p>
  )
}

// --- 알림 설정 ---

function NotificationSection() {
  const settings = useNotificationSettings()
  const update = useUpdateNotificationSettings()

  let body
  if (settings.isPending) {
    body = (
      <p role="status" className="text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  } else if (settings.isError || !settings.data) {
    body = <ErrorBanner>알림 설정을 불러오지 못했습니다. 잠시 후 새로고침해 주세요.</ErrorBanner>
  } else {
    body = (
      <div className="divide-y divide-chalk-200">
        <div className="py-2">
          <Switch
            label="이메일 알림"
            description="모집·크루 결과, 분석 완료"
            checked={settings.data.emailEnabled}
            onChange={(emailEnabled) => update.mutate({ emailEnabled })}
          />
        </div>
        <div className="py-2">
          <Switch
            label="브라우저 푸시"
            description="아래에서 이 브라우저를 구독해야 실제로 도착해요"
            checked={settings.data.pushEnabled}
            onChange={(pushEnabled) => update.mutate({ pushEnabled })}
          />
        </div>
      </div>
    )
  }

  return (
    <Card id="settings-notifications" title="알림 설정">
      {body}
      {update.isError && (
        <ErrorBanner>
          {getErrorMessage(update.error, '설정을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </ErrorBanner>
      )}
    </Card>
  )
}

// --- 브라우저 푸시 구독 ---

const PUSH_HINT: Record<PushStatus, string> = {
  unsupported: '이 브라우저는 푸시를 지원하지 않습니다.',
  not_configured: '이 서버에는 푸시가 설정되어 있지 않습니다.',
  denied: '알림 권한이 거부되어 있어요. 브라우저 사이트 설정에서 알림을 허용한 뒤 다시 시도해 주세요.',
  subscribed: '이 브라우저로 푸시를 받고 있어요.',
  unsubscribed: '구독하면 탭을 닫아도 새 알림을 받을 수 있어요.',
  busy: '확인 중…',
}

function PushSection() {
  const push = usePushSubscription()
  const subscribed = push.status === 'subscribed'
  const busy = push.status === 'busy'
  const disabled = !(push.status === 'subscribed' || push.status === 'unsubscribed')

  return (
    <Card id="settings-push" title="브라우저 푸시 구독">
      <Switch
        label="이 브라우저에서 받기"
        description="기기마다 따로 구독합니다"
        checked={subscribed}
        disabled={disabled}
        onChange={(next) => (next ? push.subscribe() : push.unsubscribe())}
      />
      <p role={busy ? 'status' : undefined} className="text-xs text-pretty text-ink-400">
        {PUSH_HINT[push.status]}
      </p>
      {push.error && <ErrorBanner>{push.error}</ErrorBanner>}
    </Card>
  )
}

// --- 비밀번호 변경 ---

function PasswordSection() {
  const { data: me } = useMe()
  const change = useChangePassword()
  const pushToast = useToastStore((s) => s.push)

  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')

  const error = change.error
  const context = { email: me?.email, nickname: me?.nickname }
  const withServerError = (check: FieldCheck, field: string): FieldCheck => {
    const serverMessage = getFieldError(error, field)
    return serverMessage ? { state: 'invalid', message: serverMessage } : check
  }
  const currentCheck = withServerError(checkRequired(current, '현재 비밀번호'), 'current_password')
  const nextCheck = withServerError(checkPassword(next, context), 'new_password')
  const confirmCheck = checkPasswordConfirm(next, confirm)

  const canSubmit =
    current.trim().length > 0 &&
    checkPassword(next, context).state === 'valid' &&
    confirmCheck.state === 'valid'
  const pending = change.isPending

  const edit =
    (setter: (value: string) => void) => (e: { target: { value: string } }) => {
      if (change.isError) change.reset()
      setter(e.target.value)
    }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || pending) return
    change.mutate(
      { currentPassword: current, newPassword: next },
      {
        onSuccess: () => {
          setCurrent('')
          setNext('')
          setConfirm('')
          pushToast({
            title: '비밀번호를 변경했습니다.',
            description: '다른 기기에서는 다시 로그인해야 합니다.',
          })
        },
      },
    )
  }

  const noPassword = getErrorCode(error) === 'no_password'
  const generalError =
    error && !getFieldError(error, 'current_password') && !getFieldError(error, 'new_password')
      ? getErrorMessage(error, '비밀번호를 변경하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      : null

  return (
    <Card id="settings-password" title="비밀번호 변경">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <TextField
          label="현재 비밀번호"
          name="currentPassword"
          type="password"
          autoComplete="current-password"
          required
          maxLength={PASSWORD_MAX_LENGTH}
          value={current}
          check={currentCheck.state === 'valid' ? IDLE : currentCheck}
          onChange={edit(setCurrent)}
        />
        <div>
          <TextField
            label="새 비밀번호"
            name="newPassword"
            type="password"
            autoComplete="new-password"
            placeholder="8~16자, 영문·숫자·특수문자 2종 조합"
            required
            maxLength={PASSWORD_MAX_LENGTH}
            value={next}
            check={
              // 조건별 상세는 아래 체크리스트가 담당 — 필드에는 상태(색)와 서버 메시지만
              nextCheck.state === 'idle'
                ? nextCheck
                : { ...nextCheck, message: getFieldError(error, 'new_password') ?? '' }
            }
            onChange={edit(setNext)}
          />
          <PasswordRuleList password={next} context={context} />
        </div>
        <TextField
          label="새 비밀번호 확인"
          name="newPasswordConfirm"
          type="password"
          autoComplete="new-password"
          required
          maxLength={PASSWORD_MAX_LENGTH}
          value={confirm}
          check={confirmCheck}
          onChange={edit(setConfirm)}
        />
        {generalError && (
          <ErrorBanner>
            {generalError}
            {noPassword && (
              <>
                {' '}
                <Link to="/forgot-password" className="font-medium underline underline-offset-2">
                  비밀번호 재설정하기
                </Link>
              </>
            )}
          </ErrorBanner>
        )}
        <Button type="submit" full disabled={!canSubmit || pending}>
          {pending ? '변경 중…' : '비밀번호 변경'}
        </Button>
      </form>
    </Card>
  )
}

// --- 회원 탈퇴 ---

function WithdrawSection() {
  const withdraw = useWithdraw()
  const [open, setOpen] = useState(false)

  return (
    <Card id="settings-withdraw" title="회원 탈퇴">
      <p className="text-sm text-pretty text-ink-500">
        기록·댓글·팔로우가 모두 삭제되며 되돌릴 수 없습니다. 크루장인 크루가 있다면 먼저 위임하거나
        삭제해 주세요.
      </p>
      <Button
        variant="secondary"
        className="text-danger-600"
        onClick={() => {
          withdraw.reset()
          setOpen(true)
        }}
      >
        회원 탈퇴
      </Button>
      <WithdrawDialog
        open={open}
        pending={withdraw.isPending}
        error={withdraw.error}
        onConfirm={(password) => withdraw.mutate(password)}
        onCancel={() => {
          if (!withdraw.isPending) setOpen(false)
        }}
      />
    </Card>
  )
}
