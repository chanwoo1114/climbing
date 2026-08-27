import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { getErrorCode, getErrorMessage, getFieldError, type ApiError } from '@/api/client'
import {
  CATEGORY_LABEL,
  CONTENT_MAX_LENGTH,
  JOIN_TYPE_LABEL,
  MAX_POST_IMAGES,
  POST_IMAGE_TYPES,
  RECRUIT_CAPACITY_MAX,
  RECRUIT_CAPACITY_MIN,
  TITLE_MAX_LENGTH,
  type JoinType,
  type Post,
  type PostCategory,
  type PostInput,
  type PostUpdate,
  type RecruitmentInput,
} from '@/api/posts'
import Button from '@/components/common/Button'
import SelectField, { type SelectOption } from '@/components/common/SelectField'
import TextArea from '@/components/common/TextArea'
import TextField from '@/components/common/TextField'
import { CategoryBadge, memberCount as recruitMemberCount } from '@/components/community/PostBits'
import { useMe } from '@/hooks/useAuth'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useGymPoints, useGyms } from '@/hooks/useGyms'
import { useCreatePost, usePost, useUpdatePost } from '@/hooks/usePosts'
import { useUpload } from '@/hooks/useUpload'
import type { FieldCheck } from '@/lib/validation'

/** <input type="datetime-local"> 값 — 로컬 기준 YYYY-MM-DDTHH:mm (toISOString 은 UTC 라 어긋난다) */
function toDateTimeLocal(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** datetime-local 값 → Date. 비었거나 이상하면 null */
function fromDateTimeLocal(value: string): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const percent = new Intl.NumberFormat('ko-KR', { style: 'percent', maximumFractionDigits: 0 })
const count = new Intl.NumberFormat('ko-KR')

interface FormValues {
  category: PostCategory
  title: string
  content: string
  gym: string
  images: string[]
  meetAt: string
  capacity: string
  joinType: JoinType
}

const fromPost = (post: Post): FormValues => ({
  category: post.category,
  title: post.title,
  content: post.content,
  gym: post.recruitment ? String(post.recruitment.gym.id) : post.gym ? String(post.gym.id) : '',
  images: post.images,
  meetAt: post.recruitment ? toDateTimeLocal(new Date(post.recruitment.meetAt)) : '',
  capacity: post.recruitment ? String(post.recruitment.capacity) : '4',
  joinType: post.recruitment?.joinType ?? 'instant',
})

const blank = (category: PostCategory, gym: string): FormValues => ({
  category,
  title: '',
  content: '',
  gym,
  images: [],
  meetAt: '',
  capacity: '4',
  joinType: 'instant',
})

/** /posts/new 와 /posts/:id/edit 를 같이 처리한다 */
export default function PostCreate() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const editing = id !== undefined
  const postId = Number(id)
  const validId = Number.isInteger(postId) && postId > 0
  const { data: me } = useMe()
  const post = usePost(editing && validId ? postId : NaN)

  if (!editing) {
    // 목록의 "글쓰기" 가 현재 탭·암장 필터를 넘겨준다
    const category = searchParams.get('category') === 'recruit' ? 'recruit' : 'free'
    const gym = Number(searchParams.get('gym'))
    // 크루 상세의 "크루 모집 올리기" 가 ?crew= 를 넘긴다 → 크루 주최 모집
    const crew = Number(searchParams.get('crew'))
    return (
      <PostForm
        initialCategory={category}
        initialGym={Number.isInteger(gym) && gym > 0 ? String(gym) : null}
        crewId={Number.isInteger(crew) && crew > 0 ? crew : null}
        homeGym={me?.homeGym ?? null}
        homeGymName={me?.homeGymName ?? null}
      />
    )
  }
  if (!validId || (post.isError && getErrorCode(post.error) === 'http_404')) {
    return <Blocked message="게시글을 찾을 수 없어요." />
  }
  if (post.isPending || !me) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (post.isError || !post.data) {
    return <Blocked message="게시글을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." />
  }
  if (post.data.user.id !== me.id) {
    return <Blocked message="본인의 게시글만 수정할 수 있어요." to={`/posts/${post.data.id}`} />
  }
  return (
    <PostForm
      editing={post.data}
      initialCategory={post.data.category}
      initialGym={null}
      homeGym={me.homeGym}
      homeGymName={me.homeGymName}
    />
  )
}

function Blocked({ message, to = '/posts' }: { message: string; to?: string }) {
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

/**
 * 모집 정보의 서버 오류는 중첩으로 온다 — fields.recruitment 가
 * 필드별 dict({capacity: [...]}) 이거나 문장 목록(["모집글에는 모집 정보가 필요합니다."]) 이다.
 */
function recruitmentError(error: unknown, field?: string): string | undefined {
  const value = (error as ApiError | undefined)?.fields?.recruitment as unknown
  if (value === undefined || value === null) return undefined
  if (Array.isArray(value)) return field === undefined ? String(value[0]) : undefined
  if (field !== undefined && typeof value === 'object') {
    return (value as Record<string, string[] | undefined>)[field]?.[0]
  }
  return undefined
}

function PostForm({
  editing,
  initialCategory,
  initialGym,
  crewId = null,
  homeGym,
  homeGymName,
}: {
  editing?: Post
  initialCategory: PostCategory
  initialGym: string | null
  /** 크루 주최 모집일 때 크루 id (recruitment.crew 로 전송) */
  crewId?: number | null
  homeGym: number | null
  homeGymName: string | null
}) {
  const navigate = useNavigate()
  const create = useCreatePost()
  const update = useUpdatePost(editing?.id ?? NaN)
  const mutation = editing ? update : create

  const [values, setValues] = useState<FormValues>(() =>
    editing
      ? fromPost(editing)
      : blank(initialCategory, initialGym ?? (homeGym === null ? '' : String(homeGym))),
  )
  // 새 글: 홈짐(useMe)이 폼보다 늦게 도착하면 아직 안 골랐을 때만 채워 넣는다
  const touchedGym = useRef(editing !== undefined || initialGym !== null)
  useEffect(() => {
    if (!touchedGym.current && homeGym !== null && values.gym === '') {
      setValues((v) => ({ ...v, gym: String(homeGym) }))
    }
  }, [homeGym, values.gym])

  // 암장 후보: 내 위치를 알면 가까운 순, 모르면 전국 전체를 가나다순 (LogCreate 와 같은 규칙)
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
    const editingGym = editing?.recruitment?.gym ?? editing?.gym ?? null
    if (editingGym) ensureFirst(String(editingGym.id), editingGym.name)
    return options
  }, [geo.position, nearby.data, points.data, homeGym, homeGymName, editing])
  const gymsLoading = geo.position ? nearby.isPending : points.isPending

  const isRecruit = values.category === 'recruit'
  const error = mutation.error
  const serverError = (field: string) => getFieldError(error, field)
  const withServer = (check: FieldCheck, message: string | undefined): FieldCheck =>
    message ? invalid(message) : check

  // --- 검증 (서버와 같은 규칙, 최종 판정은 서버) ---
  const titleTrimmed = values.title.trim()
  const titleValid = titleTrimmed.length > 0 && values.title.length <= TITLE_MAX_LENGTH
  const titleCheck = withServer(
    values.title.length > TITLE_MAX_LENGTH
      ? invalid(`제목은 ${TITLE_MAX_LENGTH}자 이하여야 합니다.`)
      : IDLE,
    serverError('title'),
  )
  const contentTrimmed = values.content.trim()
  const contentValid = contentTrimmed.length > 0 && values.content.length <= CONTENT_MAX_LENGTH
  const contentCheck = withServer(IDLE, serverError('content'))

  const now = new Date()
  const meetAtDate = fromDateTimeLocal(values.meetAt)
  const meetAtValid = meetAtDate !== null && meetAtDate.getTime() > now.getTime()
  const meetAtCheck = withServer(
    values.meetAt !== '' && !meetAtValid ? invalid('모임 일시는 지금 이후여야 합니다.') : IDLE,
    recruitmentError(error, 'meet_at'),
  )
  // 수정 중엔 이미 확정된 인원(작성자 포함)보다 정원을 줄일 수 없다
  const capacityMin = editing?.recruitment
    ? Math.max(RECRUIT_CAPACITY_MIN, recruitMemberCount(editing.recruitment))
    : RECRUIT_CAPACITY_MIN
  const capacityNumber = Number(values.capacity)
  const capacityValid =
    Number.isInteger(capacityNumber) &&
    capacityNumber >= capacityMin &&
    capacityNumber <= RECRUIT_CAPACITY_MAX
  const capacityCheck = withServer(
    values.capacity !== '' && !capacityValid
      ? invalid(
          capacityMin > RECRUIT_CAPACITY_MIN && capacityNumber < capacityMin
            ? `이미 ${count.format(capacityMin)}명이 참여 중이라 그보다 줄일 수 없어요.`
            : `정원은 ${RECRUIT_CAPACITY_MIN}~${RECRUIT_CAPACITY_MAX}명이에요.`,
        )
      : IDLE,
    recruitmentError(error, 'capacity'),
  )
  const gymError = serverError('gym') ?? (isRecruit ? recruitmentError(error, 'gym') : undefined)
  const joinTypeError = recruitmentError(error, 'join_type')
  const imagesError = serverError('images')

  const recruitValid = !isRecruit || (values.gym !== '' && meetAtValid && capacityValid)
  const [uploading, setUploading] = useState(false)
  const canSubmit = titleValid && contentValid && recruitValid && !uploading
  const pending = mutation.isPending

  const fieldErrors =
    ['title', 'content', 'gym', 'images', 'category'].some((field) => serverError(field)) ||
    recruitmentError(error, 'gym') !== undefined ||
    recruitmentError(error, 'meet_at') !== undefined ||
    recruitmentError(error, 'capacity') !== undefined ||
    joinTypeError !== undefined
  const generalError = error
    ? fieldErrors
      ? null
      : (recruitmentError(error) ??
        serverError('category') ??
        getErrorMessage(error, '게시글을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.'))
    : null

  const edit = <K extends keyof FormValues>(key: K, value: FormValues[K]) => {
    if (mutation.isError) mutation.reset()
    setValues((v) => ({ ...v, [key]: value }))
  }
  const onGymChange = (gym: string) => {
    touchedGym.current = true
    edit('gym', gym)
  }
  const addImage = (url: string) => {
    if (mutation.isError) mutation.reset()
    setValues((v) =>
      v.images.length >= MAX_POST_IMAGES ? v : { ...v, images: [...v.images, url] },
    )
  }
  const removeImage = (index: number) =>
    edit(
      'images',
      values.images.filter((_, i) => i !== index),
    )

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || pending) return
    const gym = values.gym === '' ? null : Number(values.gym)
    const recruitment: RecruitmentInput | undefined =
      isRecruit && meetAtDate
        ? {
            gym: Number(values.gym),
            meetAt: meetAtDate.toISOString(),
            capacity: capacityNumber,
            joinType: values.joinType,
            ...(crewId !== null && !editing ? { crew: crewId } : {}),
          }
        : undefined

    if (editing) {
      const before = editing.recruitment
      // 모집 정보는 바뀐 게 있을 때만 보낸다 — 이미 지난 모임의 제목만 고칠 때 meet_at 검증에 걸리지 않게
      const recruitChanged =
        recruitment !== undefined &&
        before !== null &&
        (recruitment.gym !== before.gym.id ||
          recruitment.meetAt !== new Date(before.meetAt).toISOString() ||
          recruitment.capacity !== before.capacity ||
          recruitment.joinType !== before.joinType)
      const input: PostUpdate = {
        title: titleTrimmed,
        content: contentTrimmed,
        gym,
        images: values.images,
        ...(recruitChanged ? { recruitment } : {}),
      }
      update.mutate(input, {
        onSuccess: (post) => navigate(`/posts/${post.id}`, { replace: true }),
      })
      return
    }
    const input: PostInput = {
      category: values.category,
      title: titleTrimmed,
      content: contentTrimmed,
      gym,
      images: values.images,
      ...(recruitment ? { recruitment } : {}),
    }
    create.mutate(input, {
      onSuccess: (post) => navigate(`/posts/${post.id}`),
    })
  }

  return (
    <div className="mx-auto mt-4 max-w-lg md:mt-8">
      <h1 className="mb-6 text-2xl font-semibold text-ink-700">
        {editing ? '글 수정' : '글쓰기'}
      </h1>
      <form
        onSubmit={onSubmit}
        noValidate
        className="space-y-5 rounded-card border border-chalk-300 bg-white p-6"
      >
        {editing ? (
          <div>
            <p className="mb-1 text-sm font-medium text-ink-500">종류</p>
            <div className="flex items-center gap-2">
              <CategoryBadge category={values.category} />
              <span className="text-xs text-ink-400">글의 종류는 바꿀 수 없어요</span>
            </div>
          </div>
        ) : (
          <fieldset>
            <legend className="mb-1 block text-sm font-medium text-ink-500">종류</legend>
            <div className="flex gap-2">
              {(['free', 'recruit'] as const).map((category) => (
                <Chip
                  key={category}
                  name="category"
                  value={category}
                  checked={values.category === category}
                  onChange={() => edit('category', category)}
                  disabled={pending}
                  activeClass={
                    category === 'recruit'
                      ? 'border-ochre-400 bg-ochre-100 font-medium text-ochre-500'
                      : 'border-slate-400 bg-slate-100 font-medium text-slate-500'
                  }
                >
                  {CATEGORY_LABEL[category]}
                </Chip>
              ))}
            </div>
            <p className="mt-1 text-xs text-pretty text-ink-400">
              {isRecruit
                ? '같이 갈 사람을 모아요. 암장·일시·정원을 정해 주세요.'
                : '자유롭게 이야기를 나눠요.'}
            </p>
          </fieldset>
        )}

        <TextField
          label="제목"
          name="title"
          placeholder={isRecruit ? '예) 토요일 저녁 더클라임 양재 같이 가요' : '제목을 입력하세요'}
          maxLength={TITLE_MAX_LENGTH}
          required
          value={values.title}
          check={titleCheck}
          onChange={(e) => edit('title', e.target.value)}
          disabled={pending}
        />

        <TextArea
          label="내용"
          name="content"
          placeholder={
            isRecruit
              ? '어떤 분위기로 갈지, 실력대는 어느 정도면 좋을지 적어 주세요'
              : '나누고 싶은 이야기를 적어 주세요'
          }
          maxLength={CONTENT_MAX_LENGTH}
          showCount
          required
          value={values.content}
          check={contentCheck}
          onChange={(e) => edit('content', e.target.value)}
          disabled={pending}
          rows={8}
        />

        <SelectField
          label={isRecruit ? '투어 암장' : '관련 암장 (선택)'}
          name="gym"
          placeholder={
            gymsLoading ? '암장 목록 불러오는 중…' : isRecruit ? '암장을 선택하세요' : '선택 안 함'
          }
          hint={
            isRecruit
              ? '모집 대상 암장이에요. 글의 관련 암장으로도 표시돼요.'
              : geo.position
                ? '가까운 암장 순으로 보여드려요'
                : undefined
          }
          options={gymOptions}
          value={values.gym}
          disabled={gymsLoading || pending}
          error={gymError}
          onChange={(e) => onGymChange(e.target.value)}
          required={isRecruit}
        />

        {isRecruit && (
          <fieldset className="space-y-4 rounded-xl border border-chalk-300 bg-chalk-50 p-4">
            <legend className="px-1 text-sm font-medium text-ink-600">모집 정보</legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <TextField
                label="모임 일시"
                name="meetAt"
                type="datetime-local"
                min={toDateTimeLocal(now)}
                required
                value={values.meetAt}
                check={meetAtCheck}
                onChange={(e) => edit('meetAt', e.target.value)}
                disabled={pending}
              />
              <TextField
                label="정원 (본인 포함)"
                name="capacity"
                type="number"
                min={capacityMin}
                max={RECRUIT_CAPACITY_MAX}
                step={1}
                inputMode="numeric"
                required
                value={values.capacity}
                check={capacityCheck}
                onChange={(e) => edit('capacity', e.target.value)}
                disabled={pending}
              />
            </div>
            <JoinTypeField
              value={values.joinType}
              onChange={(joinType) => edit('joinType', joinType)}
              error={joinTypeError}
              disabled={pending}
            />
          </fieldset>
        )}

        <ImagesField
          images={values.images}
          onAdd={addImage}
          onRemove={removeImage}
          onBusyChange={setUploading}
          error={imagesError}
          disabled={pending}
        />

        {generalError && (
          <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
            {generalError}
          </p>
        )}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="secondary"
            onClick={() => navigate(editing ? `/posts/${editing.id}` : '/posts')}
            disabled={pending}
          >
            취소
          </Button>
          {/* 이 페이지의 유일한 primary CTA */}
          <Button type="submit" disabled={!canSubmit || pending}>
            {pending ? '저장 중…' : editing ? '저장' : isRecruit ? '모집 올리기' : '글 올리기'}
          </Button>
        </div>
      </form>
    </div>
  )
}

// --- 칩 라디오 (종류·참여 방식) — LogCreate 와 같은 규칙 ---
// 네이티브 radio 를 sr-only 로 두고 label 을 칩으로 그린다. 포커스 링은 label 에 peer 로 옮겨 그린다.

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
      <label htmlFor={id} className={`${CHIP} ${checked ? activeClass : CHIP_IDLE}`}>
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
  value: JoinType
  onChange: (value: JoinType) => void
  error?: string
  disabled?: boolean
}) {
  const errorId = 'join-type-error'
  return (
    <fieldset aria-describedby={error ? errorId : undefined}>
      <legend className="mb-1 block text-sm font-medium text-ink-500">참여 방식</legend>
      <div className="flex flex-wrap gap-2">
        {(['instant', 'approval'] as const).map((joinType) => (
          <Chip
            key={joinType}
            name="joinType"
            value={joinType}
            checked={value === joinType}
            onChange={() => onChange(joinType)}
            disabled={disabled}
            activeClass="border-ink-500 bg-chalk-200 font-medium text-ink-700"
          >
            {JOIN_TYPE_LABEL[joinType]}
          </Chip>
        ))}
      </div>
      <p className="mt-1 text-xs text-pretty text-ink-400">
        {value === 'instant'
          ? '신청하면 바로 확정되고, 정원이 차면 자동으로 마감돼요.'
          : '신청을 받은 뒤 내가 한 명씩 승인해요.'}
      </p>
      {error && (
        <p id={errorId} role="alert" className="mt-1 text-xs text-pretty text-danger-500">
          {error}
        </p>
      )}
    </fieldset>
  )
}

// --- 이미지 ---

/**
 * presigned 업로드로 최대 10장. 여러 장을 고르면 한 장씩 차례로 올린다 (useUpload 는 한 건 상태 머신).
 * 저장소가 설정되지 않은 서버(503 storage_not_configured)면 안내만 하고 이미지 없이 올릴 수 있게 둔다.
 */
function ImagesField({
  images,
  onAdd,
  onRemove,
  onBusyChange,
  error,
  disabled,
}: {
  images: string[]
  onAdd: (url: string) => void
  onRemove: (index: number) => void
  onBusyChange: (busy: boolean) => void
  error?: string
  disabled?: boolean
}) {
  const upload = useUpload('post_image', POST_IMAGE_TYPES)
  const inputRef = useRef<HTMLInputElement>(null)
  const [queue, setQueue] = useState<{ done: number; total: number } | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  const busy = upload.status === 'requesting' || upload.status === 'uploading'
  useEffect(() => onBusyChange(busy), [busy, onBusyChange])

  const storageUnavailable = upload.errorCode === 'storage_not_configured'
  const remaining = MAX_POST_IMAGES - images.length
  const errorId = 'images-error'
  const hintId = 'images-hint'

  const onPick = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setLocalError(null)
    const picked = Array.from(files)
    const accepted = picked.filter((file) => (POST_IMAGE_TYPES as readonly string[]).includes(file.type))
    const problems: string[] = []
    if (accepted.length < picked.length) problems.push('JPG, PNG, WebP 이미지만 올릴 수 있어요.')
    if (accepted.length > remaining) {
      problems.push(`이미지는 ${MAX_POST_IMAGES}장까지예요. 앞의 ${count.format(remaining)}장만 올려요.`)
    }
    if (problems.length > 0) setLocalError(problems.join(' '))

    const batch = accepted.slice(0, remaining)
    setQueue({ done: 0, total: batch.length })
    for (const [index, file] of batch.entries()) {
      const url = await upload.upload(file)
      if (!url) break // 실패·취소 — 메시지는 훅 상태에 있다
      onAdd(url)
      setQueue({ done: index + 1, total: batch.length })
    }
    setQueue(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const message = localError ?? (upload.status === 'error' && !storageUnavailable ? upload.error : null) ?? error

  return (
    <div>
      <p className="mb-1 text-sm font-medium text-ink-500">
        이미지 (선택){' '}
        <span className="font-normal text-ink-400 tabular-nums">
          {count.format(images.length)}/{MAX_POST_IMAGES}
        </span>
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={POST_IMAGE_TYPES.join(',')}
        multiple
        onChange={(e) => onPick(e.target.files)}
        disabled={disabled || busy || storageUnavailable || remaining <= 0}
        aria-describedby={message ? errorId : hintId}
        className="sr-only"
        tabIndex={-1}
      />

      {images.length > 0 && (
        <ul className="mb-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
          {images.map((url, index) => (
            <li key={`${index}-${url}`} className="relative aspect-square">
              <img
                src={url}
                alt={`첨부 이미지 ${index + 1}`}
                className="size-full rounded-xl bg-chalk-200 object-cover"
              />
              {/* 44px 터치 영역 안에 작은 원형 아이콘 */}
              <button
                type="button"
                aria-label={`이미지 ${index + 1} 제거`}
                onClick={() => onRemove(index)}
                disabled={disabled}
                className="absolute top-0 right-0 inline-flex size-11 items-center justify-center rounded-xl disabled:opacity-50"
              >
                <span
                  aria-hidden
                  className="inline-flex size-6 items-center justify-center rounded-full bg-ink-700/70 text-xs text-white transition-colors duration-150 hover:bg-ink-700"
                >
                  ✕
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {busy ? (
        <div className="rounded-xl border border-chalk-300 bg-chalk-50 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <p role="status" className="min-w-0 truncate text-sm text-ink-600">
              {upload.status === 'requesting'
                ? '업로드 준비 중…'
                : `올리는 중 ${percent.format(upload.progress)}`}
              {queue && queue.total > 1 && (
                <span className="ml-1 text-ink-400 tabular-nums">
                  ({count.format(queue.done + 1)}/{count.format(queue.total)})
                </span>
              )}
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
        <p role="status" id={hintId} className="rounded-xl bg-chalk-100 px-3 py-2 text-xs text-pretty text-ink-500">
          이미지 저장소가 아직 설정되지 않았어요. 지금은 이미지 없이 글을 올릴 수 있어요.
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            onClick={() => inputRef.current?.click()}
            disabled={disabled || remaining <= 0}
          >
            {images.length === 0 ? '이미지 선택' : '이미지 추가'}
          </Button>
          <span id={hintId} className="text-xs text-pretty text-ink-400">
            {remaining <= 0 ? '최대 장수예요' : 'JPG · PNG · WebP, 여러 장 가능'}
          </span>
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
