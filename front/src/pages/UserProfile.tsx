import { Link, useParams } from 'react-router'

import { getErrorCode, getErrorMessage } from '@/api/client'
import type { UserProfile as Profile } from '@/api/users'
import LogList from '@/components/climbs/LogList'
import Avatar from '@/components/common/Avatar'
import Button from '@/components/common/Button'
import { useOpenDirectRoom } from '@/hooks/useChat'
import { useToggleFollow, useUser, useUserLogs } from '@/hooks/useUsers'

const count = new Intl.NumberFormat('ko-KR')
const joinedAt = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long' })

// 글자가 작은 메타 링크(팔로워·팔로잉·홈짐)도 44px 터치 영역
const META_LINK = '-my-2 -mx-1 inline-flex min-h-11 items-center px-1 hover:underline'

export default function UserProfile() {
  const { id } = useParams()
  const userId = Number(id)
  const validId = Number.isInteger(userId) && userId > 0
  const { data: user, isPending, isError, error, refetch } = useUser(validId ? userId : NaN)

  if (!validId || (isError && getErrorCode(error) === 'http_404')) {
    return (
      <div role="alert" className="py-10 text-center">
        <p className="text-sm text-danger-500">존재하지 않는 회원이에요</p>
        <Link
          to="/feed"
          className="mt-2 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
        >
          피드로 돌아가기
        </Link>
      </div>
    )
  }
  if (isPending) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (isError || !user) {
    return (
      <div role="alert" className="py-10 text-center">
        <p className="text-sm text-pretty text-danger-500">
          {getErrorMessage(error, '프로필을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
        <Button variant="secondary" className="mt-3" onClick={() => refetch()}>
          다시 시도
        </Button>
      </div>
    )
  }
  return <ProfileView user={user} />
}

function ProfileView({ user }: { user: Profile }) {
  const logs = useUserLogs(user.id)

  return (
    <div className="mx-auto max-w-xl">
      <ProfileHeader user={user} />

      <section aria-labelledby="logs-heading" className="mt-6">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 id="logs-heading" className="text-base font-semibold text-ink-700">
            기록
          </h2>
          {user.isMe && (
            // 성공/실패 필터가 있는 내 기록 페이지
            <Link
              to="/logs"
              className="-mr-2 inline-flex min-h-11 items-center px-2 text-sm font-medium text-hold-600 hover:underline"
            >
              필터로 보기
            </Link>
          )}
        </div>
        <LogList
          query={logs}
          errorMessage="기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
          empty={
            <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
              <p className="text-sm font-medium text-ink-600">아직 기록이 없어요</p>
              {user.isMe && (
                <Link
                  to="/logs/new"
                  className="mt-3 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
                >
                  첫 기록 남기기
                </Link>
              )}
            </div>
          }
        />
      </section>
    </div>
  )
}

function ProfileHeader({ user }: { user: Profile }) {
  const toggleFollow = useToggleFollow(user.id)
  const openDirectRoom = useOpenDirectRoom(user.id)

  return (
    <section
      aria-labelledby="profile-heading"
      className="rounded-card border border-chalk-300 bg-white p-5"
    >
      <div className="flex items-center gap-4">
        <Avatar user={user} size="lg" />
        <div className="min-w-0 flex-1">
          <h1 id="profile-heading" className="truncate text-xl font-semibold text-ink-700">
            {user.nickname}
          </h1>
          <p className="mt-0.5 text-xs text-ink-400">
            <time dateTime={user.createdAt}>{joinedAt.format(new Date(user.createdAt))}</time>{' '}
            가입
          </p>
          {user.mainCrew && (
            // 대표 크루 — 크루 상세에서 고른다 (활동 중인 크루만)
            <Link
              to={`/crews/${user.mainCrew.id}`}
              className="-ml-1 mt-1 inline-flex min-h-11 max-w-full items-center gap-1 px-1 text-xs font-medium text-ink-600 hover:underline"
            >
              <span className="sr-only">대표 크루 </span>
              <span aria-hidden className="shrink-0 rounded-xl bg-hold-100 px-1.5 py-0.5 text-hold-600">
                크루
              </span>
              <span className="min-w-0 truncate">{user.mainCrew.name}</span>
            </Link>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {!user.isMe && (
            // 1:1 방을 찾거나 만들고 그 방으로 이동
            <Button
              variant="secondary"
              onClick={() => openDirectRoom.mutate()}
              disabled={openDirectRoom.isPending}
              className="text-sm"
            >
              {openDirectRoom.isPending ? '여는 중…' : '메시지'}
            </Button>
          )}
          {user.isMe ? (
            <Link
              to="/profile"
              className="inline-flex min-h-11 items-center justify-center rounded-xl border border-chalk-300 bg-white px-4 text-sm font-medium text-ink-600 transition-colors duration-150 hover:bg-chalk-100"
            >
              프로필 수정
            </Link>
          ) : user.isFollowing ? (
            <Button
              variant="secondary"
              onClick={() => toggleFollow.mutate(false)}
              className="text-sm"
            >
              팔로잉
            </Button>
          ) : (
            // 이 페이지의 유일한 primary CTA
            <Button onClick={() => toggleFollow.mutate(true)} className="text-sm">
              팔로우
            </Button>
          )}
        </div>
      </div>

      <p className="mt-4 flex flex-wrap items-center gap-x-2 text-sm text-ink-500">
        <Link to={`/users/${user.id}/followers`} className={META_LINK}>
          팔로워{' '}
          <span className="ml-1 font-semibold text-ink-700 tabular-nums">
            {count.format(user.followerCount)}
          </span>
        </Link>
        <span aria-hidden>·</span>
        <Link to={`/users/${user.id}/following`} className={META_LINK}>
          팔로잉{' '}
          <span className="ml-1 font-semibold text-ink-700 tabular-nums">
            {count.format(user.followingCount)}
          </span>
        </Link>
        {user.homeGym && (
          <>
            <span aria-hidden>·</span>
            <Link
              to={`/gyms/${user.homeGym.id}`}
              className={`${META_LINK} min-w-0 max-w-full font-medium text-hold-600`}
            >
              <span className="sr-only">홈짐 </span>
              <span aria-hidden className="mr-1">
                🏠
              </span>
              <span className="truncate">{user.homeGym.name}</span>
            </Link>
          </>
        )}
      </p>

      {user.bio && (
        <p className="mt-3 text-sm whitespace-pre-line text-pretty break-words text-ink-600">
          {user.bio}
        </p>
      )}

      {(toggleFollow.isError || openDirectRoom.isError) && (
        <p role="alert" className="mt-3 rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {getErrorMessage(
            toggleFollow.isError ? toggleFollow.error : openDirectRoom.error,
            '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.',
          )}
        </p>
      )}
    </section>
  )
}
