import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchAnalysisWithKeypoints,
  fetchLogAnalysis,
  isAnalysisRunning,
  requestAnalysis,
  type VideoAnalysis,
} from '@/api/analysis'
import { useAuthStore } from '@/stores/authStore'

/**
 * 쿼리 키
 * - ['analyses', 'log', logId]        기록의 분석 1건 (없으면 null)
 * - ['analyses', id, 'keypoints']     랜드마크 포함 상세 — 크고 불변이라 staleTime Infinity
 */
const logAnalysisKey = (logId: number) => ['analyses', 'log', logId] as const
const keypointsKey = (id: number) => ['analyses', id, 'keypoints'] as const

/** 대기/진행 중일 때 상태를 다시 묻는 간격 */
const POLL_INTERVAL_MS = 3_000

/**
 * 기록의 분석 상태/결과. 분석 API 는 로그인 전용이라 토큰이 없으면 부르지 않는다.
 * pending/processing 동안만 3초마다 폴링하고, 끝나면(done/failed/없음) 멈춘다.
 */
export function useLogAnalysis(logId: number) {
  const loggedIn = useAuthStore((s) => !!s.accessToken)
  return useQuery({
    queryKey: logAnalysisKey(logId),
    queryFn: () => fetchLogAnalysis(logId),
    enabled: loggedIn && Number.isFinite(logId),
    refetchInterval: (query) => (isAnalysisRunning(query.state.data) ? POLL_INTERVAL_MS : false),
  })
}

/**
 * 분석 요청(작성자만). 응답이 곧 최신 상태라 캐시에 바로 넣으면
 * "분석 중…" 으로 즉시 바뀌고, 폴링은 useLogAnalysis 의 refetchInterval 이 이어받는다.
 */
export function useRequestAnalysis(logId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => requestAnalysis(logId),
    onSuccess: (analysis) => {
      queryClient.setQueryData<VideoAnalysis | null>(logAnalysisKey(logId), analysis)
    },
  })
}

/**
 * 스켈레톤 오버레이용 랜드마크. 프레임당 33점이라 용량이 커서 버튼을 눌렀을 때만(enabled) 받고,
 * 완료된 분석의 결과는 바뀌지 않으니 다시 받지 않는다.
 */
export function useAnalysisKeypoints(id: number | null, enabled: boolean) {
  return useQuery({
    queryKey: keypointsKey(id ?? 0),
    queryFn: () => fetchAnalysisWithKeypoints(id as number),
    enabled: enabled && id !== null && Number.isFinite(id),
    staleTime: Infinity,
    gcTime: 10 * 60 * 1000,
    select: (analysis) => analysis.keypoints,
  })
}
