import type { InputHTMLAttributes } from 'react'

import type { FieldCheck } from '@/lib/validation'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  /** 실시간 검증 결과. idle이면 평상시 스타일 */
  check?: FieldCheck
}

// 포커스는 outline 대신 보더색으로 표시한다 (outline-none 의 대체 수단).
const BORDER = {
  idle: 'border-chalk-300 focus:border-hold-300',
  valid: 'border-moss-400 focus:border-moss-500',
  invalid: 'border-danger-500 focus:border-danger-600',
} as const

const MESSAGE = {
  idle: '',
  valid: 'text-moss-500',
  invalid: 'text-danger-500',
} as const

// 이메일 칸은 모바일 자동 대문자·자동 수정·맞춤법 검사가 입력을 망친다.
const EMAIL_DEFAULTS = {
  spellCheck: false,
  autoCapitalize: 'none',
  autoCorrect: 'off',
  inputMode: 'email',
} as const

export default function TextField({ label, id, check, type, ...rest }: Props) {
  const inputId = id ?? rest.name
  const state = check?.state ?? 'idle'
  const messageId = `${inputId}-message`
  const hasMessage = state !== 'idle' && !!check?.message

  return (
    <div>
      <label htmlFor={inputId} className="block">
        <span className="mb-1 block text-sm font-medium text-ink-500">{label}</span>
        <div className="relative">
          <input
            id={inputId}
            type={type}
            aria-invalid={state === 'invalid'}
            aria-describedby={hasMessage ? messageId : undefined}
            className={`min-h-11 w-full rounded-xl border bg-white px-3 py-2.5 pr-9 text-ink-700 transition-colors duration-150 placeholder:text-ink-300 focus:outline-none disabled:cursor-not-allowed disabled:bg-chalk-100 disabled:text-ink-400 ${BORDER[state]}`}
            {...(type === 'email' ? EMAIL_DEFAULTS : {})}
            {...rest}
          />
          {state !== 'idle' && (
            <span
              aria-hidden
              className={`pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm ${MESSAGE[state]}`}
            >
              {state === 'valid' ? '✓' : '✕'}
            </span>
          )}
        </div>
      </label>
      {/* 입력 중 바뀌는 메시지 — 스크린리더에 조용히 알린다 */}
      <p
        id={messageId}
        aria-live="polite"
        className={`mt-1 text-xs text-pretty ${MESSAGE[state]} ${hasMessage ? '' : 'hidden'}`}
      >
        {hasMessage ? check.message : ''}
      </p>
    </div>
  )
}
