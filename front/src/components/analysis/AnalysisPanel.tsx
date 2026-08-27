import { useState } from 'react'

import {
  JOINT_NAMES,
  isAnalysisRunning,
  type AnalysisMetrics,
  type JointName,
  type VideoAnalysis,
} from '@/api/analysis'
import type { ClimbLog } from '@/api/climbs'
import { getErrorMessage } from '@/api/client'
import ComTrajectory from '@/components/analysis/ComTrajectory'
import PoseOverlay from '@/components/analysis/PoseOverlay'
import Button from '@/components/common/Button'
import { useAnalysisKeypoints, useLogAnalysis, useRequestAnalysis } from '@/hooks/useAnalysis'
import { useAuthStore } from '@/stores/authStore'

const percent = new Intl.NumberFormat('ko-KR', { style: 'percent', maximumFractionDigits: 0 })
const decimal2 = new Intl.NumberFormat('ko-KR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const degrees = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 })
const seconds = new Intl.NumberFormat('ko-KR', {
  style: 'unit',
  unit: 'second',
  maximumFractionDigits: 1,
})
const count = new Intl.NumberFormat('ko-KR')
const dateTime = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'short' })

const JOINT_LABEL: Record<JointName, string> = {
  leftElbow: '왼쪽 팔꿈치',
  rightElbow: '오른쪽 팔꿈치',
  leftKnee: '왼쪽 무릎',
  rightKnee: '오른쪽 무릎',
  leftHip: '왼쪽 고관절',
  rightHip: '오른쪽 고관절',
}

const CARD = 'rounded-card border border-chalk-300 bg-white p-4 md:p-5'

interface Props {
  log: Pick<ClimbLog, 'id' | 'videoUrl'>
  isOwner: boolean
}

/**
 * 기록 상세의 "자세 분석" 섹션. 영상이 있는 기록에서만 렌더링한다.
 * - 분석 없음: 작성자에게만 요청 버튼, 남에게는 섹션 자체를 숨긴다
 * - 대기/진행: 상태 표시 + 3초 폴링 (useLogAnalysis)
 * - 실패: 사유 + 작성자 재요청
 * - 완료: 지표 타일·관절 각도·무게중심 궤적, 원하면 스켈레톤 오버레이
 */
export default function AnalysisPanel({ log, isOwner }: Props) {
  const loggedIn = useAuthStore((s) => !!s.accessToken)
  const analysis = useLogAnalysis(log.id)
  const request = useRequestAnalysis(log.id)

  // 분석 API 는 로그인 전용 — 비로그인에겐 아무것도 보여줄 게 없다
  if (!loggedIn) return null
  if (analysis.isSuccess && analysis.data === null && !isOwner) return null

  const requestError = request.isError
    ? getErrorMessage(request.error, '분석을 요청하지 못했습니다. 잠시 후 다시 시도해 주세요.')
    : null

  return (
    <section aria-labelledby="analysis-heading" className="space-y-3">
      <h2 id="analysis-heading" className="text-base font-semibold text-ink-700">
        자세 분석
      </h2>

      {analysis.isPending && (
        <p role="status" className="text-sm text-ink-400">
          분석 정보를 불러오는 중…
        </p>
      )}
      {analysis.isError && (
        <p role="alert" className="text-sm text-danger-500">
          분석 정보를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.
        </p>
      )}

      {analysis.isSuccess && analysis.data === null && isOwner && (
        <div className={CARD}>
          <p className="text-sm font-medium text-ink-700">AI 가 영상 속 자세를 분석해 드려요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">
            무게중심 이동, 관절 각도, 동적·정적 무브 비율을 계산합니다. 영상 길이 2분 이하, 처리에
            몇 분 걸려요.
          </p>
          <Button
            variant="secondary"
            className="mt-3"
            onClick={() => request.mutate()}
            disabled={request.isPending}
          >
            {request.isPending ? '요청하는 중…' : 'AI 자세 분석 요청'}
          </Button>
          {requestError && (
            <p role="alert" className="mt-3 rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
              {requestError}
            </p>
          )}
        </div>
      )}

      {analysis.data && isAnalysisRunning(analysis.data) && (
        <Running analysis={analysis.data} />
      )}

      {analysis.data?.status === 'failed' && (
        <div role="alert" className={CARD}>
          <p className="text-sm font-medium text-danger-500">분석에 실패했어요</p>
          <p className="mt-1 text-sm text-pretty text-ink-600">
            {analysis.data.errorMessage || '분석 중 오류가 발생했습니다.'}
          </p>
          {analysis.data.retryCount > 0 && (
            <p className="mt-1 text-xs text-ink-400 tabular-nums">
              자동 재시도 {count.format(analysis.data.retryCount)}회
            </p>
          )}
          {isOwner && (
            <Button
              variant="secondary"
              className="mt-3"
              onClick={() => request.mutate()}
              disabled={request.isPending}
            >
              {request.isPending ? '요청하는 중…' : '다시 요청'}
            </Button>
          )}
          {requestError && (
            <p className="mt-3 rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
              {requestError}
            </p>
          )}
        </div>
      )}

      {analysis.data?.status === 'done' && (
        <Results analysis={analysis.data} videoUrl={log.videoUrl} />
      )}
    </section>
  )
}

// --- 진행 중 ---

function Running({ analysis }: { analysis: VideoAnalysis }) {
  return (
    <div role="status" className={CARD}>
      {/* React 19 가 <style> 을 head 로 끌어올리고 href 로 중복 제거한다.
          transform 만 움직이고, 모션 축소 설정에선 정지된 전체 바로 보인다 */}
      <style href="analysis-indeterminate" precedence="default">
        {'@keyframes analysis-indeterminate{from{transform:translateX(-100%)}to{transform:translateX(300%)}}'}
      </style>
      <p className="text-sm font-medium text-ink-700">
        {analysis.status === 'pending' ? '분석 대기 중…' : '분석 중…'}{' '}
        <span className="font-normal text-ink-400">(보통 1~3분)</span>
      </p>
      <div aria-hidden className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-chalk-200">
        <div className="h-full w-1/3 rounded-full bg-hold-500 animate-[analysis-indeterminate_1.4s_ease-in-out_infinite] motion-reduce:w-full motion-reduce:animate-none" />
      </div>
      <p className="mt-2 text-xs text-pretty text-ink-400">
        이 페이지를 떠나도 분석은 계속돼요. 완료되면 여기에 결과가 표시됩니다.
        {analysis.retryCount > 0 && (
          <span className="tabular-nums"> 자동 재시도 {count.format(analysis.retryCount)}회.</span>
        )}
      </p>
    </div>
  )
}

// --- 결과 ---

function Results({ analysis, videoUrl }: { analysis: VideoAnalysis; videoUrl: string }) {
  const [showSkeleton, setShowSkeleton] = useState(false)
  const keypoints = useAnalysisKeypoints(analysis.id, showSkeleton)
  const metrics = analysis.metrics

  if (!metrics) {
    return (
      <p role="status" className={`${CARD} text-sm text-ink-400`}>
        분석은 끝났지만 결과가 비어 있어요.
      </p>
    )
  }

  const aspect = keypoints.data ? keypoints.data.width / keypoints.data.height : null

  return (
    <div className="space-y-3">
      <div className={CARD}>
        <StatTiles metrics={metrics} processedAt={analysis.processedAt} />
        <p className="mt-3 text-xs text-pretty text-ink-400">
          위치 값은 화면 크기를 1로 본 비율이라 실제 거리(m)가 아니에요. 같은 각도·거리에서 찍은
          영상끼리 비교할 때 참고하세요.
        </p>
      </div>

      {metrics.com && (
        <div className={CARD}>
          <h3 className="text-sm font-semibold text-ink-700">무게중심 이동</h3>
          <div className="mt-3">
            <ComTrajectory com={metrics.com} aspect={aspect} />
          </div>
        </div>
      )}

      <JointTable angles={metrics.jointAngles} />

      <div className={CARD}>
        <h3 className="text-sm font-semibold text-ink-700">스켈레톤</h3>
        <p className="mt-1 text-xs text-pretty text-ink-400">
          영상 위에 감지된 관절 33개를 겹쳐 보여줍니다. 흐린 점은 가려졌거나 불확실한 부위예요.
        </p>
        {!showSkeleton && (
          <Button variant="secondary" className="mt-3" onClick={() => setShowSkeleton(true)}>
            스켈레톤 보기
          </Button>
        )}
        {showSkeleton && keypoints.isPending && (
          <p role="status" className="mt-3 text-sm text-ink-400">
            관절 데이터를 불러오는 중…
          </p>
        )}
        {showSkeleton && keypoints.isError && (
          <p role="alert" className="mt-3 text-sm text-danger-500">
            관절 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
          </p>
        )}
        {showSkeleton && keypoints.isSuccess && !keypoints.data && (
          <p role="status" className="mt-3 text-sm text-ink-400">
            저장된 관절 데이터가 없어요.
          </p>
        )}
        {showSkeleton && keypoints.data && (
          <div className="mt-3">
            <PoseOverlay videoUrl={videoUrl} keypoints={keypoints.data} />
          </div>
        )}
      </div>
    </div>
  )
}

function StatTiles({
  metrics,
  processedAt,
}: {
  metrics: AnalysisMetrics
  processedAt: string | null
}) {
  const { com, moveRatio } = metrics
  const tiles: { label: string; value: string; hint?: string }[] = [
    {
      label: '상승 높이',
      value: com ? percent.format(com.verticalGain) : '—',
      hint: '화면 높이 기준',
    },
    {
      label: '이동 경로 길이',
      value: com ? decimal2.format(com.pathLength) : '—',
      hint: '화면 크기 = 1',
    },
    {
      label: '동적 무브 비율',
      value: moveRatio ? percent.format(moveRatio.dynamic) : '—',
      hint: moveRatio ? `정적 ${percent.format(moveRatio.static)}` : undefined,
    },
    {
      label: '자세 감지율',
      value: percent.format(metrics.detectionRate),
      hint: `${count.format(metrics.detectedFrames)} / ${count.format(metrics.frameCount)} 프레임`,
    },
    { label: '영상 길이', value: seconds.format(metrics.duration) },
    {
      label: '처리 시각',
      value: processedAt ? dateTime.format(new Date(processedAt)) : '—',
    },
  ]

  return (
    <dl className="grid grid-cols-2 gap-2 md:grid-cols-3">
      {tiles.map((tile) => (
        <div key={tile.label} className="rounded-xl bg-chalk-100 px-3 py-2.5">
          <dt className="text-xs text-ink-400">{tile.label}</dt>
          <dd className="mt-0.5 text-lg font-semibold text-ink-700 tabular-nums">{tile.value}</dd>
          {tile.hint && <dd className="text-xs text-ink-400 tabular-nums">{tile.hint}</dd>}
        </div>
      ))}
    </dl>
  )
}

function JointTable({ angles }: { angles: AnalysisMetrics['jointAngles'] }) {
  const rows = JOINT_NAMES.filter((name) => angles[name])
  if (rows.length === 0) return null

  return (
    <div className={CARD}>
      <h3 className="text-sm font-semibold text-ink-700">관절 각도</h3>
      <p className="mt-1 text-xs text-pretty text-ink-400">
        관절을 꼭짓점으로 한 각도(°). 팔꿈치가 작을수록 많이 굽힌 상태예요.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-chalk-300 text-left text-xs text-ink-400">
              <th scope="col" className="py-2 pr-2 font-medium">
                관절
              </th>
              <th scope="col" className="py-2 px-2 text-right font-medium">
                평균
              </th>
              <th scope="col" className="py-2 px-2 text-right font-medium">
                최소
              </th>
              <th scope="col" className="py-2 pl-2 text-right font-medium">
                최대
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-chalk-200">
            {rows.map((name) => {
              const stat = angles[name]!
              return (
                <tr key={name}>
                  <th scope="row" className="py-2 pr-2 text-left font-normal text-ink-600">
                    {JOINT_LABEL[name]}
                  </th>
                  <td className="py-2 px-2 text-right text-ink-700 tabular-nums">
                    {degrees.format(stat.mean)}°
                  </td>
                  <td className="py-2 px-2 text-right text-ink-500 tabular-nums">
                    {degrees.format(stat.min)}°
                  </td>
                  <td className="py-2 pl-2 text-right text-ink-500 tabular-nums">
                    {degrees.format(stat.max)}°
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
