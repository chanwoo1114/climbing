import type { TextareaHTMLAttributes } from 'react'

import type { FieldCheck } from '@/lib/validation'

interface Props extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
  check?: FieldCheck
  /** 현재 글자 수 / 최대 글자 수를 오른쪽 아래에 표시한다 (maxLength 필요) */
  showCount?: boolean
}

// TextField 와 같은 보더 규칙 — 포커스는 outline 대신 보더색으로 표시
const BORDER = {
  idle: 'border-chalk-300 focus:border-hold-300',
  valid: 'border-moss-400 focus:border-moss-500',
  invalid: 'border-danger-500 focus:border-danger-600',
} as const

const MESSAGE = {
  idle: 'text-ink-400',
  valid: 'text-moss-500',
  invalid: 'text-danger-500',
} as const

export default function TextArea({
  label,
  id,
  check,
  showCount = false,
  maxLength,
  value,
  ...rest
}: Props) {
  const inputId = id ?? rest.name
  const state = check?.state ?? 'idle'
  const messageId = `${inputId}-message`
  const hasMessage = state !== 'idle' && !!check?.message
  const length = typeof value === 'string' ? value.length : 0

  return (
    <div>
      <label htmlFor={inputId} className="block">
        <span className="mb-1 block text-sm font-medium text-ink-500">{label}</span>
        <textarea
          id={inputId}
          maxLength={maxLength}
          value={value}
          aria-invalid={state === 'invalid'}
          aria-describedby={hasMessage ? messageId : undefined}
          className={`min-h-28 w-full resize-y rounded-xl border bg-white px-3 py-2.5 text-ink-700 transition-colors duration-150 placeholder:text-ink-300 focus:outline-none ${BORDER[state]}`}
          {...rest}
        />
      </label>
      <div className="mt-1 flex items-start justify-between gap-2 text-xs">
        <p
          id={messageId}
          aria-live="polite"
          className={`text-pretty ${MESSAGE[state]} ${hasMessage ? '' : 'sr-only'}`}
        >
          {hasMessage ? check.message : ''}
        </p>
        {showCount && maxLength !== undefined && (
          <span className="ml-auto shrink-0 text-ink-400 tabular-nums">
            {length}/{maxLength}
          </span>
        )}
      </div>
    </div>
  )
}
