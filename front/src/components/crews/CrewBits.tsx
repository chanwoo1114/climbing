import {
  CREW_JOIN_TYPE_LABEL,
  CREW_MY_STATUS_LABEL,
  type CrewJoinType,
  type CrewMyStatus,
  type CrewSummary,
} from '@/api/crews'

/** 크루 공용 조각 — 대표 이미지·배지·인원 표기. CrewCard/CrewList/CrewDetail 이 같이 쓴다 */

export const count = new Intl.NumberFormat('ko-KR')

/** 성공률(0~100) — 소수 1자리까지. "%" 는 호출부가 붙인다 */
export const percent = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 })

/** 순위 배지 — 1~3위는 ochre 로 살짝 띄우고 나머지는 중립. 동점은 같은 숫자가 나란히 온다 */
export function RankBadge({ rank }: { rank: number }) {
  const top = rank <= 3
  return (
    <span
      className={`inline-flex size-7 shrink-0 items-center justify-center rounded-lg text-xs font-semibold tabular-nums ${
        top ? 'bg-ochre-100 text-ochre-500' : 'bg-chalk-200 text-ink-500'
      }`}
    >
      <span className="sr-only">{count.format(rank)}위</span>
      <span aria-hidden>{count.format(rank)}</span>
    </span>
  )
}

/** "12/30명" — 활동 중인 크루원(크루장 포함) / 최대 인원 */
export const memberCountText = (crew: Pick<CrewSummary, 'memberCount' | 'maxMembers'>) =>
  `${count.format(crew.memberCount)}/${count.format(crew.maxMembers)}명`

type Size = 'sm' | 'md' | 'lg'

const SIZE: Record<Size, string> = {
  sm: 'size-10 text-sm',
  md: 'size-14 text-lg',
  lg: 'size-20 text-2xl',
}

/** 대표 이미지가 없으면 이름 첫 글자. 사람(Avatar, 원형)과 구분되게 모서리만 둥근 사각형 */
export function CrewImage({
  crew,
  size = 'md',
}: {
  crew: Pick<CrewSummary, 'name' | 'image'>
  size?: Size
}) {
  if (crew.image) {
    return (
      <img src={crew.image} alt="" className={`${SIZE[size]} shrink-0 rounded-xl object-cover`} />
    )
  }
  const initial = [...crew.name][0]?.toUpperCase() ?? '?'
  return (
    <span
      aria-hidden
      className={`${SIZE[size]} inline-flex shrink-0 items-center justify-center rounded-xl bg-chalk-200 font-semibold text-ink-500`}
    >
      {initial}
    </span>
  )
}

const BADGE = 'inline-flex shrink-0 items-center rounded-xl px-2 py-0.5 text-xs font-medium'

// 크루장 = ochre(포인트), 운영진 = slate(정보), 크루원 = moss(소속 확정), 대기 = 중립
const STATUS_CLASS: Record<CrewMyStatus, string> = {
  owner: 'bg-ochre-100 text-ochre-500',
  staff: 'bg-slate-100 text-slate-500',
  member: 'bg-moss-100 text-moss-500',
  pending: 'bg-chalk-200 text-ink-500',
}

/** 내 상태(목록·상세) 와 크루원 역할(멤버 목록) 둘 다 이 배지로 그린다 */
export function StatusBadge({ status }: { status: CrewMyStatus }) {
  return <span className={`${BADGE} ${STATUS_CLASS[status]}`}>{CREW_MY_STATUS_LABEL[status]}</span>
}

// 가입 방식은 정보 성격 — 즉시 가입은 중립, 승인제는 slate
const JOIN_TYPE_CLASS: Record<CrewJoinType, string> = {
  instant: 'bg-chalk-200 text-ink-500',
  approval: 'bg-slate-100 text-slate-500',
}

export function JoinTypeBadge({ joinType }: { joinType: CrewJoinType }) {
  return (
    <span className={`${BADGE} ${JOIN_TYPE_CLASS[joinType]}`}>{CREW_JOIN_TYPE_LABEL[joinType]}</span>
  )
}
