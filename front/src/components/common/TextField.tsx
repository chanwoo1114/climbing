import type { InputHTMLAttributes } from 'react'

import type { FieldCheck } from '@/lib/validation'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  /** 실시간 검증 결과. idle이면 평상시 스타일 */
  check?: FieldCheck
}

const BORDER = {
  idle: 'border-chalk-300 focus:border-terra-300',
  valid: 'border-moss-400 focus:border-moss-500',
  invalid: 'border-danger-500 focus:border-danger-600',
} as const

const MESSAGE = {
  idle: '',
  valid: 'text-moss-500',
  invalid: 'text-danger-500',
} as const

export default function TextField({ label, id, check, ...rest }: Props) {
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
            aria-invalid={state === 'invalid'}
            aria-describedby={hasMessage ? messageId : undefined}
            className={`w-full rounded-xl border bg-white px-3 py-2.5 pr-9 text-ink-700 placeholder:text-ink-300 focus:outline-none ${BORDER[state]}`}
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
      {hasMessage && (
        <p id={messageId} className={`mt-1 text-xs ${MESSAGE[state]}`}>
          {check.message}
        </p>
      )}
    </div>
  )
}
