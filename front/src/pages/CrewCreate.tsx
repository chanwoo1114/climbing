import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { getErrorCode, getErrorMessage, getFieldError } from '@/api/client'
import {
  CREW_DESCRIPTION_MAX_LENGTH,
  CREW_JOIN_TYPE_LABEL,
  CREW_MAX_MEMBERS_DEFAULT,
  CREW_MAX_MEMBERS_MAX,
  CREW_MAX_MEMBERS_MIN,
  CREW_NAME_MAX_LENGTH,
  isManagerStatus,
  type Crew,
  type CrewInput,
  type CrewJoinType,
} from '@/api/crews'
import { POST_IMAGE_TYPES } from '@/api/posts'
import Button from '@/components/common/Button'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import SelectField, { type SelectOption } from '@/components/common/SelectField'
import TextArea from '@/components/common/TextArea'
import TextField from '@/components/common/TextField'
import { CrewImage, count } from '@/components/crews/CrewBits'
import { useMe } from '@/hooks/useAuth'
import { useCreateCrew, useCrew, useDeleteCrew, useUpdateCrew } from '@/hooks/useCrews'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useGymPoints, useGyms } from '@/hooks/useGyms'
import { useUpload } from '@/hooks/useUpload'
import type { FieldCheck } from '@/lib/validation'

const percent = new Intl.NumberFormat('ko-KR', { style: 'percent', maximumFractionDigits: 0 })

interface FormValues {
  name: string
  description: string
  image: string
  homeGym: string
  joinType: CrewJoinType
  maxMembers: string
  isFeedPublic: boolean
}

const fromCrew = (crew: Crew): FormValues => ({
  name: crew.name,
  description: crew.description,
  image: crew.image,
  homeGym: crew.homeGym ? String(crew.homeGym.id) : '',
  joinType: crew.joinType,
  maxMembers: String(crew.maxMembers),
  isFeedPublic: crew.isFeedPublic,
})

const blank = (homeGym: string): FormValues => ({
  name: '',
  description: '',
  image: '',
  homeGym,
  joinType: 'instant',
  maxMembers: String(CREW_MAX_MEMBERS_DEFAULT),
  isFeedPublic: false,
})

/** /crews/new 와 /crews/:id/edit 를 같이 처리한다 */
export default function CrewCreate() {
  const { id } = useParams()
  const editing = id !== undefined
  const crewId = Number(id)
  const validId = Number.isInteger(crewId) && crewId > 0
  const { data: me } = useMe()
  const crew = useCrew(editing && validId ? crewId : NaN)

  if (!editing) {
    return <CrewForm homeGym={me?.homeGym ?? null} homeGymName={me?.homeGymName ?? null} />
  }
  const code = crew.isError ? getErrorCode(crew.error) : undefined
  if (!validId || code === 'http_404' || code === 'not_found') {
    return <Blocked message="크루를 찾을 수 없어요." />
  }
  if (crew.isPending) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (crew.isError || !crew.data) {
    return <Blocked message="크루를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." />
  }
  if (!isManagerStatus(crew.data.myStatus)) {
    return (
      <Blocked message="크루장·운영진만 크루를 수정할 수 있어요." to={`/crews/${crew.data.id}`} />
    )
  }
  return (
    <CrewForm
      editing={crew.data}
      homeGym={me?.homeGym ?? null}
      homeGymName={me?.homeGymName ?? null}
    />
  )
}

function Blocked({ message, to = '/crews' }: { message: string; to?: string }) {
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

function CrewForm({
  editing,
  homeGym,
  homeGymName,
}: {
  editing?: Crew
  homeGym: number | null
  homeGymName: string | null
}) {
  const navigate = useNavigate()
  const create = useCreateCrew()
  const update = useUpdateCrew(editing?.id ?? NaN)
  const mutation = editing ? update : create

  const [values, setValues] = useState<FormValues>(() =>
    editing ? fromCrew(editing) : blank(homeGym === null ? '' : String(homeGym)),
  )
  // 새 크루: 내 홈짐(useMe)이 폼보다 늦게 도착하면 아직 안 골랐을 때만 채워 넣는다
  const touchedGym = useRef(editing !== undefined)
  useEffect(() => {
    if (!touchedGym.current && homeGym !== null && values.homeGym === '') {
      setValues((v) => ({ ...v, homeGym: String(homeGym) }))
    }
  }, [homeGym, values.homeGym])

  // 암장 후보: 내 위치를 알면 가까운 순, 모르면 전국 전체를 가나다순 (PostCreate 와 같은 규칙)
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
    if (homeGym !== null) ensureFirst(String(homeGym), homeGymName ?? `암장 #${homeGym}`)
    if (editing?.homeGym) ensureFirst(String(editing.homeGym.id), editing.homeGym.name)
    return options
  }, [geo.position, nearby.data, points.data, homeGym, homeGymName, editing])
  const gymsLoading = geo.position ? nearby.isPending : points.isPending

  const error = mutation.error
  const serverError = (field: string) => getFieldError(error, field)
  const withServer = (check: FieldCheck, message: string | undefined): FieldCheck =>
    message ? invalid(message) : check

  // --- 검증 (서버와 같은 규칙, 최종 판정은 서버) ---
  const nameTrimmed = values.name.trim()
  const nameValid = nameTrimmed.length > 0 && nameTrimmed.length <= CREW_NAME_MAX_LENGTH
  const nameCheck = withServer(
    values.name.length > CREW_NAME_MAX_LENGTH
      ? invalid(`크루 이름은 ${CREW_NAME_MAX_LENGTH}자 이하여야 합니다.`)
      : IDLE,
    serverError('name'),
  )
  const descriptionValid = values.description.length <= CREW_DESCRIPTION_MAX_LENGTH
  const descriptionCheck = withServer(IDLE, serverError('description'))

  // 수정 중엔 이미 활동 중인 인원(크루장 포함)보다 최대 인원을 줄일 수 없다
  const membersMin = editing
    ? Math.max(CREW_MAX_MEMBERS_MIN, editing.memberCount)
    : CREW_MAX_MEMBERS_MIN
  const maxMembersNumber = Number(values.maxMembers)
  const maxMembersValid =
    Number.isInteger(maxMembersNumber) &&
    maxMembersNumber >= membersMin &&
    maxMembersNumber <= CREW_MAX_MEMBERS_MAX
  const maxMembersCheck = withServer(
    values.maxMembers !== '' && !maxMembersValid
      ? invalid(
          membersMin > CREW_MAX_MEMBERS_MIN && maxMembersNumber < membersMin
            ? `이미 ${count.format(membersMin)}명이 활동 중이라 그보다 줄일 수 없어요.`
            : `최대 인원은 ${CREW_MAX_MEMBERS_MIN}~${CREW_MAX_MEMBERS_MAX}명이에요.`,
        )
      : IDLE,
    serverError('max_members'),
  )
  const gymError = serverError('home_gym')
  const joinTypeError = serverError('join_type')
  const imageError = serverError('image')

  const [uploading, setUploading] = useState(false)
  const canSubmit = nameValid && descriptionValid && maxMembersValid && !uploading
  const pending = mutation.isPending

  const fieldErrors = [
    'name',
    'description',
    'image',
    'home_gym',
    'join_type',
    'max_members',
    'is_feed_public',
  ].some((field) => serverError(field))
  const generalError =
    error && !fieldErrors
      ? getErrorMessage(error, '크루를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      : null

  const edit = <K extends keyof FormValues>(key: K, value: FormValues[K]) => {
    if (mutation.isError) mutation.reset()
    setValues((v) => ({ ...v, [key]: value }))
  }
  const onGymChange = (homeGym: string) => {
    touchedGym.current = true
    edit('homeGym', homeGym)
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || pending) return
    const input: CrewInput = {
      name: nameTrimmed,
      description: values.description.trim(),
      image: values.image,
      homeGym: values.homeGym === '' ? null : Number(values.homeGym),
      joinType: values.joinType,
      maxMembers: maxMembersNumber,
      isFeedPublic: values.isFeedPublic,
    }
    if (editing) {
      update.mutate(input, {
        onSuccess: (crew) => navigate(`/crews/${crew.id}`, { replace: true }),
      })
      return
    }
    create.mutate(input, {
      onSuccess: (crew) => navigate(`/crews/${crew.id}`),
    })
  }

  return (
    <div className="mx-auto mt-4 max-w-lg md:mt-8">
      <h1 className="mb-6 text-2xl font-semibold text-ink-700">
        {editing ? '크루 설정' : '크루 만들기'}
      </h1>
      <form
        onSubmit={onSubmit}
        noValidate
        className="space-y-5 rounded-card border border-chalk-300 bg-white p-6"
      >
        <TextField
          label="크루 이름"
          name="name"
          placeholder="예) 양재 볼더링 클럽"
          maxLength={CREW_NAME_MAX_LENGTH}
          autoComplete="off"
          required
          value={values.name}
          check={nameCheck}
          onChange={(e) => edit('name', e.target.value)}
          disabled={pending}
        />

        <TextArea
          label="소개 (선택)"
          name="description"
          placeholder="어떤 크루인지, 언제 주로 모이는지 적어 주세요"
          maxLength={CREW_DESCRIPTION_MAX_LENGTH}
          showCount
          value={values.description}
          check={descriptionCheck}
          onChange={(e) => edit('description', e.target.value)}
          disabled={pending}
          rows={5}
        />

        <ImageField
          name={values.name}
          image={values.image}
          onChange={(image) => edit('image', image)}
          onBusyChange={setUploading}
          error={imageError}
          disabled={pending}
        />

        <SelectField
          label="홈짐 (선택)"
          name="homeGym"
          placeholder={gymsLoading ? '암장 목록 불러오는 중…' : '선택 안 함'}
          hint={
            geo.position ? '주로 모이는 암장이에요. 가까운 암장 순으로 보여드려요' : '주로 모이는 암장이에요'
          }
          options={gymOptions}
          value={values.homeGym}
          disabled={gymsLoading || pending}
          error={gymError}
          onChange={(e) => onGymChange(e.target.value)}
        />

        <JoinTypeField
          value={values.joinType}
          onChange={(joinType) => edit('joinType', joinType)}
          error={joinTypeError}
          disabled={pending}
        />

        <TextField
          label="최대 인원 (크루장 포함)"
          name="maxMembers"
          type="number"
          min={membersMin}
          max={CREW_MAX_MEMBERS_MAX}
          step={1}
          inputMode="numeric"
          required
          value={values.maxMembers}
          check={maxMembersCheck}
          onChange={(e) => edit('maxMembers', e.target.value)}
          disabled={pending}
        />

        <label className="flex min-h-11 cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            name="isFeedPublic"
            checked={values.isFeedPublic}
            onChange={(e) => edit('isFeedPublic', e.target.checked)}
            disabled={pending}
            className="size-5 shrink-0 rounded accent-hold-500"
          />
          <span className="text-sm">
            <span className="block font-medium text-ink-600">크루 피드 공개</span>
            <span className="block text-xs text-pretty text-ink-400">
              끄면 크루원만 크루 피드를 볼 수 있어요
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
            onClick={() => navigate(editing ? `/crews/${editing.id}` : '/crews')}
            disabled={pending}
          >
            취소
          </Button>
          {/* 이 페이지의 유일한 primary CTA */}
          <Button type="submit" disabled={!canSubmit || pending}>
            {pending ? '저장 중…' : editing ? '저장' : '크루 만들기'}
          </Button>
        </div>
      </form>

      {editing?.myStatus === 'owner' && <DeleteCrew crew={editing} />}
    </div>
  )
}

// --- 칩 라디오 (가입 방식) — PostCreate/LogCreate 와 같은 규칙 ---
// 네이티브 radio 를 sr-only 로 두고 label 을 칩으로 그린다. 포커스 링은 label 에 peer 로 옮겨 그린다.

const CHIP =
  'inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border px-3 text-sm ' +
  'transition-colors duration-150 ' +
  'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-hold-500 ' +
  'peer-disabled:cursor-not-allowed peer-disabled:opacity-50'

const CHIP_IDLE = 'border-chalk-300 bg-white text-ink-600 hover:bg-chalk-100'
const CHIP_ACTIVE = 'border-ink-500 bg-chalk-200 font-medium text-ink-700'

function Chip({
  name,
  value,
  checked,
  onChange,
  disabled,
  children,
}: {
  name: string
  value: string
  checked: boolean
  onChange: () => void
  disabled?: boolean
  children: ReactNode
}) {
  const id = `${name}-${value}`
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
      <label htmlFor={id} className={`${CHIP} ${checked ? CHIP_ACTIVE : CHIP_IDLE}`}>
        {children}
      </label>
    </span>
  )
}

function JoinTypeField({
  value,
  onChange,
  error,
  disabled,
}: {
  value: CrewJoinType
  onChange: (value: CrewJoinType) => void
  error?: string
  disabled?: boolean
}) {
  const errorId = 'join-type-error'
  return (
    <fieldset aria-describedby={error ? errorId : undefined}>
      <legend className="mb-1 block text-sm font-medium text-ink-500">가입 방식</legend>
      <div className="flex flex-wrap gap-2">
        {(['instant', 'approval'] as const).map((joinType) => (
          <Chip
            key={joinType}
            name="joinType"
            value={joinType}
            checked={value === joinType}
            onChange={() => onChange(joinType)}
            disabled={disabled}
          >
            {CREW_JOIN_TYPE_LABEL[joinType]}
          </Chip>
        ))}
      </div>
      <p className="mt-1 text-xs text-pretty text-ink-400">
        {value === 'instant'
          ? '신청하면 바로 크루원이 되고 채팅방에 들어와요.'
          : '신청을 받은 뒤 크루장·운영진이 한 명씩 승인해요.'}
      </p>
      {error && (
        <p id={errorId} role="alert" className="mt-1 text-xs text-pretty text-danger-500">
          {error}
        </p>
      )}
    </fieldset>
  )
}

// --- 대표 이미지 ---

/**
 * presigned 업로드 한 장. 저장소가 설정되지 않은 서버(503 storage_not_configured)면
 * 안내만 하고 이미지 없이 만들 수 있게 둔다.
 */
function ImageField({
  name,
  image,
  onChange,
  onBusyChange,
  error,
  disabled,
}: {
  name: string
  image: string
  onChange: (url: string) => void
  onBusyChange: (busy: boolean) => void
  error?: string
  disabled?: boolean
}) {
  const upload = useUpload('post_image', POST_IMAGE_TYPES)
  const inputRef = useRef<HTMLInputElement>(null)

  const busy = upload.status === 'requesting' || upload.status === 'uploading'
  useEffect(() => onBusyChange(busy), [busy, onBusyChange])

  const storageUnavailable = upload.errorCode === 'storage_not_configured'
  const errorId = 'image-error'
  const hintId = 'image-hint'

  const onPick = async (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    const url = await upload.upload(file)
    if (url) onChange(url)
    if (inputRef.current) inputRef.current.value = ''
  }

  const onRemove = () => {
    upload.reset()
    onChange('')
  }

  const message = (upload.status === 'error' && !storageUnavailable ? upload.error : null) ?? error

  return (
    <div>
      <p className="mb-1 text-sm font-medium text-ink-500">대표 이미지 (선택)</p>
      <input
        ref={inputRef}
        type="file"
        accept={POST_IMAGE_TYPES.join(',')}
        onChange={(e) => onPick(e.target.files)}
        disabled={disabled || busy || storageUnavailable}
        aria-describedby={message ? errorId : hintId}
        className="sr-only"
        tabIndex={-1}
      />

      {busy ? (
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
            aria-label="이미지 업로드"
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
          이미지 저장소가 아직 설정되지 않았어요. 지금은 이미지 없이 만들 수 있어요.
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <CrewImage crew={{ name: name || '?', image }} />
          <Button
            variant="secondary"
            onClick={() => inputRef.current?.click()}
            disabled={disabled}
          >
            {image ? '이미지 바꾸기' : '이미지 선택'}
          </Button>
          {image ? (
            <Button variant="secondary" onClick={onRemove} disabled={disabled}>
              제거
            </Button>
          ) : (
            <span id={hintId} className="text-xs text-pretty text-ink-400">
              JPG · PNG · WebP
            </span>
          )}
        </div>
      )}
      {message && (
        <p id={errorId} role="alert" className="mt-1 text-xs text-pretty text-danger-500">
          {message}
        </p>
      )}
    </div>
  )
}

// --- 삭제 (크루장만) ---

function DeleteCrew({ crew }: { crew: Crew }) {
  const navigate = useNavigate()
  const remove = useDeleteCrew()
  const [confirm, setConfirm] = useState(false)

  const onDelete = () => {
    remove.mutate(crew.id, {
      onSuccess: () => navigate('/crews', { replace: true }),
    })
  }

  return (
    <section
      aria-labelledby="delete-heading"
      className="mt-6 rounded-card border border-chalk-300 bg-white p-6"
    >
      <h2 id="delete-heading" className="text-base font-semibold text-ink-700">
        크루 삭제
      </h2>
      <p className="mt-1 text-sm text-pretty text-ink-500">
        크루원 {count.format(crew.memberCount)}명의 소속이 모두 해제돼요. 채팅방의 대화 기록은 남아요.
      </p>
      {remove.isError && (
        <p role="alert" className="mt-3 rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {getErrorMessage(remove.error, '크루를 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
      )}
      {/* 파괴적 액션 — 실행은 확인 모달 안의 danger 버튼이 한다 */}
      <button
        type="button"
        onClick={() => setConfirm(true)}
        disabled={remove.isPending}
        className="-ml-2 mt-2 inline-flex min-h-11 items-center px-2 text-sm font-medium text-danger-500 transition-colors duration-150 hover:text-danger-600 disabled:opacity-50"
      >
        크루 삭제
      </button>

      <ConfirmDialog
        open={confirm}
        title={`'${crew.name}' 크루를 삭제할까요?`}
        description="크루원들의 소속과 대표 크루 설정이 모두 해제되며 되돌릴 수 없어요."
        confirmLabel="삭제"
        pendingLabel="삭제 중…"
        pending={remove.isPending}
        onConfirm={onDelete}
        onCancel={() => setConfirm(false)}
      />
    </section>
  )
}
