import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'danger'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  /** 부모 너비를 꽉 채운다 (폼 제출 버튼) */
  full?: boolean
}

// min-h-11 = 44px 터치 영역. 전환은 바뀌는 속성만 명시 (transition-all 금지).
// 누름 피드백 scale(0.97) 은 모션 축소 설정이면 꺼진다.
const BASE =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 font-medium ' +
  'transition-[background-color,color,border-color,transform] duration-150 ease-out ' +
  'active:scale-[0.97] motion-reduce:active:scale-100 ' +
  'disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100'

const VARIANT: Record<Variant, string> = {
  // hold-500 은 화면당 주요 CTA 1개에만
  primary: 'bg-hold-500 text-white hover:bg-hold-600',
  secondary: 'border border-chalk-300 bg-white text-ink-600 hover:bg-chalk-100',
  // 삭제 확인 등 파괴적 액션 전용 — 확인 모달 안에서만 쓴다
  danger: 'bg-danger-500 text-white hover:bg-danger-600',
}

export default function Button({
  variant = 'primary',
  full = false,
  type = 'button',
  className = '',
  ...rest
}: Props) {
  return (
    <button
      type={type}
      className={`${BASE} ${VARIANT[variant]} ${full ? 'w-full' : ''} ${className}`}
      {...rest}
    />
  )
}
