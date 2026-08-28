import { useRef, useState } from 'react'

import { getErrorMessage, getFieldError } from '@/api/client'
import type { GymDetail } from '@/api/gyms'
import { POST_IMAGE_TYPES } from '@/api/posts'
import Button from '@/components/common/Button'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import { Card, Empty, ErrorBanner } from '@/components/gyms/manage/ManageBits'
import { useAddGymImage, useDeleteGymImage, useReorderGymImages } from '@/hooks/useGyms'
import { useUpload } from '@/hooks/useUpload'
import { useToastStore } from '@/stores/toastStore'

const percent = new Intl.NumberFormat('ko-KR', { style: 'percent', maximumFractionDigits: 0 })

/**
 * 사진 — presigned 업로드(post_image kind, 서버에 gym 전용 kind 가 없다) 후 URL 을 등록한다.
 * 순서 변경은 전체 id 배열을 새 순서대로 PUT 한다.
 */
export default function ImageSection({ gym }: { gym: GymDetail }) {
  const images = [...gym.images].sort((a, b) => a.order - b.order)
  const add = useAddGymImage(gym.id)
  const remove = useDeleteGymImage(gym.id)
  const reorder = useReorderGymImages(gym.id)
  const upload = useUpload(
    'post_image',
    POST_IMAGE_TYPES,
    '지원하지 않는 형식입니다. JPG, PNG, WebP 이미지만 올릴 수 있어요.',
  )
  const pushToast = useToastStore((s) => s.push)
  const inputRef = useRef<HTMLInputElement>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)

  const uploading = upload.status === 'requesting' || upload.status === 'uploading'
  const busy = uploading || add.isPending || remove.isPending || reorder.isPending
  const storageUnavailable = upload.errorCode === 'storage_not_configured'

  const onPick = async (files: FileList | null) => {
    const file = files?.[0]
    if (inputRef.current) inputRef.current.value = ''
    if (!file) return
    const url = await upload.upload(file)
    if (!url) return
    add.mutate(
      { image: url, order: images.length },
      {
        onSuccess: () => {
          upload.reset()
          pushToast({ title: '사진을 추가했습니다.' })
        },
      },
    )
  }

  const move = (index: number, delta: -1 | 1) => {
    const target = index + delta
    if (target < 0 || target >= images.length) return
    const ids = images.map((image) => image.id)
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    reorder.mutate(ids)
  }

  const onDelete = () => {
    if (confirmId === null) return
    remove.mutate(confirmId, { onSettled: () => setConfirmId(null) })
  }

  const uploadError = upload.status === 'error' && !storageUnavailable ? upload.error : null
  const addError = add.error
    ? getFieldError(add.error, 'image') ??
      getErrorMessage(add.error, '사진을 등록하지 못했습니다. 잠시 후 다시 시도해 주세요.')
    : null
  const reorderError = reorder.error
    ? getFieldError(reorder.error, 'ids') ??
      getErrorMessage(reorder.error, '순서를 바꾸지 못했습니다. 잠시 후 다시 시도해 주세요.')
    : null
  const removeError = remove.error
    ? getErrorMessage(remove.error, '사진을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')
    : null
  const confirming = images.find((image) => image.id === confirmId)

  return (
    <Card id="manage-images" title="사진" description="첫 번째 사진이 지도 목록의 썸네일이 돼요.">
      <input
        ref={inputRef}
        type="file"
        accept={POST_IMAGE_TYPES.join(',')}
        aria-label="사진 파일"
        onChange={(e) => onPick(e.target.files)}
        disabled={busy || storageUnavailable}
        className="sr-only"
        tabIndex={-1}
      />

      {images.length === 0 ? (
        <Empty>등록된 사진이 없어요</Empty>
      ) : (
        <ul aria-label={`${gym.name} 사진`} className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {images.map((image, index) => (
            <li key={image.id} className="space-y-2">
              <img
                src={image.image}
                alt={`${gym.name} 사진 ${index + 1}`}
                loading="lazy"
                className="aspect-[4/3] w-full rounded-xl object-cover"
              />
              <div className="flex items-center gap-1">
                <Button
                  variant="secondary"
                  aria-label="위로"
                  className="min-w-11 px-0"
                  onClick={() => move(index, -1)}
                  disabled={index === 0 || busy}
                >
                  <span aria-hidden>↑</span>
                </Button>
                <Button
                  variant="secondary"
                  aria-label="아래로"
                  className="min-w-11 px-0"
                  onClick={() => move(index, 1)}
                  disabled={index === images.length - 1 || busy}
                >
                  <span aria-hidden>↓</span>
                </Button>
                <Button
                  variant="secondary"
                  aria-label={`${index + 1}번 사진 삭제`}
                  className="ml-auto"
                  onClick={() => {
                    remove.reset()
                    setConfirmId(image.id)
                  }}
                  disabled={busy}
                >
                  삭제
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {uploading && (
        <div className="rounded-xl border border-chalk-300 bg-chalk-50 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <p role="status" className="min-w-0 truncate text-sm text-ink-600">
              {upload.status === 'requesting'
                ? '업로드 준비 중…'
                : `올리는 중 ${percent.format(upload.progress)}`}
            </p>
            <Button variant="secondary" onClick={upload.cancel}>
              취소
            </Button>
          </div>
          <div
            role="progressbar"
            aria-label="사진 업로드"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(upload.progress * 100)}
            className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-chalk-200"
          >
            <div
              className="h-full origin-left rounded-full bg-hold-300 transition-transform duration-150 ease-out"
              style={{ transform: `scaleX(${upload.progress})` }}
            />
          </div>
        </div>
      )}

      {storageUnavailable && (
        <p role="status" className="rounded-xl bg-chalk-100 px-3 py-2 text-xs text-pretty text-ink-500">
          이미지 저장소가 아직 설정되지 않았어요. 사진은 나중에 올릴 수 있어요.
        </p>
      )}
      {uploadError && <ErrorBanner>{uploadError}</ErrorBanner>}
      {addError && <ErrorBanner>{addError}</ErrorBanner>}
      {reorderError && <ErrorBanner>{reorderError}</ErrorBanner>}
      {removeError && <ErrorBanner>{removeError}</ErrorBanner>}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-pretty text-ink-400">JPG · PNG · WebP</span>
        {/* 이 섹션의 유일한 primary CTA */}
        <Button
          onClick={() => inputRef.current?.click()}
          disabled={busy || storageUnavailable}
        >
          {add.isPending ? '등록 중…' : '사진 올리기'}
        </Button>
      </div>

      <ConfirmDialog
        open={confirmId !== null}
        title={`${confirming ? `${images.indexOf(confirming) + 1}번 ` : ''}사진을 삭제할까요?`}
        description="삭제한 사진은 되돌릴 수 없어요."
        confirmLabel="삭제"
        pendingLabel="삭제 중…"
        pending={remove.isPending}
        onConfirm={onDelete}
        onCancel={() => setConfirmId(null)}
      />
    </Card>
  )
}
