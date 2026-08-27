import type { ComMetrics } from '@/api/analysis'

const VIEW_W = 100

interface Props {
  com: ComMetrics
  /** 영상 가로/세로 비 (keypoints 를 받았을 때). 모르면 정사각형으로 그린다 */
  aspect?: number | null
}

/**
 * 무게중심 궤적 — 화면 전체(0~1 정규화 좌표, y 는 아래로)를 한 장의 그림으로.
 * 단일 시리즈라 범례는 없고, 시작·끝 점만 색으로 구분한다 (텍스트 라벨은 ink 토큰).
 */
export default function ComTrajectory({ com, aspect }: Props) {
  const viewH = aspect && aspect > 0 ? VIEW_W / aspect : VIEW_W
  const toX = (x: number) => (x * VIEW_W).toFixed(2)
  const toY = (y: number) => (y * viewH).toFixed(2)
  const points = com.trajectory.map(([, x, y]) => `${toX(x)},${toY(y)}`).join(' ')
  const [sx, sy] = com.start
  const [ex, ey] = com.end

  // 마커 ≥ 8px 를 뷰박스 단위로 — 카드 폭(≈ 500px)에서 100 단위이므로 1.6 ≈ 8px
  const dotR = 1.6
  const label = `무게중심 이동 궤적. 시작 위치 x ${Math.round(sx * 100)}%, y ${Math.round(
    sy * 100,
  )}%에서 끝 위치 x ${Math.round(ex * 100)}%, y ${Math.round(ey * 100)}%까지 ${
    com.trajectory.length
  }개 점`

  return (
    <figure className="space-y-2">
      <svg
        role="img"
        aria-label={label}
        viewBox={`0 0 ${VIEW_W} ${viewH.toFixed(2)}`}
        className="h-auto w-full rounded-xl border border-chalk-300"
      >
        <rect x="0" y="0" width={VIEW_W} height={viewH} className="fill-chalk-100" />
        {/* 눈금은 조용하게 — 화면을 4등분하는 안내선 */}
        {[0.25, 0.5, 0.75].map((f) => (
          <g key={f} className="stroke-chalk-300" strokeWidth="0.3">
            <line x1={toX(f)} y1="0" x2={toX(f)} y2={viewH} />
            <line x1="0" y1={toY(f)} x2={VIEW_W} y2={toY(f)} />
          </g>
        ))}
        {com.trajectory.length > 1 && (
          <polyline
            points={points}
            fill="none"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
            className="stroke-hold-500"
          />
        )}
        <circle cx={toX(sx)} cy={toY(sy)} r={dotR} className="fill-moss-500 stroke-white" strokeWidth="0.4" />
        <circle cx={toX(ex)} cy={toY(ey)} r={dotR} className="fill-ochre-500 stroke-white" strokeWidth="0.4" />
      </svg>
      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-500">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-full bg-moss-500" />
          시작
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-full bg-ochre-500" />
          끝
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-0.5 w-4 rounded-full bg-hold-500" />
          무게중심 경로
        </span>
      </figcaption>
    </figure>
  )
}
