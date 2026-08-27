import { Link } from 'react-router'

import { useToastStore, type Toast } from '@/stores/toastStore'

/**
 * 토스트 영역 — RootLayout 에 한 번만 둔다. 모바일은 아래 가운데, md: 이상은 오른쪽 위.
 * 영역 자체가 항상 렌더되는 live region 이라 스크린리더가 새 토스트를 읽어준다.
 * 등장 애니메이션은 transform/opacity 만 (index.css --animate-toast-in), 모션 축소면 끈다.
 */
export default function ToastRegion() {
  const toasts = useToastStore((s) => s.toasts)
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-4 bottom-4 z-30 flex flex-col items-center gap-2 md:inset-x-auto md:top-4 md:right-4 md:bottom-auto md:items-end"
    >
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} />
      ))}
    </div>
  )
}

function CloseIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    >
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  )
}

const BODY = 'flex min-h-11 min-w-0 flex-1 flex-col justify-center py-2 pl-4 text-left'

function ToastCard({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss)
  const body = (
    <>
      <p className="text-sm font-medium text-pretty break-words text-ink-700">{toast.title}</p>
      {toast.description && (
        <p className="mt-0.5 text-xs text-pretty break-words text-ink-400">{toast.description}</p>
      )}
    </>
  )
  return (
    <div className="pointer-events-auto flex w-full max-w-sm items-stretch rounded-card border border-chalk-300 bg-white shadow-sm motion-safe:animate-toast-in motion-reduce:animate-none">
      {toast.href ? (
        <Link
          to={toast.href}
          onClick={() => dismiss(toast.id)}
          className={`${BODY} rounded-l-card transition-colors duration-150 hover:bg-chalk-100`}
        >
          {body}
        </Link>
      ) : (
        <div className={BODY}>{body}</div>
      )}
      <button
        type="button"
        aria-label="알림 닫기"
        onClick={() => dismiss(toast.id)}
        className="inline-flex size-11 shrink-0 items-center justify-center self-start rounded-r-card text-ink-400 transition-colors duration-150 hover:text-ink-600"
      >
        <CloseIcon />
      </button>
    </div>
  )
}
