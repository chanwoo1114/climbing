/** 프로필 이미지가 없으면 닉네임 첫 글자. 기록 카드·댓글·프로필·회원 목록이 같이 쓴다 */
export interface AvatarUser {
  nickname: string
  image: string | null
}

type Size = 'sm' | 'md' | 'lg'

const SIZE: Record<Size, string> = {
  sm: 'size-8 text-xs',
  md: 'size-10 text-sm',
  lg: 'size-16 text-xl',
}

export default function Avatar({ user, size = 'md' }: { user: AvatarUser; size?: Size }) {
  if (user.image) {
    return (
      <img src={user.image} alt="" className={`${SIZE[size]} shrink-0 rounded-full object-cover`} />
    )
  }
  const initial = [...user.nickname][0]?.toUpperCase() ?? '?'
  return (
    <span
      aria-hidden
      className={`${SIZE[size]} inline-flex shrink-0 items-center justify-center rounded-full bg-chalk-200 font-semibold text-ink-500`}
    >
      {initial}
    </span>
  )
}
