import { useEffect, useId, useRef } from 'react'

import Button from '@/components/common/Button'

/**
 * 파괴적·되돌리기 어려운 액션 확인 — 네이티브 <dialog> 가 포커스 가두기·Esc·바깥 배경을 맡는다.
 * 진행 중에는 Esc 로 닫히지 않게 막는다. (pages/LogDetail 의 것과 같은 규칙)
 */
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  pendingLabel = '처리 중…',
  variant = 'danger',
  pending,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  pendingLabel?: string
  /** danger: 삭제 등 파괴적 액션 / primary: 마감처럼 되돌릴 수 없지만 파괴적이진 않은 액션 */
  variant?: 'danger' | 'primary'
  pending: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    else if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onClose={onCancel}
      onCancel={(e) => {
        if (pending) e.preventDefault()
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-sm rounded-card border border-chalk-300 bg-white p-6 text-ink-600 backdrop:bg-ink-700/40"
    >
      <h2 id={titleId} className="text-base font-semibold text-ink-700">
        {title}
      </h2>
      <p id={descriptionId} className="mt-1 text-sm text-pretty text-ink-500">
        {description}
      </p>
      <div className="mt-5 flex justify-end gap-2">
        {/* 기본 포커스는 취소 — Enter 연타로 실행되지 않게 */}
        <Button variant="secondary" onClick={onCancel} disabled={pending} autoFocus>
          취소
        </Button>
        <Button variant={variant} onClick={onConfirm} disabled={pending}>
          {pending ? pendingLabel : confirmLabel}
        </Button>
      </div>
    </dialog>
  )
}
