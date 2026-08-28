import Button from '@/components/common/Button'
import { currentMonth, formatMonth, isValidMonth, shiftMonth } from '@/lib/month'

/**
 * 월 선택 — 이전/다음 버튼 + <input type="month">. 상태는 부모가 URL(?month=)에 둔다.
 * 다음 달은 이번 달(Asia/Seoul)까지만 — 미래 달은 항상 빈 통계라 막는다.
 */
export default function MonthPicker({
  month,
  onChange,
  label = '조회 월',
}: {
  month: string
  onChange: (month: string) => void
  label?: string
}) {
  const latest = currentMonth()
  const atLatest = month >= latest

  return (
    <div role="group" aria-label={label} className="flex items-center gap-1">
      <Button
        variant="secondary"
        aria-label="이전 달"
        className="min-w-11 px-0"
        onClick={() => onChange(shiftMonth(month, -1))}
      >
        <span aria-hidden>‹</span>
      </Button>
      <label className="block">
        <span className="sr-only">월 선택</span>
        <input
          type="month"
          value={month}
          max={latest}
          aria-label={`월 선택, ${formatMonth(month)}`}
          onChange={(e) => {
            // 지우면 '' 가 온다 — 유효한 값일 때만 반영
            if (isValidMonth(e.target.value)) onChange(e.target.value)
          }}
          className="min-h-11 rounded-xl border border-chalk-300 bg-white px-3 text-sm font-medium text-ink-700 transition-colors duration-150 tabular-nums focus:border-hold-300 focus:outline-none"
        />
      </label>
      <Button
        variant="secondary"
        aria-label="다음 달"
        className="min-w-11 px-0"
        disabled={atLatest}
        onClick={() => onChange(shiftMonth(month, 1))}
      >
        <span aria-hidden>›</span>
      </Button>
    </div>
  )
}
