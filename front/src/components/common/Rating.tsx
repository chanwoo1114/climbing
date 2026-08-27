/**
 * 별점 — 읽기(RatingStars)와 입력(RatingInput).
 * 별 색은 서브 포인트(ochre). hold 는 CTA 전용이라 쓰지 않는다.
 */
export const RATING_MAX = 5
const STARS = [1, 2, 3, 4, 5]

const score = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 })

interface StarsProps {
  /** 1~5. 평균처럼 소수여도 되고, 별은 반올림해서 채운다 */
  value: number
  className?: string
}

export function RatingStars({ value, className = '' }: StarsProps) {
  const filled = Math.round(value)
  return (
    <span
      role="img"
      aria-label={`${RATING_MAX}점 만점에 ${score.format(value)}점`}
      className={`inline-flex gap-0.5 leading-none ${className}`}
    >
      {STARS.map((n) => (
        <span key={n} aria-hidden className={n <= filled ? 'text-ochre-400' : 'text-chalk-400'}>
          ★
        </span>
      ))}
    </span>
  )
}

interface InputProps {
  /** 0 이면 아직 고르지 않음 */
  value: number
  onChange: (value: number) => void
  name?: string
  disabled?: boolean
  /** 서버 검증 오류 등 */
  error?: string
}

// 네이티브 radio 를 sr-only 로 두고 label 을 별 모양으로 그린다 — 방향키 이동·폼 시맨틱은 브라우저 몫.
// 각 별은 44px(size-11) 터치 영역. 포커스 링은 숨은 input 대신 label 에 peer 로 옮겨 그린다.
const STAR_LABEL =
  'inline-flex size-11 cursor-pointer items-center justify-center rounded-xl text-2xl leading-none ' +
  'transition-colors duration-150 ' +
  'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-hold-500 ' +
  'peer-disabled:cursor-not-allowed peer-disabled:opacity-50'

export function RatingInput({ value, onChange, name = 'rating', disabled, error }: InputProps) {
  const errorId = `${name}-error`
  return (
    <fieldset aria-describedby={error ? errorId : undefined}>
      <legend className="mb-1 block text-sm font-medium text-ink-500">별점</legend>
      <div className="-ml-2 flex items-center">
        {STARS.map((n) => {
          const id = `${name}-${n}`
          return (
            <span key={n}>
              <input
                type="radio"
                id={id}
                name={name}
                value={n}
                checked={value === n}
                onChange={() => onChange(n)}
                disabled={disabled}
                aria-invalid={!!error}
                className="peer sr-only"
              />
              <label
                htmlFor={id}
                className={`${STAR_LABEL} ${
                  n <= value ? 'text-ochre-400' : 'text-chalk-400 hover:text-ochre-400'
                }`}
              >
                <span aria-hidden>★</span>
                <span className="sr-only">{n}점</span>
              </label>
            </span>
          )
        })}
        <span aria-hidden className="ml-1 text-sm text-ink-400 tabular-nums">
          {value > 0 ? `${value}점` : '별을 눌러 선택'}
        </span>
      </div>
      {error && (
        <p id={errorId} role="alert" className="mt-1 text-xs text-pretty text-danger-500">
          {error}
        </p>
      )}
    </fieldset>
  )
}
