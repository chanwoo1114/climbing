import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type { AnalysisKeypoints, KeypointFrame } from '@/api/analysis'

/** MediaPipe Pose 표준 연결선 (POSE_CONNECTIONS) */
const CONNECTIONS: readonly [number, number][] = [
  // 얼굴
  [0, 1], [1, 2], [2, 3], [3, 7], [0, 4], [4, 5], [5, 6], [6, 8], [9, 10],
  // 상체
  [11, 12], [11, 13], [13, 15], [15, 17], [15, 19], [15, 21], [17, 19],
  [12, 14], [14, 16], [16, 18], [16, 20], [16, 22], [18, 20],
  // 몸통
  [11, 23], [12, 24], [23, 24],
  // 하체
  [23, 25], [24, 26], [25, 27], [26, 28], [27, 29], [28, 30], [29, 31], [30, 32], [27, 31], [28, 32],
]

/** 이 값 미만의 visibility 는 가려졌거나 불확실한 점 — 흐리게 그린다 */
const VISIBLE = 0.5

const seconds = new Intl.NumberFormat('ko-KR', {
  style: 'unit',
  unit: 'second',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

/** t 로 정렬된 프레임에서 time 에 가장 가까운 프레임 인덱스 (이진 탐색) */
export function nearestFrameIndex(frames: readonly KeypointFrame[], time: number): number {
  if (frames.length === 0) return -1
  let lo = 0
  let hi = frames.length - 1
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (frames[mid].t < time) lo = mid + 1
    else hi = mid
  }
  // lo 는 time 이상인 첫 프레임 — 바로 앞 프레임이 더 가까울 수 있다
  if (lo > 0 && Math.abs(frames[lo - 1].t - time) <= Math.abs(frames[lo].t - time)) return lo - 1
  return lo
}

interface Props {
  videoUrl: string
  keypoints: AnalysisKeypoints
}

/**
 * 영상 위에 랜드마크·연결선 SVG 를 겹친다. 재생 중엔 rAF 로, 멈춰 있을 땐 timeupdate 로
 * currentTime 을 따라간다. 영상이 재생되지 않으면(원격 파일 오류 등) 슬라이더로 훑어볼 수 있다.
 */
export default function PoseOverlay({ videoUrl, keypoints }: Props) {
  const { width, height, frames, duration } = keypoints
  const videoRef = useRef<HTMLVideoElement>(null)
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [videoFailed, setVideoFailed] = useState(false)

  const frameIndex = useMemo(() => nearestFrameIndex(frames, time), [frames, time])
  const frame = frameIndex >= 0 ? frames[frameIndex] : null

  const syncTime = useCallback(() => {
    const video = videoRef.current
    if (video) setTime(video.currentTime)
  }, [])

  // 재생 중에는 timeupdate(약 4Hz)만으로는 스켈레톤이 뚝뚝 끊겨서 프레임마다 맞춘다
  useEffect(() => {
    if (!playing) return
    let raf = 0
    const tick = () => {
      syncTime()
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, syncTime])

  const onScrub = (value: number) => {
    setTime(value)
    const video = videoRef.current
    if (video && !videoFailed) video.currentTime = value
  }

  const scrubMax = duration || frames[frames.length - 1]?.t || 0

  return (
    <div className="space-y-2">
      <div
        className="relative w-full overflow-hidden rounded-xl bg-ink-700"
        style={{ aspectRatio: `${width} / ${height}` }}
      >
        {!videoFailed && (
          <video
            ref={videoRef}
            src={videoUrl}
            controls
            playsInline
            preload="metadata"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onTimeUpdate={syncTime}
            onSeeked={syncTime}
            onError={() => {
              setPlaying(false)
              setVideoFailed(true)
            }}
            className="absolute inset-0 size-full"
          />
        )}
        <svg
          aria-hidden
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          className="pointer-events-none absolute inset-0 size-full"
        >
          {frame?.lm && <Skeleton lm={frame.lm} width={width} height={height} />}
        </svg>
      </div>

      {videoFailed && (
        <p role="alert" className="text-xs text-pretty text-danger-500">
          영상을 재생할 수 없어 스켈레톤만 보여드려요. 아래 슬라이더로 구간을 옮길 수 있어요.
        </p>
      )}

      {videoFailed && (
        <label className="flex min-h-11 items-center gap-3 text-xs text-ink-500">
          <span className="shrink-0">재생 위치</span>
          <input
            type="range"
            min={0}
            max={scrubMax}
            step={0.05}
            value={Math.min(time, scrubMax)}
            onChange={(e) => onScrub(Number(e.target.value))}
            aria-valuetext={seconds.format(time)}
            className="min-h-11 w-full accent-hold-500"
          />
        </label>
      )}

      <p className="text-xs text-ink-400 tabular-nums">
        {seconds.format(time)}
        {frame && !frame.lm && (
          <span className="text-ink-500"> · 이 구간에서는 자세를 찾지 못했어요</span>
        )}
      </p>
    </div>
  )
}

function Skeleton({
  lm,
  width,
  height,
}: {
  lm: NonNullable<KeypointFrame['lm']>
  width: number
  height: number
}) {
  // 선 2px·점 8px 를 뷰박스 단위로 환산 — 영상 너비가 어떻든 화면에서는 같은 굵기로 보인다
  const unit = width / 100
  const r = unit * 1.2
  const visible = (i: number) => (lm[i]?.[3] ?? 0) >= VISIBLE

  return (
    <g>
      <g strokeWidth={unit * 0.5} strokeLinecap="round" className="stroke-hold-300">
        {CONNECTIONS.map(([a, b]) => {
          const pa = lm[a]
          const pb = lm[b]
          if (!pa || !pb) return null
          const dim = !visible(a) || !visible(b)
          return (
            <line
              key={`${a}-${b}`}
              x1={pa[0] * width}
              y1={pa[1] * height}
              x2={pb[0] * width}
              y2={pb[1] * height}
              opacity={dim ? 0.3 : 0.9}
            />
          )
        })}
      </g>
      <g className="fill-ochre-400 stroke-white" strokeWidth={unit * 0.25}>
        {lm.map((p, i) => (
          <circle key={i} cx={p[0] * width} cy={p[1] * height} r={r} opacity={visible(i) ? 1 : 0.3} />
        ))}
      </g>
    </g>
  )
}
