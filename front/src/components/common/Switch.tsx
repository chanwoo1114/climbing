import { useId } from 'react'

interface Props {
  label: string
  description?: string
  checked: boolean
  disabled?: boolean
  onChange: (next: boolean) => void
}

/**
 * 접근 가능한 토글 — <button role="switch" aria-checked>. 트랙은 24px 이지만 버튼 자체가
 * 44px 터치 영역을 갖는다. 켜짐은 moss(성공) 색 — hold 는 화면당 CTA 1개에만 쓴다.
 */
export default function Switch({ label, description, checked, disabled, onChange }: Props) {
  const labelId = useId()
  const descriptionId = useId()
  return (
    <div className="flex items-center gap-3">
      <div className="min-w-0 flex-1">
        <p id={labelId} className="text-sm font-medium text-ink-700">
          {label}
        </p>
        {description && (
          <p id={descriptionId} className="mt-0.5 text-xs text-pretty text-ink-400">
            {description}
          </p>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={labelId}
        aria-describedby={description ? descriptionId : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-xl disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span
          aria-hidden
          className={`relative inline-block h-6 w-11 rounded-full transition-colors duration-150 ${
            checked ? 'bg-moss-500' : 'bg-chalk-400'
          }`}
        >
          <span
            className={`absolute top-0.5 left-0.5 size-5 rounded-full bg-white transition-transform duration-150 ${
              checked ? 'translate-x-5' : 'translate-x-0'
            }`}
          />
        </span>
      </button>
    </div>
  )
}
