import { Link } from 'react-router'

import type { UserSummary } from '@/api/users'
import Avatar from '@/components/common/Avatar'
import Button from '@/components/common/Button'
import { useMe } from '@/hooks/useAuth'
import { useToggleFollow } from '@/hooks/useUsers'

/** 팔로워·팔로잉·검색 결과가 같이 쓰는 회원 목록 */
export default function UserList({ users }: { users: UserSummary[] }) {
  const { data: me } = useMe()
  return (
    <ul className="space-y-2">
      {users.map((user) => (
        <UserListItem key={user.id} user={user} isMe={me?.id === user.id} />
      ))}
    </ul>
  )
}

function UserListItem({ user, isMe }: { user: UserSummary; isMe: boolean }) {
  const toggleFollow = useToggleFollow(user.id)
  return (
    <li className="flex items-center gap-3 rounded-card border border-chalk-300 bg-white p-3">
      <Link
        to={`/users/${user.id}`}
        className="-my-1 flex min-h-11 min-w-0 flex-1 items-center gap-3 rounded-xl"
      >
        <Avatar user={user} />
        <span className="truncate text-sm font-medium text-ink-700">{user.nickname}</span>
      </Link>
      {/* 목록 안의 팔로우는 보조 액션 — hold 배경(primary)은 프로필 페이지의 몫 */}
      {!isMe && (
        <Button
          variant="secondary"
          className="shrink-0 px-3 text-sm"
          onClick={() => toggleFollow.mutate(!user.isFollowing)}
        >
          {user.isFollowing ? '팔로잉' : '팔로우'}
        </Button>
      )}
    </li>
  )
}
