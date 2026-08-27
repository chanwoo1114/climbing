import { Link, useParams } from 'react-router'

import { getErrorCode, getErrorMessage } from '@/api/client'
import Button from '@/components/common/Button'
import UserList from '@/components/users/UserList'
import { useFollowers, useFollowing, useUser } from '@/hooks/useUsers'

type Kind = 'followers' | 'following'

const COPY: Record<Kind, { title: string; empty: string }> = {
  followers: { title: '팔로워', empty: '아직 팔로워가 없어요' },
  following: { title: '팔로잉', empty: '아직 팔로우한 사람이 없어요' },
}

const count = new Intl.NumberFormat('ko-KR')

/** /users/:id/followers 와 /users/:id/following — 한 컴포넌트, kind 만 다르다 */
export default function UserFollowList({ kind }: { kind: Kind }) {
  const { id } = useParams()
  const userId = Number(id)
  const validId = Number.isInteger(userId) && userId > 0
  const safeId = validId ? userId : NaN

  const user = useUser(safeId)
  const followers = useFollowers(kind === 'followers' ? safeId : NaN)
  const following = useFollowing(kind === 'following' ? safeId : NaN)
  const list = kind === 'followers' ? followers : following
  const users = list.data?.pages.flatMap((page) => page.results) ?? []
  const copy = COPY[kind]

  if (!validId || (user.isError && getErrorCode(user.error) === 'http_404')) {
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

  const total =
    kind === 'followers' ? user.data?.followerCount : user.data?.followingCount

  return (
    <div className="mx-auto max-w-xl">
      <Link
        to={`/users/${userId}`}
        className="-ml-2 inline-flex min-h-11 items-center px-2 text-sm font-medium text-ink-500 hover:text-ink-700"
      >
        <span aria-hidden className="mr-1">
          ←
        </span>
        <span className="min-w-0 max-w-48 truncate">{user.data?.nickname ?? '프로필'}</span>
      </Link>
      <h1 className="mt-1 mb-4 text-2xl font-semibold text-ink-700">
        {copy.title}
        {total !== undefined && (
          <span className="ml-2 text-base font-medium text-ink-400 tabular-nums">
            {count.format(total)}
          </span>
        )}
      </h1>

      {list.isPending && (
        <p role="status" className="py-10 text-center text-sm text-ink-400">
          불러오는 중…
        </p>
      )}
      {list.isError && (
        <div role="alert" className="py-10 text-center">
          <p className="text-sm text-pretty text-danger-500">
            {getErrorMessage(list.error, '목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => list.refetch()}>
            다시 시도
          </Button>
        </div>
      )}
      {list.data && users.length === 0 && (
        <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
          <p className="text-sm font-medium text-ink-600">{copy.empty}</p>
        </div>
      )}
      {users.length > 0 && <UserList users={users} />}

      {list.hasNextPage && (
        <div className="mt-3">
          <Button
            variant="secondary"
            full
            onClick={() => list.fetchNextPage()}
            disabled={list.isFetchingNextPage}
          >
            {list.isFetchingNextPage ? '불러오는 중…' : '더 보기'}
          </Button>
        </div>
      )}
    </div>
  )
}
