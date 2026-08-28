import { useCallback, useRef, useState } from 'react'

import { getErrorCode, getErrorMessage } from '@/api/client'
import {
  CLIMB_VIDEO_TYPES,
  IMAGE_TYPES,
  putFileToPresignedUrl,
  requestPresignedUpload,
  type UploadKind,
} from '@/api/uploads'

export type UploadStatus = 'idle' | 'requesting' | 'uploading' | 'done' | 'error'

export interface UploadState {
  status: UploadStatus
  /** 0~1. uploading 중에만 의미 있다 */
  progress: number
  /** done 이면 저장할 공개 URL */
  fileUrl: string | null
  fileName: string | null
  error: string | null
  /** 서버 error.code — 'storage_not_configured'(503) 등. 클라이언트 검사 실패면 null */
  errorCode: string | null
}

const INITIAL: UploadState = {
  status: 'idle',
  progress: 0,
  fileUrl: null,
  fileName: null,
  error: null,
  errorCode: null,
}

const megabytes = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 })
const toMB = (n: number) => `${megabytes.format(n / (1024 * 1024))}MB`

/**
 * presigned 업로드 한 건의 상태 머신.
 * 파일 선택 → 형식 검사 → presigned URL 발급 → (max_bytes 검사) → S3 PUT (진행률) → fileUrl.
 * 크기 상한은 서버 응답(max_bytes)이 알려주므로 발급 뒤에 검사한다.
 */
export function useUpload(
  kind: UploadKind,
  allowedTypes: readonly string[],
  /** 형식 검사 실패 메시지 — 기본값은 영상 기준이라 이미지 kind 는 따로 넘긴다 */
  typeError = '지원하지 않는 형식입니다. MP4, MOV, WebM 영상만 올릴 수 있어요.',
) {
  const [state, setState] = useState<UploadState>(INITIAL)
  const controller = useRef<AbortController | null>(null)

  const cancel = useCallback(() => {
    controller.current?.abort()
    controller.current = null
    setState(INITIAL)
  }, [])

  const upload = useCallback(
    async (file: File): Promise<string | null> => {
      controller.current?.abort()
      if (!allowedTypes.includes(file.type)) {
        setState({
          ...INITIAL,
          status: 'error',
          fileName: file.name,
          error: typeError,
        })
        return null
      }
      const abort = new AbortController()
      controller.current = abort
      setState({ ...INITIAL, status: 'requesting', fileName: file.name })
      try {
        const presigned = await requestPresignedUpload({
          kind,
          filename: file.name,
          contentType: file.type,
        })
        if (abort.signal.aborted) return null
        if (file.size > presigned.maxBytes) {
          setState({
            ...INITIAL,
            status: 'error',
            fileName: file.name,
            error: `파일이 너무 큽니다. ${toMB(presigned.maxBytes)} 이하로 올려 주세요. (선택한 파일 ${toMB(file.size)})`,
          })
          return null
        }
        setState((s) => ({ ...s, status: 'uploading', progress: 0 }))
        await putFileToPresignedUrl(presigned, file, {
          signal: abort.signal,
          onProgress: (progress) => setState((s) => ({ ...s, progress })),
        })
        setState({
          status: 'done',
          progress: 1,
          fileUrl: presigned.fileUrl,
          fileName: file.name,
          error: null,
          errorCode: null,
        })
        return presigned.fileUrl
      } catch (error) {
        if (abort.signal.aborted) return null
        setState({
          ...INITIAL,
          status: 'error',
          fileName: file.name,
          error: getErrorMessage(error, '파일을 올리지 못했습니다. 잠시 후 다시 시도해 주세요.'),
          errorCode: getErrorCode(error) ?? null,
        })
        return null
      } finally {
        if (controller.current === abort) controller.current = null
      }
    },
    [kind, allowedTypes, typeError],
  )

  return { ...state, upload, cancel, reset: cancel }
}

/** 등반 영상 전용 프리셋 */
export function useVideoUpload() {
  return useUpload('climb_video', CLIMB_VIDEO_TYPES)
}

/** 베타 영상 (≤200MB) */
export function useBetaVideoUpload() {
  return useUpload('beta_video', CLIMB_VIDEO_TYPES)
}

/** 베타 썸네일 이미지 (≤5MB) */
export function useBetaThumbnailUpload() {
  return useUpload(
    'beta_thumbnail',
    IMAGE_TYPES,
    '지원하지 않는 형식입니다. JPG, PNG, WebP 이미지만 올릴 수 있어요.',
  )
}
