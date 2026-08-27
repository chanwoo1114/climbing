import axios from 'axios'

import { api } from '@/api/client'

/**
 * S3 presigned PUT 업로드 (backend common.services.uploads).
 * 파일은 서버를 거치지 않는다: 1) presigned URL 발급 → 2) 브라우저가 S3 로 직접 PUT →
 * 3) 응답의 fileUrl 을 기록/프로필 API 에 저장.
 */

export type UploadKind = 'profile_image' | 'post_image' | 'climb_video'

/** backend UPLOAD_KINDS["climb_video"] 와 동일하게 유지 — 서버가 최종 판정 */
export const CLIMB_VIDEO_TYPES = ['video/mp4', 'video/quicktime', 'video/webm'] as const

export interface PresignedUploadRequest {
  kind: UploadKind
  filename: string
  contentType: string
}

export interface PresignedUpload {
  uploadUrl: string
  method: 'PUT'
  /** 서명에 포함된 헤더 — PUT 할 때 그대로 보내야 한다 (다르면 S3 가 403) */
  headers: Record<string, string>
  /** 업로드 완료 후 DB 에 저장할 공개 URL */
  fileUrl: string
  key: string
  expiresIn: number
  /** 클라이언트 사전 검사용 상한 (서버 강제는 버킷 정책) */
  maxBytes: number
}

export async function requestPresignedUpload(
  input: PresignedUploadRequest,
): Promise<PresignedUpload> {
  const { data } = await api.post<PresignedUpload>('/uploads/presigned-url/', input)
  return data
}

export interface PutFileOptions {
  onProgress?: (fraction: number) => void
  signal?: AbortSignal
}

/**
 * presigned URL 로 파일을 올린다. `api` 인스턴스가 아니라 기본 axios 를 쓴다 —
 * S3 에는 Authorization 헤더도, 응답 래퍼도 없다.
 */
export async function putFileToPresignedUrl(
  presigned: PresignedUpload,
  file: File,
  { onProgress, signal }: PutFileOptions = {},
): Promise<void> {
  await axios.put(presigned.uploadUrl, file, {
    headers: presigned.headers,
    signal,
    // 큰 영상은 기본 15초 타임아웃으로는 모자라다
    timeout: 10 * 60 * 1000,
    onUploadProgress: (event) => {
      if (!onProgress) return
      const total = event.total ?? file.size
      onProgress(total > 0 ? Math.min(1, event.loaded / total) : 0)
    },
  })
}
