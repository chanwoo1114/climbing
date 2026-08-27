import type { SelectHTMLAttributes } from 'react'

export interface SelectOption {
  value: string
  label: string
}

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  options: SelectOption[]
  /** 선택 안 함 항목의 라벨. 주면 value="" 옵션이 맨 위에 붙는다 */
  placeholder?: string
  /** 라벨 아래 보조 설명 */
  hint?: string
  /** 서버 검증 오류 등 — 있으면 빨간 보더 + role=alert 메시지 */
  error?: string
}

export default function SelectField({
  label,
  id,
  options,
  placeholder,
  hint,
  error,
  ...rest
}: Props) {
  const inputId = id ?? rest.name
  const hintId = `${inputId}-hint`
  const errorId = `${inputId}-error`
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(' ') || undefined

  return (
    <div>
      <label htmlFor={inputId} className="block">
        <span className="mb-1 block text-sm font-medium text-ink-500">{label}</span>
        <div className="relative">
          <select
            id={inputId}
            aria-invalid={!!error}
            aria-describedby={describedBy}
            className={`min-h-11 w-full appearance-none rounded-xl border bg-white px-3 py-2.5 pr-9 text-ink-700 transition-colors duration-150 focus:outline-none disabled:opacity-50 ${
              error
                ? 'border-danger-500 focus:border-danger-600'
                : 'border-chalk-300 focus:border-hold-300'
            }`}
            {...rest}
          >
            {placeholder !== undefined && <option value="">{placeholder}</option>}
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {/* 브라우저 기본 화살표 대신 — appearance-none 의 대체 표시 */}
          <span
            aria-hidden
            className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-xs text-ink-400"
          >
            ▼
          </span>
        </div>
      </label>
      {error ? (
        <p id={errorId} role="alert" className="mt-1 text-xs text-pretty text-danger-500">
          {error}
        </p>
      ) : (
        hint && (
          <p id={hintId} className="mt-1 text-xs text-pretty text-ink-400">
            {hint}
          </p>
        )
      )}
    </div>
  )
}
