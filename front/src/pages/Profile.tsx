import { useEffect, useMemo, useState, type FormEvent } from 'react'

import type { Me, MeUpdate } from '@/api/auth'
import { getFieldError } from '@/api/client'
import Button from '@/components/common/Button'
import SelectField from '@/components/common/SelectField'
import TextArea from '@/components/common/TextArea'
import TextField from '@/components/common/TextField'
import { useMe, useUpdateMe } from '@/hooks/useAuth'
import { useGyms } from '@/hooks/useGyms'
import { checkNickname, type FieldCheck } from '@/lib/validation'

/** 소개글 길이 상한 — 서버 TextField 는 제한이 없어 화면에서만 막는다 */
export const BIO_MAX_LENGTH = 200

const IDLE: FieldCheck = { state: 'idle', message: '' }
const joinedAt = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'long' })

export default function Profile() {
  const { data: me, isPending, isError } = useMe()

  if (isPending) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (isError || !me) {
    return (
      <p role="alert" className="py-10 text-center text-sm text-danger-500">
        프로필을 불러오지 못했습니다. 잠시 후 새로고침해 주세요.
      </p>
    )
  }
  // 폼 초기값은 me 가 준비된 뒤에 잡아야 해서 컴포넌트를 나눈다
  return <ProfileForm me={me} />
}

const toSelectValue = (gymId: number | null) => (gymId === null ? '' : String(gymId))

function ProfileForm({ me }: { me: Me }) {
  const updateMutation = useUpdateMe()
  // 홈짐 후보 — 지도 검색 전까지는 전체 목록에서 고른다
  const gyms = useGyms()

  const [nickname, setNickname] = useState(me.nickname)
  const [bio, setBio] = useState(me.bio)
  const [homeGym, setHomeGym] = useState(toSelectValue(me.homeGym))
  const [saved, setSaved] = useState(false)

  // 저장 직후 서버값이 캐시에 반영되면 폼 기준값도 따라간다
  useEffect(() => {
    setNickname(me.nickname)
    setBio(me.bio)
    setHomeGym(toSelectValue(me.homeGym))
  }, [me.nickname, me.bio, me.homeGym])

  const error = updateMutation.error
  const withServerError = (check: FieldCheck, field: string): FieldCheck => {
    const serverMessage = getFieldError(error, field)
    return serverMessage ? { state: 'invalid', message: serverMessage } : check
  }
  // 자기 닉네임 그대로면 "사용 가능" 메시지를 띄우지 않는다
  const nicknameCheck = withServerError(
    nickname === me.nickname ? IDLE : checkNickname(nickname),
    'nickname',
  )
  const bioCheck = withServerError(IDLE, 'bio')
  const homeGymError = getFieldError(error, 'home_gym')

  // 바뀐 필드만 PATCH 한다
  const changes = useMemo(() => {
    const diff: MeUpdate = {}
    const homeGymId = homeGym === '' ? null : Number(homeGym)
    if (nickname !== me.nickname) diff.nickname = nickname
    if (bio !== me.bio) diff.bio = bio
    if (homeGymId !== me.homeGym) diff.homeGym = homeGymId
    return diff
  }, [nickname, bio, homeGym, me])
  const dirty = Object.keys(changes).length > 0

  const canSubmit =
    dirty &&
    (nickname === me.nickname || checkNickname(nickname).state === 'valid') &&
    bio.length <= BIO_MAX_LENGTH
  const pending = updateMutation.isPending

  // 입력을 고치기 시작하면 이전 서버 오류와 "저장했습니다" 를 지운다
  const edit =
    (setter: (value: string) => void) => (e: { target: { value: string } }) => {
      if (updateMutation.isError) updateMutation.reset()
      setSaved(false)
      setter(e.target.value)
    }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || pending) return
    updateMutation.mutate(changes, { onSuccess: () => setSaved(true) })
  }

  const gymOptions = useMemo(() => {
    const options = (gyms.data ?? []).map((gym) => ({
      value: String(gym.id),
      label: gym.name,
    }))
    // 목록에 아직 없는(로딩 전 등) 현재 홈짐은 이름으로라도 보여준다
    if (homeGym && !options.some((option) => option.value === homeGym)) {
      options.unshift({ value: homeGym, label: me.homeGymName ?? `암장 #${homeGym}` })
    }
    return options
  }, [gyms.data, homeGym, me.homeGymName])

  // 필드별로 표시된 오류는 아래 공통 배너에서 중복 노출하지 않는다
  const generalError =
    error &&
    !getFieldError(error, 'nickname') &&
    !getFieldError(error, 'bio') &&
    !homeGymError
      ? error.message
      : null

  return (
    <div className="mx-auto mt-4 max-w-sm md:mt-10">
      <h1 className="mb-6 text-2xl font-semibold text-ink-700">내 프로필</h1>
      <form
        onSubmit={onSubmit}
        noValidate
        className="space-y-4 rounded-card border border-chalk-300 bg-white p-6"
      >
        <TextField
          label="이메일"
          name="email"
          type="email"
          value={me.email}
          readOnly
          disabled
        />
        <TextField
          label="닉네임"
          name="nickname"
          autoComplete="nickname"
          spellCheck={false}
          required
          maxLength={30}
          value={nickname}
          check={nicknameCheck}
          onChange={edit(setNickname)}
        />
        <TextArea
          label="소개"
          name="bio"
          placeholder="주로 하는 종목, 목표 난이도 같은 걸 적어 보세요"
          maxLength={BIO_MAX_LENGTH}
          showCount
          value={bio}
          check={bioCheck}
          onChange={edit(setBio)}
        />
        <SelectField
          label="홈짐"
          name="homeGym"
          placeholder="선택 안 함"
          hint="주로 다니는 암장 — 기록 작성 시 기본값으로 쓰입니다"
          options={gymOptions}
          value={homeGym}
          disabled={gyms.isPending}
          error={homeGymError}
          onChange={edit(setHomeGym)}
        />

        {generalError && (
          <p
            role="alert"
            className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600"
          >
            {generalError}
          </p>
        )}
        {saved && !dirty && (
          <p role="status" className="text-sm text-moss-500">
            저장했습니다.
          </p>
        )}

        <Button type="submit" full disabled={!canSubmit || pending}>
          {pending ? '저장 중…' : '저장'}
        </Button>
      </form>
      <p className="mt-4 text-center text-xs text-ink-400">
        {joinedAt.format(new Date(me.createdAt))} 가입
      </p>
    </div>
  )
}
