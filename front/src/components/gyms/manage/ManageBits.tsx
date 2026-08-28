import type { ReactNode } from 'react'

/** 관리 화면 섹션 카드 — Settings 의 Card 와 같은 규칙 (white + chalk-300 보더, rounded-card) */
export function Card({
  id,
  title,
  description,
  children,
}: {
  id: string
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section
      aria-labelledby={id}
      className="space-y-4 rounded-card border border-chalk-300 bg-white p-5 md:p-6"
    >
      <div>
        <h2 id={id} className="text-base font-semibold text-ink-700">
          {title}
        </h2>
        {description && <p className="mt-1 text-sm text-pretty text-ink-400">{description}</p>}
      </div>
      {children}
    </section>
  )
}

export function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-pretty text-danger-600">
      {children}
    </p>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed border-chalk-400 bg-chalk-50 px-4 py-6 text-center text-sm text-pretty text-ink-400">
      {children}
    </p>
  )
}

export const krw = new Intl.NumberFormat('ko-KR', { style: 'currency', currency: 'KRW' })
export const sinceDate = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium' })
