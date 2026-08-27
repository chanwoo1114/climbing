import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
  type RefObject,
} from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { MEMO_MAX_LENGTH, type ClimbLog, type ClimbLogInput } from '@/api/climbs'
import { getErrorCode, getErrorMessage, getFieldError } from '@/api/client'
import type { GymDifficulty } from '@/api/gyms'
import { CLIMB_VIDEO_TYPES } from '@/api/uploads'
import Button from '@/components/common/Button'
import SelectField, { type SelectOption } from '@/components/common/SelectField'
import TextArea from '@/components/common/TextArea'
import TextField from '@/components/common/TextField'
import { useMe } from '@/hooks/useAuth'
import { useCreateLog, useGymDifficulties, useLog, useUpdateLog } from '@/hooks/useClimbs'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useGymPoints, useGyms } from '@/hooks/useGyms'
import { useVideoUpload, type UploadStatus } from '@/hooks/useUpload'
import type { FieldCheck } from '@/lib/validation'

/** <input type="date"> 값 — 로컬 날짜 기준 YYYY-MM-DD (toISOString 은 UTC 라 자정 근처에 하루 밀린다) */
function toDateInputValue(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const percent = new Intl.NumberFormat('ko-KR', { style: 'percent', maximumFractionDigits: 0 })

interface FormValues {
  gym: string
  difficulty: string
  isSuccess: boolean
  attempts: string
  climbedAt: string
  memo: string
  videoUrl: string
  isShared: boolean
}

const fromLog = (log: ClimbLog): FormValues => ({
  gym: String(log.gym.id),
  difficulty: log.difficulty ? String(log.difficulty.id) : '',
  isSuccess: log.isSuccess,
  attempts: String(log.attempts),
  climbedAt: log.climbedAt,
  memo: log.memo,
  videoUrl: log.videoUrl,
  isShared: log.isShared,
})

const blank = (gym: string): FormValues => ({
  gym,
  difficulty: '',
  isSuccess: true,
  attempts: '1',
  climbedAt: toDateInputValue(new Date()),
  memo: '',
  videoUrl: '',
  isShared: true,
})

/** /logs/new 와 /logs/:id/edit 를 같이 처리한다 */
export default function LogCreate() {
  const { id } = useParams()
  const editing = id !== undefined
  const logId = Number(id)
  const validId = Number.isInteger(logId) && logId > 0
  const { data: me } = useMe()
  const log = useLog(editing && validId ? logId : NaN)

  if (!editing) {
    return <LogForm homeGym={me?.homeGym ?? null} homeGymName={me?.homeGymName ?? null} />
  }
  if (!validId || (log.isError && getErrorCode(log.error) === 'http_404')) {
    return <Blocked message="기록을 찾을 수 없어요." />
  }
  if (log.isPending || !me) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (log.isError || !log.data) {
    return <Blocked message="기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." />
  }
  if (log.data.user.id !== me.id) {
    return <Blocked message="본인의 기록만 수정할 수 있어요." to={`/logs/${log.data.id}`} />
  }
  return (
    <LogForm
      editing={log.data}
      homeGym={me.homeGym}
      homeGymName={me.homeGymName}
    />
  )
}

function Blocked({ message, to = '/feed' }: { message: string; to?: string }) {
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

function LogForm({
  editing,
  homeGym,
  homeGymName,
}: {
  editing?: ClimbLog
  homeGym: number | null
  homeGymName: string | null
}) {
  const navigate = useNavigate()
  const create = useCreateLog()
  const update = useUpdateLog(editing?.id ?? NaN)
  const mutation = editing ? update : create

  const [values, setValues] = useState<FormValues>(() =>
    editing ? fromLog(editing) : blank(homeGym === null ? '' : String(homeGym)),
  )
  // 새 기록: 홈짐(useMe)이 폼보다 늦게 도착하면 아직 안 골랐을 때만 채워 넣는다
  const touchedGym = useRef(editing !== undefined)
  useEffect(() => {
    if (!touchedGym.current && homeGym !== null && values.gym === '') {
      setValues((v) => ({ ...v, gym: String(homeGym) }))
    }
  }, [homeGym, values.gym])

  // 암장 후보: 내 위치를 알면 가까운 순(100곳 상한), 모르면 전국 전체를 가나다순.
  // 권한 프롬프트는 띄우지 않는다.
  const geo = useGeolocation()
  const nearby = useGyms(
    geo.position ? { lat: geo.position.lat, lng: geo.position.lng } : {},
    geo.position !== null,
  )
  const points = useGymPoints()
  const gymOptions = useMemo<SelectOption[]>(() => {
    const source = geo.position
      ? (nearby.data ?? [])
      : [...(points.data ?? [])].sort((a, b) => a.name.localeCompare(b.name, 'ko'))
    const options = source.map((gym) => ({ value: String(gym.id), label: gym.name }))
    const ensureFirst = (value: string, label: string) => {
      const index = options.findIndex((option) => option.value === value)
      const [existing] = index >= 0 ? options.splice(index, 1) : []
      options.unshift(existing ?? { value, label })
    }
    // 수정 중인 기록의 암장 → 홈짐 순으로 맨 위
    if (homeGym !== null) ensureFirst(String(homeGym), homeGymName ?? `암장 #${homeGym}`)
    if (editing) ensureFirst(String(editing.gym.id), editing.gym.name)
    return options
  }, [geo.position, nearby.data, points.data, homeGym, homeGymName, editing])

  const gymId = values.gym === '' ? null : Number(values.gym)
  const difficulties = useGymDifficulties(gymId)

  const upload = useVideoUpload()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const uploading = upload.status === 'requesting' || upload.status === 'uploading'

  const error = mutation.error
  const serverError = (field: string) => getFieldError(error, field)
  const withServer = (check: FieldCheck, field: string): FieldCheck => {
    const message = serverError(field)
    return message ? invalid(message) : check
  }

  // --- 검증 (서버와 같은 규칙, 최종 판정은 서버) ---
  const attemptsNumber = Number(values.attempts)
  const attemptsValid = Number.isInteger(attemptsNumber) && attemptsNumber >= 1
  const attemptsCheck = withServer(
    values.attempts !== '' && !attemptsValid ? invalid('시도 횟수는 1 이상의 정수여야 합니다.') : IDLE,
    'attempts',
  )
  const today = toDateInputValue(new Date())
  const dateValid = /^\d{4}-\d{2}-\d{2}$/.test(values.climbedAt) && values.climbedAt <= today
  const dateCheck = withServer(
    values.climbedAt !== '' && !dateValid ? invalid('미래 날짜는 기록할 수 없습니다.') : IDLE,
    'climbed_at',
  )
  const memoCheck = withServer(IDLE, 'memo')
  const gymError = serverError('gym')
  const difficultyError = serverError('difficulty')
  const videoError = serverError('video_url')

  const canSubmit =
    values.gym !== '' &&
    attemptsValid &&
    dateValid &&
    values.memo.length <= MEMO_MAX_LENGTH &&
    !uploading
  const pending = mutation.isPending

  const fieldErrors = ['gym', 'difficulty', 'attempts', 'climbed_at', 'memo', 'video_url'].some(
    (field) => serverError(field),
  )
  const generalError =
    error && !fieldErrors
      ? getErrorMessage(error, '기록을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      : null

  const edit = <K extends keyof FormValues>(key: K, value: FormValues[K]) => {
    if (mutation.isError) mutation.reset()
    setValues((v) => ({ ...v, [key]: value }))
  }
  const onGymChange = (gym: string) => {
    touchedGym.current = true
    if (mutation.isError) mutation.reset()
    // 난이도는 암장에 종속 — 암장이 바뀌면 다시 고른다
    setValues((v) => ({ ...v, gym, difficulty: '' }))
  }

  const onPickFile = async (file: File | undefined) => {
    if (!file) return
    const fileUrl = await upload.upload(file)
    if (fileUrl) edit('videoUrl', fileUrl)
  }
  const onRemoveVideo = () => {
    upload.reset()
    if (fileInputRef.current) fileInputRef.current.value = ''
    edit('videoUrl', '')
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || pending) return
    const input: ClimbLogInput = {
      gym: Number(values.gym),
      difficulty: values.difficulty === '' ? null : Number(values.difficulty),
      isSuccess: values.isSuccess,
      attempts: attemptsNumber,
      climbedAt: values.climbedAt,
      memo: values.memo.trim(),
      videoUrl: values.videoUrl,
      isShared: values.isShared,
    }
    mutation.mutate(input, {
      onSuccess: (log) => navigate(`/logs/${log.id}`, { replace: editing !== undefined }),
    })
  }

  return (
    <div className="mx-auto mt-4 max-w-lg md:mt-8">
      <h1 className="mb-6 text-2xl font-semibold text-ink-700">
        {editing ? '기록 수정' : '기록하기'}
      </h1>
      <form
        onSubmit={onSubmit}
        noValidate
        className="space-y-5 rounded-card border border-chalk-300 bg-white p-6"
      >
        <SelectField
          label="암장"
          name="gym"
          placeholder={(geo.position ? nearby.isPending : points.isPending) ? '암장 목록 불러오는 중…' : '암장을 선택하세요'}
          hint={
            geo.position
              ? '가까운 암장 순으로 보여드려요'
              : homeGym !== null
                ? '홈짐이 기본으로 선택돼요'
                : undefined
          }
          options={gymOptions}
          value={values.gym}
          disabled={(geo.position ? nearby.isPending : points.isPending) || pending}
          error={gymError}
          onChange={(e) => onGymChange(e.target.value)}
          required
        />

        <DifficultyField
          gymSelected={gymId !== null}
          difficulties={difficulties.data ?? []}
          loading={difficulties.isPending && gymId !== null}
          value={values.difficulty}
          onChange={(difficulty) => edit('difficulty', difficulty)}
          error={difficultyError}
          disabled={pending}
        />

        <ResultField
          value={values.isSuccess}
          onChange={(isSuccess) => edit('isSuccess', isSuccess)}
          disabled={pending}
        />

        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="시도 횟수"
            name="attempts"
            type="number"
            min={1}
            step={1}
            inputMode="numeric"
            required
            value={values.attempts}
            check={attemptsCheck}
            onChange={(e) => edit('attempts', e.target.value)}
            disabled={pending}
          />
          <TextField
            label="등반일"
            name="climbedAt"
            type="date"
            max={today}
            required
            value={values.climbedAt}
            check={dateCheck}
            onChange={(e) => edit('climbedAt', e.target.value)}
            disabled={pending}
          />
        </div>

        <TextArea
          label="메모"
          name="memo"
          placeholder="어떤 문제였는지, 어디서 막혔는지, 다음에 시도할 베타를 적어 보세요"
          maxLength={MEMO_MAX_LENGTH}
          showCount
          value={values.memo}
          check={memoCheck}
          onChange={(e) => edit('memo', e.target.value)}
          disabled={pending}
        />

        <VideoField
          inputRef={fileInputRef}
          videoUrl={values.videoUrl}
          status={upload.status}
          progress={upload.progress}
          fileName={upload.fileName}
          error={upload.error ?? videoError}
          disabled={pending}
          onPick={onPickFile}
          onCancel={upload.cancel}
          onRemove={onRemoveVideo}
        />

        <label className="flex min-h-11 cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            name="isShared"
            checked={values.isShared}
            onChange={(e) => edit('isShared', e.target.checked)}
            disabled={pending}
            className="size-5 shrink-0 rounded accent-hold-500"
          />
          <span className="text-sm">
            <span className="block font-medium text-ink-600">피드에 공개</span>
            <span className="block text-xs text-pretty text-ink-400">
              끄면 나만 볼 수 있어요
            </span>
          </span>
        </label>

        {generalError && (
          <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
            {generalError}
          </p>
        )}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="secondary"
            onClick={() => navigate(editing ? `/logs/${editing.id}` : '/feed')}
            disabled={pending}
          >
            취소
          </Button>
          {/* 이 페이지의 유일한 primary CTA */}
          <Button type="submit" disabled={!canSubmit || pending}>
            {pending ? '저장 중…' : editing ? '저장' : '기록 남기기'}
          </Button>
        </div>
      </form>
    </div>
  )
}

// --- 칩 라디오 (난이도·결과) ---
// 네이티브 radio 를 sr-only 로 두고 label 을 칩으로 그린다 — 방향키 이동·폼 시맨틱은 브라우저 몫.
// 포커스 링은 숨은 input 대신 label 에 peer 로 옮겨 그린다.

const CHIP =
  'inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border px-3 text-sm ' +
  'transition-colors duration-150 ' +
  'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-hold-500 ' +
  'peer-disabled:cursor-not-allowed peer-disabled:opacity-50'

const CHIP_IDLE = 'border-chalk-300 bg-white text-ink-600 hover:bg-chalk-100'

function Chip({
  name,
  value,
  checked,
  onChange,
  disabled,
  activeClass,
  children,
}: {
  name: string
  value: string
  checked: boolean
  onChange: () => void
  disabled?: boolean
  activeClass: string
  children: ReactNode
}) {
  const id = `${name}-${value || 'none'}`
  return (
    <span>
      <input
        type="radio"
        id={id}
        name={name}
        value={value}
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="peer sr-only"
      />
      <label htmlFor={id} className={`${CHIP} ${checked ? activeClass : CHIP_IDLE}`}>
        {children}
      </label>
    </span>
  )
}

function DifficultyField({
  gymSelected,
  difficulties,
  loading,
  value,
  onChange,
  error,
  disabled,
}: {
  gymSelected: boolean
  difficulties: GymDifficulty[]
  loading: boolean
  value: string
  onChange: (value: string) => void
  error?: string
  disabled?: boolean
}) {
  const errorId = 'difficulty-error'
  return (
    <fieldset aria-describedby={error ? errorId : undefined}>
      <legend className="mb-1 block text-sm font-medium text-ink-500">난이도</legend>
      {!gymSelected ? (
        <p className="text-sm text-ink-400">암장을 먼저 선택하세요.</p>
      ) : loading ? (
        <p role="status" className="text-sm text-ink-400">
          난이도를 불러오는 중…
        </p>
      ) : difficulties.length === 0 ? (
        <p className="text-sm text-pretty text-ink-400">
          이 암장은 등록된 난이도가 없어요. 난이도 없이 기록할 수 있어요.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Chip
            name="difficulty"
            value=""
            checked={value === ''}
            onChange={() => onChange('')}
            disabled={disabled}
            activeClass="border-ink-500 bg-chalk-200 text-ink-700"
          >
            선택 안 함
          </Chip>
          {difficulties.map((difficulty) => (
            <Chip
              key={difficulty.id}
              name="difficulty"
              value={String(difficulty.id)}
              checked={value === String(difficulty.id)}
              onChange={() => onChange(String(difficulty.id))}
              disabled={disabled}
              activeClass="border-ink-500 bg-chalk-200 text-ink-700"
            >
              {/* 색은 토큰이 아니라 암장이 정한 값 */}
              <span
                aria-hidden
                className="size-3.5 shrink-0 rounded-full border border-chalk-400"
                style={{ backgroundColor: difficulty.color }}
              />
              {difficulty.name}
            </Chip>
          ))}
        </div>
      )}
      {error && (
        <p id={errorId} role="alert" className="mt-1 text-xs text-pretty text-danger-500">
          {error}
        </p>
      )}
    </fieldset>
  )
}

function ResultField({
  value,
  onChange,
  disabled,
}: {
  value: boolean
  onChange: (value: boolean) => void
  disabled?: boolean
}) {
  return (
    <fieldset>
      <legend className="mb-1 block text-sm font-medium text-ink-500">결과</legend>
      <div className="flex gap-2">
        <Chip
          name="isSuccess"
          value="true"
          checked={value}
          onChange={() => onChange(true)}
          disabled={disabled}
          activeClass="border-moss-500 bg-moss-100 font-medium text-moss-500"
        >
          성공
        </Chip>
        {/* 실패는 오류가 아니다 — danger 대신 ink */}
        <Chip
          name="isSuccess"
          value="false"
          checked={!value}
          onChange={() => onChange(false)}
          disabled={disabled}
          activeClass="border-ink-500 bg-chalk-200 font-medium text-ink-700"
        >
          실패
        </Chip>
      </div>
    </fieldset>
  )
}

// --- 영상 ---

function VideoField({
  inputRef,
  videoUrl,
  status,
  progress,
  fileName,
  error,
  disabled,
  onPick,
  onCancel,
  onRemove,
}: {
  inputRef: RefObject<HTMLInputElement | null>
  videoUrl: string
  status: UploadStatus
  progress: number
  fileName: string | null
  error: string | null | undefined
  disabled?: boolean
  onPick: (file: File | undefined) => void
  onCancel: () => void
  onRemove: () => void
}) {
  const uploading = status === 'requesting' || status === 'uploading'
  const attached = videoUrl !== '' && !uploading
  const errorId = 'video-error'

  return (
    <div>
      <p className="mb-1 text-sm font-medium text-ink-500">영상 (선택)</p>
      <input
        ref={inputRef}
        type="file"
        accept={CLIMB_VIDEO_TYPES.join(',')}
        onChange={(e) => onPick(e.target.files?.[0])}
        disabled={disabled || uploading}
        aria-describedby={error ? errorId : 'video-hint'}
        className="sr-only"
        tabIndex={-1}
      />
      {attached ? (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-chalk-300 bg-chalk-50 px-3 py-2">
          <p role="status" className="min-w-0 truncate text-sm text-ink-600">
            <span aria-hidden className="mr-1.5 text-moss-500">
              ✓
            </span>
            {fileName ?? '영상 첨부됨'}
          </p>
          <Button variant="secondary" onClick={onRemove} disabled={disabled}>
            제거
          </Button>
        </div>
      ) : uploading ? (
        <div className="rounded-xl border border-chalk-300 bg-chalk-50 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <p role="status" className="min-w-0 truncate text-sm text-ink-600">
              {status === 'requesting' ? '업로드 준비 중…' : `올리는 중 ${percent.format(progress)}`}
              {fileName && <span className="ml-1 text-ink-400">— {fileName}</span>}
            </p>
            <Button variant="secondary" onClick={onCancel}>
              취소
            </Button>
          </div>
          <div
            role="progressbar"
            aria-label="영상 업로드"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress * 100)}
            className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-chalk-200"
          >
            <div
              className="h-full origin-left rounded-full bg-hold-300 transition-transform duration-150 ease-out"
              style={{ transform: `scaleX(${progress})` }}
            />
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            onClick={() => inputRef.current?.click()}
            disabled={disabled}
          >
            영상 파일 선택
          </Button>
          <span id="video-hint" className="text-xs text-pretty text-ink-400">
            MP4 · MOV · WebM
          </span>
        </div>
      )}
      {error && (
        <p id={errorId} role="alert" className="mt-1 text-xs text-pretty text-danger-500">
          {error}
        </p>
      )}
    </div>
  )
}
