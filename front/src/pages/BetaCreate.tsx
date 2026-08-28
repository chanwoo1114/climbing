import { useMemo, useRef, useState, type FormEvent, type RefObject } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import {
  BETA_DESCRIPTION_MAX_LENGTH,
  BETA_SECTOR_MAX_LENGTH,
  BETA_TITLE_MAX_LENGTH,
  type BetaWrite,
  type ClimbBeta,
} from '@/api/betas'
import { getErrorCode, getErrorMessage, getFieldError } from '@/api/client'
import type { GymDetail } from '@/api/gyms'
import { CLIMB_VIDEO_TYPES, IMAGE_TYPES } from '@/api/uploads'
import { parseDateOnly } from '@/components/climbs/LogCard'
import Button from '@/components/common/Button'
import SelectField, { type SelectOption } from '@/components/common/SelectField'
import TextArea from '@/components/common/TextArea'
import TextField from '@/components/common/TextField'
import { useMe } from '@/hooks/useAuth'
import { useBeta, useBetaSectors, useCreateBeta, useUpdateBeta } from '@/hooks/useBetas'
import { useMyLogs } from '@/hooks/useClimbs'
import { useGym } from '@/hooks/useGyms'
import { useBetaThumbnailUpload, useBetaVideoUpload, type UploadState } from '@/hooks/useUpload'
import type { FieldCheck } from '@/lib/validation'
import { useToastStore } from '@/stores/toastStore'

const percent = new Intl.NumberFormat('ko-KR', { style: 'percent', maximumFractionDigits: 0 })
const logDate = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium' })

interface FormValues {
  title: string
  sector: string
  difficulty: string
  description: string
  videoUrl: string
  thumbnailUrl: string
  climbLog: string
}

const fromBeta = (beta: ClimbBeta): FormValues => ({
  title: beta.title,
  sector: beta.sector,
  difficulty: beta.difficulty ? String(beta.difficulty.id) : '',
  description: beta.description,
  videoUrl: beta.videoUrl,
  thumbnailUrl: beta.thumbnailUrl,
  climbLog: beta.climbLogId === null ? '' : String(beta.climbLogId),
})

const BLANK: FormValues = {
  title: '',
  sector: '',
  difficulty: '',
  description: '',
  videoUrl: '',
  thumbnailUrl: '',
  climbLog: '',
}

/**
 * /gyms/:gymId/betas/new (생성) 와 /betas/:betaId/edit (수정) 를 같이 처리한다.
 * 수정은 영상을 바꿀 수 없다 — 서버가 video_url 을 거부하므로 필드 자체를 숨긴다.
 */
export default function BetaCreate() {
  const { gymId: gymParam, betaId: betaParam } = useParams()
  const editing = betaParam !== undefined
  const betaId = Number(betaParam)
  const validBeta = Number.isInteger(betaId) && betaId > 0
  const { data: me } = useMe()
  const beta = useBeta(editing && validBeta ? betaId : NaN)

  const gymId = editing ? (beta.data?.gym.id ?? NaN) : Number(gymParam)
  const validGym = Number.isInteger(gymId) && gymId > 0
  const gym = useGym(validGym ? gymId : NaN)

  if (editing) {
    if (!validBeta || (beta.isError && getErrorCode(beta.error) === 'http_404')) {
      return <Blocked message="베타 영상을 찾을 수 없어요." />
    }
    if (beta.isPending || !me) return <Loading />
    if (beta.isError || !beta.data) {
      return <Blocked message="베타 영상을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." />
    }
    if (!beta.data.isMine && beta.data.user.id !== me.id) {
      return (
        <Blocked message="본인이 올린 베타만 수정할 수 있어요." to={`/betas/${beta.data.id}`} />
      )
    }
  }

  if (!validGym || (gym.isError && getErrorCode(gym.error) === 'http_404')) {
    return <Blocked message="암장을 찾을 수 없어요." />
  }
  if (gym.isPending) return <Loading />
  if (gym.isError || !gym.data) {
    return <Blocked message="암장 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." />
  }
  return <BetaForm gym={gym.data} editing={editing ? beta.data : undefined} />
}

function Loading() {
  return (
    <p role="status" className="py-10 text-center text-sm text-ink-400">
      불러오는 중…
    </p>
  )
}

function Blocked({ message, to = '/' }: { message: string; to?: string }) {
  return (
    <div role="alert" className="py-10 text-center">
      <p className="text-sm text-pretty text-danger-500">{message}</p>
      <Link
        to={to}
        className="mt-2 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
      >
        돌아가기
      </Link>
    </div>
  )
}

const IDLE: FieldCheck = { state: 'idle', message: '' }
const invalid = (message: string): FieldCheck => ({ state: 'invalid', message })

const FIELDS = [
  'title',
  'sector',
  'difficulty',
  'description',
  'video_url',
  'thumbnail_url',
  'climb_log',
] as const

function BetaForm({ gym, editing }: { gym: GymDetail; editing?: ClimbBeta }) {
  const navigate = useNavigate()
  const push = useToastStore((s) => s.push)
  const create = useCreateBeta(gym.id)
  const update = useUpdateBeta(editing?.id ?? NaN)
  const mutation = editing ? update : create

  const [values, setValues] = useState<FormValues>(() => (editing ? fromBeta(editing) : BLANK))

  const sectors = useBetaSectors(gym.id)
  const difficultyOptions: SelectOption[] = [...gym.difficulties]
    .sort((a, b) => a.order - b.order)
    .map((d) => ({ value: String(d.id), label: d.name }))

  // "내 기록 연결" 후보 — 이 암장에서 남긴 내 기록 (최근 순, 첫 페이지)
  const myLogs = useMyLogs({ gym: gym.id })
  const linkedLogId = editing?.climbLogId ?? null
  const logOptions = useMemo<SelectOption[]>(() => {
    const logs = myLogs.data?.pages.flatMap((page) => page.results) ?? []
    const options = logs.map((log) => ({
      value: String(log.id),
      label: [
        logDate.format(parseDateOnly(log.climbedAt)),
        log.difficulty?.name ?? '난이도 없음',
        log.isSuccess ? '성공' : '실패',
      ].join(' · '),
    }))
    // 수정 중인 베타에 이미 연결된 기록이 첫 페이지에 없어도 선택지에서 빠지지 않게
    if (linkedLogId !== null && !options.some((o) => o.value === String(linkedLogId))) {
      options.unshift({ value: String(linkedLogId), label: `연결된 기록 #${linkedLogId}` })
    }
    return options
  }, [myLogs.data, linkedLogId])

  const video = useBetaVideoUpload()
  const thumbnail = useBetaThumbnailUpload()
  const videoInputRef = useRef<HTMLInputElement>(null)
  const thumbnailInputRef = useRef<HTMLInputElement>(null)
  const uploading = [video.status, thumbnail.status].some(
    (status) => status === 'requesting' || status === 'uploading',
  )

  const error = mutation.error
  const serverError = (field: string) => getFieldError(error, field)
  const withServer = (check: FieldCheck, field: string): FieldCheck => {
    const message = serverError(field)
    return message ? invalid(message) : check
  }

  // --- 검증 (서버와 같은 규칙, 최종 판정은 서버) ---
  const title = values.title.trim()
  const titleValid = title.length > 0 && title.length <= BETA_TITLE_MAX_LENGTH
  const titleCheck = withServer(
    values.title !== '' && !titleValid ? invalid(`제목은 ${BETA_TITLE_MAX_LENGTH}자 이하여야 합니다.`) : IDLE,
    'title',
  )
  const sector = values.sector.trim()
  const sectorValid = sector.length <= BETA_SECTOR_MAX_LENGTH
  const sectorCheck = withServer(
    sectorValid ? IDLE : invalid(`섹터 이름은 ${BETA_SECTOR_MAX_LENGTH}자 이하여야 합니다.`),
    'sector',
  )
  const descriptionCheck = withServer(IDLE, 'description')
  const videoValid = editing !== undefined || values.videoUrl !== ''

  const canSubmit =
    titleValid &&
    sectorValid &&
    values.description.length <= BETA_DESCRIPTION_MAX_LENGTH &&
    videoValid &&
    !uploading
  const pending = mutation.isPending

  const generalError =
    error && !FIELDS.some((field) => serverError(field))
      ? getErrorMessage(error, '베타 영상을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      : null

  const edit = <K extends keyof FormValues>(key: K, value: FormValues[K]) => {
    if (mutation.isError) mutation.reset()
    setValues((v) => ({ ...v, [key]: value }))
  }

  const pickVideo = async (file: File | undefined) => {
    if (!file) return
    const url = await video.upload(file)
    if (url) edit('videoUrl', url)
  }
  const removeVideo = () => {
    video.reset()
    if (videoInputRef.current) videoInputRef.current.value = ''
    edit('videoUrl', '')
  }
  const pickThumbnail = async (file: File | undefined) => {
    if (!file) return
    const url = await thumbnail.upload(file)
    if (url) edit('thumbnailUrl', url)
  }
  const removeThumbnail = () => {
    thumbnail.reset()
    if (thumbnailInputRef.current) thumbnailInputRef.current.value = ''
    edit('thumbnailUrl', '')
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || pending) return
    const body: Omit<BetaWrite, 'videoUrl'> = {
      title,
      sector,
      difficulty: values.difficulty === '' ? null : Number(values.difficulty),
      description: values.description.trim(),
      thumbnailUrl: values.thumbnailUrl,
      climbLog: values.climbLog === '' ? null : Number(values.climbLog),
    }
    const onSuccess = (beta: ClimbBeta) => {
      push({ title: editing ? '베타 영상을 수정했어요.' : '베타 영상을 올렸어요.' })
      navigate(`/betas/${beta.id}`, { replace: editing !== undefined })
    }
    if (editing) update.mutate(body, { onSuccess })
    else create.mutate({ ...body, videoUrl: values.videoUrl }, { onSuccess })
  }

  const cancelPath = editing ? `/betas/${editing.id}` : `/gyms/${gym.id}?tab=betas`

  return (
    <div className="mx-auto mt-4 max-w-lg md:mt-8">
      <h1 className="mb-1 text-2xl font-semibold text-ink-700">
        {editing ? '베타 수정' : '베타 올리기'}
      </h1>
      <p className="mb-6 text-sm text-pretty break-words text-ink-400">{gym.name}</p>

      <form
        onSubmit={onSubmit}
        noValidate
        className="space-y-5 rounded-card border border-chalk-300 bg-white p-6"
      >
        <TextField
          label="제목"
          name="title"
          placeholder="예: 파란 문제 하이스텝 베타"
          maxLength={BETA_TITLE_MAX_LENGTH}
          required
          value={values.title}
          check={titleCheck}
          onChange={(e) => edit('title', e.target.value)}
          disabled={pending}
        />

        <div>
          <TextField
            label="섹터 (선택)"
            name="sector"
            list="sector-options"
            placeholder="예: A벽, 오버행"
            maxLength={BETA_SECTOR_MAX_LENGTH}
            autoComplete="off"
            value={values.sector}
            check={sectorCheck}
            onChange={(e) => edit('sector', e.target.value)}
            disabled={pending}
          />
          {/* 이미 쓰인 섹터 이름을 자동완성으로 — 표기가 갈리지 않게 */}
          <datalist id="sector-options">
            {(sectors.data ?? []).map((item) => (
              <option key={item.sector} value={item.sector} />
            ))}
          </datalist>
        </div>

        <SelectField
          label="난이도 (선택)"
          name="difficulty"
          placeholder={difficultyOptions.length === 0 ? '등록된 난이도가 없어요' : '선택 안 함'}
          options={difficultyOptions}
          value={values.difficulty}
          error={serverError('difficulty')}
          onChange={(e) => edit('difficulty', e.target.value)}
          disabled={pending || difficultyOptions.length === 0}
        />

        <TextArea
          label="설명 (선택)"
          name="description"
          placeholder="어디서 막히는지, 핵심 무브가 뭔지 적어 보세요"
          maxLength={BETA_DESCRIPTION_MAX_LENGTH}
          showCount
          value={values.description}
          check={descriptionCheck}
          onChange={(e) => edit('description', e.target.value)}
          disabled={pending}
        />

        {editing ? (
          <div>
            <p className="mb-1 text-sm font-medium text-ink-500">영상</p>
            <p
              role="status"
              className="rounded-xl bg-chalk-100 px-3 py-2 text-xs text-pretty text-ink-500"
            >
              영상은 바꿀 수 없어요. 다른 영상을 올리려면 새 베타로 올려 주세요.
            </p>
          </div>
        ) : (
          <UploadField
            id="video"
            label="영상 (필수)"
            hint="MP4 · MOV · WebM, 200MB 이하"
            pickLabel="영상 파일 선택"
            accept={CLIMB_VIDEO_TYPES.join(',')}
            inputRef={videoInputRef}
            fileUrl={values.videoUrl}
            upload={video}
            error={video.error ?? serverError('video_url')}
            disabled={pending}
            onPick={pickVideo}
            onRemove={removeVideo}
          />
        )}

        <UploadField
          id="thumbnail"
          label="썸네일 (선택)"
          hint="JPG · PNG · WebP, 5MB 이하. 없으면 재생 표시가 대신 보여요"
          pickLabel="이미지 선택"
          accept={IMAGE_TYPES.join(',')}
          inputRef={thumbnailInputRef}
          fileUrl={values.thumbnailUrl}
          upload={thumbnail}
          error={thumbnail.error ?? serverError('thumbnail_url')}
          disabled={pending}
          onPick={pickThumbnail}
          onRemove={removeThumbnail}
        />

        <SelectField
          label="내 기록 연결 (선택)"
          name="climbLog"
          placeholder={
            myLogs.isPending
              ? '기록 불러오는 중…'
              : logOptions.length === 0
                ? '이 암장에서 남긴 기록이 없어요'
                : '연결 안 함'
          }
          hint="이 암장에서 남긴 내 등반 기록을 베타에 붙여요"
          options={logOptions}
          value={values.climbLog}
          error={serverError('climb_log')}
          onChange={(e) => edit('climbLog', e.target.value)}
          disabled={pending || myLogs.isPending || logOptions.length === 0}
        />

        {generalError && (
          <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
            {generalError}
          </p>
        )}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={() => navigate(cancelPath)} disabled={pending}>
            취소
          </Button>
          {/* 이 페이지의 유일한 primary CTA */}
          <Button type="submit" disabled={!canSubmit || pending}>
            {pending ? '저장 중…' : editing ? '저장' : '베타 올리기'}
          </Button>
        </div>
      </form>
    </div>
  )
}

// --- 업로드 필드 (영상·썸네일 공용) ---

function UploadField({
  id,
  label,
  hint,
  pickLabel,
  accept,
  inputRef,
  fileUrl,
  upload,
  error,
  disabled,
  onPick,
  onRemove,
}: {
  id: string
  label: string
  hint: string
  pickLabel: string
  accept: string
  inputRef: RefObject<HTMLInputElement | null>
  fileUrl: string
  upload: UploadState & { cancel: () => void }
  error: string | null | undefined
  disabled?: boolean
  onPick: (file: File | undefined) => void
  onRemove: () => void
}) {
  const uploading = upload.status === 'requesting' || upload.status === 'uploading'
  const attached = fileUrl !== '' && !uploading
  const storageUnavailable = upload.errorCode === 'storage_not_configured'
  const errorId = `${id}-error`
  const hintId = `${id}-hint`

  return (
    <div>
      <p id={`${id}-label`} className="mb-1 text-sm font-medium text-ink-500">
        {label}
      </p>
      <input
        ref={inputRef}
        type="file"
        id={id}
        aria-labelledby={`${id}-label`}
        accept={accept}
        onChange={(e) => onPick(e.target.files?.[0])}
        disabled={disabled || uploading || storageUnavailable}
        aria-describedby={error ? errorId : hintId}
        className="sr-only"
        tabIndex={-1}
      />
      {attached ? (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-chalk-300 bg-chalk-50 px-3 py-2">
          <p role="status" className="min-w-0 truncate text-sm text-ink-600">
            <span aria-hidden className="mr-1.5 text-moss-500">
              ✓
            </span>
            {upload.fileName ?? '첨부됨'}
          </p>
          <Button variant="secondary" onClick={onRemove} disabled={disabled}>
            제거
          </Button>
        </div>
      ) : uploading ? (
        <div className="rounded-xl border border-chalk-300 bg-chalk-50 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <p role="status" className="min-w-0 truncate text-sm text-ink-600">
              {upload.status === 'requesting'
                ? '업로드 준비 중…'
                : `올리는 중 ${percent.format(upload.progress)}`}
              {upload.fileName && <span className="ml-1 text-ink-400">— {upload.fileName}</span>}
            </p>
            <Button variant="secondary" onClick={upload.cancel}>
              취소
            </Button>
          </div>
          <div
            role="progressbar"
            aria-labelledby={`${id}-label`}
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
      ) : storageUnavailable ? (
        <p
          role="status"
          id={hintId}
          className="rounded-xl bg-chalk-100 px-3 py-2 text-xs text-pretty text-ink-500"
        >
          파일 저장소가 아직 설정되지 않았어요. 잠시 후 다시 시도해 주세요.
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={() => inputRef.current?.click()} disabled={disabled}>
            {pickLabel}
          </Button>
          <span id={hintId} className="text-xs text-pretty text-ink-400">
            {hint}
          </span>
        </div>
      )}
      {error && !storageUnavailable && (
        <p id={errorId} role="alert" className="mt-1 text-xs text-pretty text-danger-500">
          {error}
        </p>
      )}
    </div>
  )
}
