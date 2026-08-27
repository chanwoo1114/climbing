import { api } from '@/api/client'
import type { RawCursorPage } from '@/api/gyms'

// --- 읽기 모델 (backend analysis.serializers.VideoAnalysisSerializer) ---
// 응답은 인터셉터가 중첩 키까지 camelCase 로 바꾼다 (joint_angles.left_elbow → jointAngles.leftElbow).

export type AnalysisStatus = 'pending' | 'processing' | 'done' | 'failed'

export const JOINT_NAMES = [
  'leftElbow',
  'rightElbow',
  'leftKnee',
  'rightKnee',
  'leftHip',
  'rightHip',
] as const
export type JointName = (typeof JOINT_NAMES)[number]

/** 관절 각도(도) 통계 */
export interface JointAngleStats {
  mean: number
  min: number
  max: number
}

/**
 * 무게중심(어깨·엉덩이 4점 평균) 궤적 요약.
 * 좌표는 프레임 크기로 정규화된 0~1 값이고 y 는 아래로 증가한다 (실제 거리가 아니다).
 */
export interface ComMetrics {
  /** [t(초), x, y] — 최대 120점으로 줄인 궤적 */
  trajectory: [number, number, number][]
  /** 총 이동 거리 (정규화 좌표 단위) */
  pathLength: number
  /** 시작 대비 최고 상승량 (시작 y − 최소 y) */
  verticalGain: number
  /** 상하 이동 폭 */
  verticalRange: number
  start: [number, number]
  end: [number, number]
}

export interface MoveRatio {
  /** 0~1. COM 속도가 speedThreshold 를 넘는 구간 비율 */
  dynamic: number
  static: number
  speedThreshold: number
}

export interface AnalysisMetrics {
  /** 영상 길이 (초) */
  duration: number
  sampleFps: number | null
  frameCount: number
  detectedFrames: number
  /** 0~1 */
  detectionRate: number
  /** 자세를 한 프레임도 못 찾았으면 null */
  com: ComMetrics | null
  jointAngles: Partial<Record<JointName, JointAngleStats>>
  moveRatio: MoveRatio | null
}

/** MediaPipe Pose 랜드마크 하나 — [x, y, z, visibility]. x, y 는 0~1 정규화 */
export type Landmark = [number, number, number, number]

export interface KeypointFrame {
  /** 초 */
  t: number
  /** 33개. 그 프레임에서 자세를 못 찾았으면 null */
  lm: Landmark[] | null
}

export interface AnalysisKeypoints {
  fps: number
  sourceFps: number
  duration: number
  width: number
  height: number
  frames: KeypointFrame[]
}

export interface VideoAnalysis {
  id: number
  climbLog: number
  status: AnalysisStatus
  /** 실패 사유 — 그대로 보여줘도 되는 짧은 문장. 실패가 아니면 빈 문자열 */
  errorMessage: string
  /** done 일 때만 값이 있다 (서버는 그 전엔 {} 를 준다 → null 로 정규화) */
  metrics: AnalysisMetrics | null
  processedAt: string | null
  retryCount: number
  createdAt: string
  updatedAt: string
}

export interface VideoAnalysisWithKeypoints extends VideoAnalysis {
  /** ?include=keypoints 일 때만. done 이 아니면 null */
  keypoints: AnalysisKeypoints | null
}

/** MediaPipe Pose 33 랜드마크 인덱스 */
export const POSE = {
  nose: 0,
  leftShoulder: 11,
  rightShoulder: 12,
  leftElbow: 13,
  rightElbow: 14,
  leftWrist: 15,
  rightWrist: 16,
  leftHip: 23,
  rightHip: 24,
  leftKnee: 25,
  rightKnee: 26,
  leftAnkle: 27,
  rightAnkle: 28,
} as const

export const LANDMARK_COUNT = 33

/** 서버는 아직 값이 없으면 {} 를 준다 — 화면에서는 null 로 다루는 게 편하다 */
function emptyToNull<T extends object>(value: T | Record<string, never> | null | undefined): T | null {
  if (!value || typeof value !== 'object' || Object.keys(value).length === 0) return null
  return value as T
}

type RawAnalysis = Omit<VideoAnalysis, 'metrics'> & { metrics: AnalysisMetrics | Record<string, never> }
type RawAnalysisWithKeypoints = RawAnalysis & {
  keypoints?: AnalysisKeypoints | Record<string, never>
}

function normalize(raw: RawAnalysis): VideoAnalysis {
  return { ...raw, metrics: emptyToNull<AnalysisMetrics>(raw.metrics) }
}

export const isAnalysisRunning = (analysis: VideoAnalysis | null | undefined) =>
  analysis?.status === 'pending' || analysis?.status === 'processing'

// --- API ---

/** 기록의 분석 (기록당 1건). 아직 요청한 적이 없으면 null */
export async function fetchLogAnalysis(logId: number): Promise<VideoAnalysis | null> {
  const { data } = await api.get<RawCursorPage<RawAnalysis>>('/analyses/', {
    params: { climbLog: logId },
  })
  const first = data.results[0]
  return first ? normalize(first) : null
}

/**
 * 분석 요청 — 작성자만, 영상이 있어야 한다 (400 video_required).
 * 새로 큐에 넣으면 202, 이미 대기/진행/완료 상태면 그 건을 200 으로 그대로 준다.
 */
export async function requestAnalysis(logId: number): Promise<VideoAnalysis> {
  const { data } = await api.post<RawAnalysis>('/analyses/', { climbLog: logId })
  return normalize(data)
}

export async function fetchAnalysis(id: number): Promise<VideoAnalysis> {
  const { data } = await api.get<RawAnalysis>(`/analyses/${id}/`)
  return normalize(data)
}

/** 랜드마크까지 포함해서 받는다 — 용량이 커서 스켈레톤을 볼 때만 부른다 */
export async function fetchAnalysisWithKeypoints(id: number): Promise<VideoAnalysisWithKeypoints> {
  const { data } = await api.get<RawAnalysisWithKeypoints>(`/analyses/${id}/`, {
    params: { include: 'keypoints' },
  })
  return { ...normalize(data), keypoints: emptyToNull<AnalysisKeypoints>(data.keypoints) }
}
