import { useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { getErrorCode, getErrorMessage, getFieldError } from '@/api/client'
import {
  crewErrorMessage,
  isActiveStatus,
  isCrewFull,
  isManagerStatus,
  type Crew,
  type CrewMember,
} from '@/api/crews'
import LogList from '@/components/climbs/LogList'
import Avatar from '@/components/common/Avatar'
import Button from '@/components/common/Button'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import PostCard from '@/components/community/PostCard'
import {
  CrewImage,
  JoinTypeBadge,
  StatusBadge,
  count,
  memberCountText,
} from '@/components/crews/CrewBits'
import CrewStatsPanel from '@/components/crews/CrewStatsPanel'
import { useMe } from '@/hooks/useAuth'
import {
  useCrew,
  useCrewFeed,
  useCrewMembers,
  useCrewRecruitments,
  useJoinCrew,
  useKickCrewMember,
  useLeaveCrew,
  useSetCrewMemberRole,
  useSetCrewMemberStatus,
  useSetMainCrew,
  useTransferCrewOwner,
} from '@/hooks/useCrews'
import { useInfiniteSentinel } from '@/hooks/useInfiniteSentinel'
import { useToastStore } from '@/stores/toastStore'

type Tab = 'feed' | 'members' | 'recruitments' | 'stats'

const TABS: { value: Tab; label: string }[] = [
  { value: 'feed', label: '피드' },
  { value: 'members', label: '멤버' },
  { value: 'recruitments', label: '모집' },
  { value: 'stats', label: '통계' },
]

/** ?tab= 이 없거나 이상하면 피드 */
function tabFromParams(params: URLSearchParams): Tab {
  const value = params.get('tab')
  return value === 'members' || value === 'recruitments' || value === 'stats' ? value : 'feed'
}

// 글자가 작은 인라인 액션(운영진 지정·내보내기)도 44px 터치 영역
const TEXT_ACTION =
  'inline-flex min-h-11 items-center px-2 text-xs font-medium transition-colors duration-150'

// 링크를 secondary 버튼처럼 — 페이지 이동은 <a> 여야 한다
const LINK_BUTTON =
  'inline-flex min-h-11 items-center justify-center rounded-xl border border-chalk-300 bg-white px-4 text-sm font-medium text-ink-600 transition-colors duration-150 hover:bg-chalk-100'

const joinedDate = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium' })

export default function CrewDetail() {
  const { id } = useParams()
  const crewId = Number(id)
  const validId = Number.isInteger(crewId) && crewId > 0
  const { data: crew, isPending, isError, error, refetch } = useCrew(validId ? crewId : NaN)

  const code = isError ? getErrorCode(error) : undefined
  if (!validId || code === 'http_404' || code === 'not_found') {
    return <Blocked message="크루를 찾을 수 없어요. 삭제된 크루일 수 있어요." />
  }
  if (isPending) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (isError || !crew) {
    return (
      <div role="alert" className="py-10 text-center">
        <p className="text-sm text-pretty text-danger-500">
          {getErrorMessage(error, '크루를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
        <Button variant="secondary" className="mt-3" onClick={() => refetch()}>
          다시 시도
        </Button>
      </div>
    )
  }
  return <CrewDetailView crew={crew} />
}

function Blocked({ message }: { message: string }) {
  return (
    <div role="alert" className="py-10 text-center">
      <p className="text-sm text-pretty text-danger-500">{message}</p>
      <Link
        to="/crews"
        className="mt-2 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
      >
        크루 목록으로 돌아가기
      </Link>
    </div>
  )
}

function CrewDetailView({ crew }: { crew: Crew }) {
  const [searchParams] = useSearchParams()
  const tab = tabFromParams(searchParams)
  const { data: me } = useMe()
  const isMain = me?.mainCrew?.id === crew.id

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <Link
        to="/crews"
        className="-ml-2 inline-flex min-h-11 items-center px-2 text-sm font-medium text-ink-500 hover:text-ink-700"
      >
        <span aria-hidden className="mr-1">
          ←
        </span>
        크루
      </Link>

      <CrewHeader crew={crew} isMain={isMain} />

      {/* 탭 상태는 URL(?tab=)에 산다 — 새로고침·공유해도 같은 탭 */}
      <nav aria-label="크루 정보" className="inline-flex rounded-xl bg-chalk-200 p-1">
        {TABS.map((item) => {
          const active = item.value === tab
          return (
            <Link
              key={item.value}
              to={item.value === 'feed' ? `/crews/${crew.id}` : `/crews/${crew.id}?tab=${item.value}`}
              replace
              aria-current={active ? 'page' : undefined}
              className={`inline-flex min-h-11 items-center rounded-lg px-4 text-sm transition-colors duration-150 ${
                active
                  ? 'bg-white font-semibold text-ink-700'
                  : 'font-medium text-ink-500 hover:text-ink-700'
              }`}
            >
              {item.label}
            </Link>
          )
        })}
      </nav>

      {tab === 'feed' && <CrewFeed crew={crew} />}
      {tab === 'members' && <CrewMembers crew={crew} myId={me?.id ?? null} />}
      {tab === 'recruitments' && <CrewRecruitments crew={crew} />}
      {tab === 'stats' && <CrewStatsPanel crew={crew} myId={me?.id ?? null} />}
    </div>
  )
}

// --- 헤더 ---

function CrewHeader({ crew, isMain }: { crew: Crew; isMain: boolean }) {
  return (
    <section
      aria-labelledby="crew-heading"
      className="rounded-card border border-chalk-300 bg-white p-5"
    >
      <div className="flex items-start gap-4">
        <CrewImage crew={crew} size="lg" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 id="crew-heading" className="min-w-0 max-w-full truncate text-xl font-semibold text-ink-700">
              {crew.name}
            </h1>
            {crew.myStatus && <StatusBadge status={crew.myStatus} />}
            {isMain && (
              <span className="inline-flex shrink-0 items-center rounded-xl bg-hold-100 px-2 py-0.5 text-xs font-medium text-hold-600">
                대표 크루
              </span>
            )}
          </div>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-500">
            <span className="tabular-nums">
              크루원 <span className="font-semibold text-ink-700">{memberCountText(crew)}</span>
            </span>
            <JoinTypeBadge joinType={crew.joinType} />
            <span className="text-xs text-ink-400">
              {crew.isFeedPublic ? '피드 공개' : '피드는 크루원만'}
            </span>
          </p>
        </div>
      </div>

      {crew.description && (
        <p className="mt-4 text-sm leading-relaxed whitespace-pre-line text-pretty break-words text-ink-600">
          {crew.description}
        </p>
      )}

      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-ink-400">크루장</dt>
        <dd className="min-w-0">
          <Link
            to={`/users/${crew.owner.id}`}
            className="-my-2 inline-flex min-h-11 max-w-full items-center truncate font-medium text-ink-700 hover:underline"
          >
            {crew.owner.nickname}
          </Link>
        </dd>
        {crew.homeGym && (
          <>
            <dt className="text-ink-400">홈짐</dt>
            <dd className="min-w-0">
              <Link
                to={`/gyms/${crew.homeGym.id}`}
                className="-my-2 inline-flex min-h-11 max-w-full items-center truncate font-medium text-hold-600 hover:underline"
              >
                {crew.homeGym.name}
              </Link>
            </dd>
          </>
        )}
      </dl>

      <CrewActions crew={crew} isMain={isMain} />
    </section>
  )
}

/** 내 상태별 액션 — 가입/신청 취소/나가기/설정 + 채팅방·대표 크루 */
function CrewActions({ crew, isMain }: { crew: Crew; isMain: boolean }) {
  const join = useJoinCrew(crew.id)
  const leave = useLeaveCrew(crew.id)
  const setMain = useSetMainCrew()
  const [confirmLeave, setConfirmLeave] = useState(false)

  const status = crew.myStatus
  const active = isActiveStatus(status)
  const manager = isManagerStatus(status)
  const full = isCrewFull(crew)
  const busy = join.isPending || leave.isPending || setMain.isPending

  // 마지막으로 실패한 액션의 메시지만 보여준다
  const actionError =
    (join.isError && crewErrorMessage(join.error, '가입 신청을 하지 못했습니다.')) ||
    (leave.isError && crewErrorMessage(leave.error, '처리하지 못했습니다.')) ||
    (setMain.isError && crewErrorMessage(setMain.error, '대표 크루를 바꾸지 못했습니다.')) ||
    null

  return (
    <div className="mt-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {status === null ? (
          // 이 페이지의 유일한 primary CTA
          <Button onClick={() => join.mutate()} disabled={busy || full}>
            {join.isPending
              ? '신청하는 중…'
              : full
                ? '정원 마감'
                : crew.joinType === 'instant'
                  ? '가입하기'
                  : '가입 신청'}
          </Button>
        ) : status === 'pending' ? (
          <>
            <span role="status" className="text-sm font-medium text-ink-600">
              승인 대기중
            </span>
            <Button variant="secondary" onClick={() => leave.mutate()} disabled={busy}>
              {leave.isPending ? '취소하는 중…' : '신청 취소'}
            </Button>
          </>
        ) : status === 'owner' ? null : (
          <Button variant="secondary" onClick={() => setConfirmLeave(true)} disabled={busy}>
            나가기
          </Button>
        )}

        {manager && (
          <Link to={`/crews/${crew.id}/edit`} className={LINK_BUTTON}>
            크루 설정
          </Link>
        )}

        {active && !isMain && (
          <Button variant="secondary" onClick={() => setMain.mutate(crew.id)} disabled={busy}>
            {setMain.isPending ? '설정하는 중…' : '대표 크루로 설정'}
          </Button>
        )}

        {active && crew.chatRoomId !== null && (
          <Link
            to={`/chat/rooms/${crew.chatRoomId}`}
            className="inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
          >
            크루 채팅방
          </Link>
        )}

        {active && isMain && (
          <button
            type="button"
            onClick={() => setMain.mutate(null)}
            disabled={busy}
            className={`${TEXT_ACTION} text-sm text-ink-400 hover:text-ink-600 disabled:opacity-50`}
          >
            {setMain.isPending ? '해제하는 중…' : '대표 해제'}
          </button>
        )}
      </div>

      {status === null && full && (
        <p role="status" className="text-xs text-pretty text-ink-400">
          정원이 모두 차서 지금은 가입할 수 없어요.
        </p>
      )}

      {/* 크루장은 나갈 수 없다 (서버 owner_cannot_leave) — 멤버 탭의 위임 액션으로 안내 */}
      {status === 'owner' && (
        <p className="text-xs text-pretty text-ink-400">
          크루장을 위임한 뒤 나갈 수 있어요.{' '}
          <Link
            to={`/crews/${crew.id}?tab=members`}
            replace
            className="-my-2 inline-flex min-h-11 items-center font-medium text-hold-600 hover:underline"
          >
            크루장 위임하기
          </Link>
        </p>
      )}

      {actionError && (
        <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {actionError}
        </p>
      )}

      <ConfirmDialog
        open={confirmLeave}
        title="크루를 나갈까요?"
        description={
          isMain
            ? '크루 채팅방에서도 나가고 대표 크루 설정도 해제돼요. 다시 가입하려면 새로 신청해야 해요.'
            : '크루 채팅방에서도 나가요. 다시 가입하려면 새로 신청해야 해요.'
        }
        confirmLabel="나가기"
        pendingLabel="나가는 중…"
        pending={leave.isPending}
        onConfirm={() => leave.mutate(undefined, { onSuccess: () => setConfirmLeave(false) })}
        onCancel={() => setConfirmLeave(false)}
      />
    </div>
  )
}

// --- 피드 ---

function CrewFeed({ crew }: { crew: Crew }) {
  const feed = useCrewFeed(crew.id)

  if (feed.isError && getErrorCode(feed.error) === 'permission_denied') {
    return (
      <div role="status" className="rounded-card border border-chalk-300 bg-white p-8 text-center">
        <p className="text-sm font-medium text-ink-600">크루원만 볼 수 있어요</p>
        <p className="mt-1 text-xs text-pretty text-ink-400">
          {crew.myStatus === 'pending'
            ? '승인되면 크루원들의 기록을 볼 수 있어요.'
            : '가입하면 크루원들의 등반 기록을 모아 볼 수 있어요.'}
        </p>
      </div>
    )
  }
  return (
    <section aria-label="크루 피드">
      <LogList
        query={feed}
        errorMessage="크루 피드를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
        empty={
          <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
            <p className="text-sm font-medium text-ink-600">아직 크루원의 기록이 없어요</p>
            <p className="mt-1 text-xs text-pretty text-ink-400">
              크루원이 공개로 남긴 등반 기록이 여기에 모여요.
            </p>
            {isActiveStatus(crew.myStatus) && (
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
  )
}

// --- 멤버 ---

function CrewMembers({ crew, myId }: { crew: Crew; myId: number | null }) {
  const manager = isManagerStatus(crew.myStatus)
  const isOwner = crew.myStatus === 'owner'
  const members = useCrewMembers(crew.id, 'active')
  const rows = members.data?.pages.flatMap((page) => page.results) ?? []
  const sentinelRef = useInfiniteSentinel(members)

  const setRole = useSetCrewMemberRole(crew.id)
  const kick = useKickCrewMember(crew.id)
  const transfer = useTransferCrewOwner(crew.id)
  const pushToast = useToastStore((s) => s.push)
  const [pendingKick, setPendingKick] = useState<CrewMember | null>(null)
  const [pendingTransfer, setPendingTransfer] = useState<CrewMember | null>(null)
  const changingUserId = setRole.isPending ? setRole.variables?.userId : undefined

  const onKick = () => {
    if (!pendingKick) return
    kick.mutate(pendingKick.user.id, { onSuccess: () => setPendingKick(null) })
  }

  const onTransfer = () => {
    if (!pendingTransfer) return
    const { nickname } = pendingTransfer.user
    transfer.mutate(pendingTransfer.user.id, {
      onSuccess: () => {
        setPendingTransfer(null)
        pushToast({
          title: `${nickname}님이 새 크루장이 됐어요`,
          description: '회원님은 운영진으로 남아요.',
        })
      },
      // 대상이 이미 나갔거나 크루장인 경우(400 fields.user_id) — 모달을 닫고 목록 아래에 보여준다
      onError: () => setPendingTransfer(null),
    })
  }

  const transferError =
    transfer.isError &&
    (getFieldError(transfer.error, 'user_id') ??
      crewErrorMessage(transfer.error, '크루장을 위임하지 못했습니다. 잠시 후 다시 시도해 주세요.'))

  return (
    <div className="space-y-4">
      {manager && <PendingMembers crew={crew} />}

      <section
        aria-labelledby="members-heading"
        className="rounded-card border border-chalk-300 bg-white p-4 md:p-5"
      >
        <h2 id="members-heading" className="text-base font-semibold text-ink-700">
          크루원{' '}
          <span className="font-medium text-ink-400 tabular-nums">
            {count.format(crew.memberCount)}명
          </span>
        </h2>

        {members.isPending && (
          <p role="status" className="mt-3 text-sm text-ink-400">
            크루원을 불러오는 중…
          </p>
        )}
        {members.isError && (
          <div role="alert" className="mt-3">
            <p className="text-sm text-pretty text-danger-500">
              {getErrorMessage(members.error, '크루원 목록을 불러오지 못했습니다.')}
            </p>
            <Button variant="secondary" className="mt-2" onClick={() => members.refetch()}>
              다시 시도
            </Button>
          </div>
        )}
        {members.data && rows.length === 0 && (
          <p className="mt-3 text-sm text-pretty text-ink-400">아직 크루원이 없어요.</p>
        )}

        {rows.length > 0 && (
          <ul className="mt-2 divide-y divide-chalk-200">
            {rows.map((row) => {
              const isMe = row.user.id === myId
              // 크루장은 누구든 (본인 제외) 내보내고, 운영진은 크루원만 내보낼 수 있다
              const canKick =
                !isMe &&
                row.role !== 'owner' &&
                (isOwner || (crew.myStatus === 'staff' && row.role === 'member'))
              const canChangeRole = isOwner && !isMe && row.role !== 'owner'
              // 크루장 위임은 크루장만, 활동 중인 다른 크루원에게
              const canTransfer = isOwner && !isMe && row.role !== 'owner' && row.status === 'active'
              return (
                <li key={row.id} className="flex items-center gap-3 py-2">
                  <MemberRow member={row} isMe={isMe}>
                    {canTransfer && (
                      <button
                        type="button"
                        onClick={() => setPendingTransfer(row)}
                        disabled={transfer.isPending}
                        className={`${TEXT_ACTION} text-ink-400 hover:text-ink-600 disabled:opacity-50`}
                      >
                        크루장 위임
                      </button>
                    )}
                    {canChangeRole && (
                      <button
                        type="button"
                        onClick={() =>
                          setRole.mutate({
                            userId: row.user.id,
                            role: row.role === 'staff' ? 'member' : 'staff',
                          })
                        }
                        disabled={setRole.isPending}
                        className={`${TEXT_ACTION} text-ink-400 hover:text-ink-600 disabled:opacity-50`}
                      >
                        {changingUserId === row.user.id
                          ? '바꾸는 중…'
                          : row.role === 'staff'
                            ? '운영진 해제'
                            : '운영진 지정'}
                      </button>
                    )}
                    {canKick && (
                      <button
                        type="button"
                        onClick={() => setPendingKick(row)}
                        disabled={kick.isPending}
                        className={`${TEXT_ACTION} -mr-2 text-danger-500 hover:text-danger-600 disabled:opacity-50`}
                      >
                        내보내기
                      </button>
                    )}
                  </MemberRow>
                </li>
              )
            })}
          </ul>
        )}

        <div ref={sentinelRef} aria-hidden className="h-px" />
        {members.hasNextPage && (
          <Button
            variant="secondary"
            full
            className="mt-2"
            onClick={() => members.fetchNextPage()}
            disabled={members.isFetchingNextPage}
          >
            {members.isFetchingNextPage ? '불러오는 중…' : '크루원 더 보기'}
          </Button>
        )}

        {(setRole.isError || kick.isError) && (
          <p role="alert" className="mt-3 rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
            {crewErrorMessage(
              setRole.isError ? setRole.error : kick.error,
              '처리하지 못했습니다. 잠시 후 다시 시도해 주세요.',
            )}
          </p>
        )}
        {transferError && (
          <p role="alert" className="mt-3 rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
            {transferError}
          </p>
        )}
      </section>

      <ConfirmDialog
        open={pendingTransfer !== null}
        title={`${pendingTransfer?.user.nickname ?? ''}님에게 크루장을 넘길까요?`}
        description={`크루장을 ${pendingTransfer?.user.nickname ?? ''}님에게 넘깁니다. 회원님은 운영진이 됩니다.`}
        confirmLabel="위임하기"
        pendingLabel="위임하는 중…"
        variant="primary"
        pending={transfer.isPending}
        onConfirm={onTransfer}
        onCancel={() => setPendingTransfer(null)}
      />

      <ConfirmDialog
        open={pendingKick !== null}
        title={`${pendingKick?.user.nickname ?? ''}님을 내보낼까요?`}
        description="크루 채팅방에서도 나가게 돼요. 다시 들어오려면 새로 가입 신청해야 해요."
        confirmLabel="내보내기"
        pendingLabel="내보내는 중…"
        pending={kick.isPending}
        onConfirm={onKick}
        onCancel={() => setPendingKick(null)}
      />
    </div>
  )
}

/** 승인 대기 목록 — 크루장·운영진만 (부모가 걸러서 부른다) */
function PendingMembers({ crew }: { crew: Crew }) {
  const pending = useCrewMembers(crew.id, 'pending')
  const rows = pending.data?.pages.flatMap((page) => page.results) ?? []
  const setStatus = useSetCrewMemberStatus(crew.id)
  const decidingUserId = setStatus.isPending ? setStatus.variables?.userId : undefined
  const full = isCrewFull(crew)

  // 대기가 없으면 자리만 차지하니 조용히 숨긴다
  if (pending.data && rows.length === 0 && !setStatus.isError) return null

  return (
    <section
      aria-labelledby="pending-heading"
      className="rounded-card border border-chalk-300 bg-white p-4 md:p-5"
    >
      <h2 id="pending-heading" className="text-base font-semibold text-ink-700">
        가입 신청{' '}
        {pending.data && (
          <span className="font-medium text-ink-400 tabular-nums">{count.format(rows.length)}건</span>
        )}
      </h2>

      {pending.isPending && (
        <p role="status" className="mt-3 text-sm text-ink-400">
          신청을 불러오는 중…
        </p>
      )}
      {pending.isError && (
        <p role="alert" className="mt-3 text-sm text-pretty text-danger-500">
          {getErrorMessage(pending.error, '가입 신청 목록을 불러오지 못했습니다.')}
        </p>
      )}
      {full && rows.length > 0 && (
        <p role="status" className="mt-2 text-xs text-pretty text-ink-400">
          정원이 모두 차서 승인하려면 최대 인원을 늘려야 해요.
        </p>
      )}

      {rows.length > 0 && (
        <ul className="mt-2 divide-y divide-chalk-200">
          {rows.map((row) => (
            <li key={row.id} className="flex items-center gap-3 py-2">
              <MemberRow member={row} isMe={false} showRole={false}>
                <span className="flex shrink-0 items-center gap-1">
                  <Button
                    variant="secondary"
                    className="text-sm"
                    onClick={() => setStatus.mutate({ userId: row.user.id, status: 'active' })}
                    disabled={setStatus.isPending || full}
                  >
                    {decidingUserId === row.user.id ? '처리 중…' : '승인'}
                  </Button>
                  <Button
                    variant="secondary"
                    className="text-sm"
                    onClick={() => setStatus.mutate({ userId: row.user.id, status: 'rejected' })}
                    disabled={setStatus.isPending}
                  >
                    거절
                  </Button>
                </span>
              </MemberRow>
            </li>
          ))}
        </ul>
      )}

      {pending.hasNextPage && (
        <Button
          variant="secondary"
          full
          className="mt-2"
          onClick={() => pending.fetchNextPage()}
          disabled={pending.isFetchingNextPage}
        >
          {pending.isFetchingNextPage ? '불러오는 중…' : '신청 더 보기'}
        </Button>
      )}
      {setStatus.isError && (
        <p role="alert" className="mt-3 rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {crewErrorMessage(setStatus.error, '처리하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
      )}
    </section>
  )
}

function MemberRow({
  member,
  isMe,
  showRole = true,
  children,
}: {
  member: CrewMember
  isMe: boolean
  showRole?: boolean
  children?: ReactNode
}) {
  const { user } = member
  return (
    <>
      <Link to={`/users/${user.id}`} tabIndex={-1} className="-m-1.5 shrink-0 rounded-full p-1.5">
        <Avatar user={user} size="sm" />
      </Link>
      <div className="min-w-0 flex-1">
        <p className="flex min-w-0 items-center gap-2 text-sm font-medium text-ink-700">
          <Link to={`/users/${user.id}`} className="min-w-0 truncate hover:underline">
            {user.nickname}
          </Link>
          {isMe && <span className="shrink-0 text-xs font-normal text-ink-400">나</span>}
        </p>
        {member.joinedAt && (
          <p className="text-xs text-ink-400 tabular-nums">
            <time dateTime={member.joinedAt}>{joinedDate.format(new Date(member.joinedAt))}</time>{' '}
            가입
          </p>
        )}
      </div>
      {showRole && <StatusBadge status={member.role} />}
      {children}
    </>
  )
}

// --- 모집 ---

function CrewRecruitments({ crew }: { crew: Crew }) {
  const navigate = useNavigate()
  const posts = useCrewRecruitments(crew.id)
  const items = posts.data?.pages.flatMap((page) => page.results) ?? []
  const sentinelRef = useInfiniteSentinel(posts)
  const active = isActiveStatus(crew.myStatus)
  // PostCreate 가 ?crew= 를 읽어 크루 주최 모집으로 올린다
  const createPath = `/posts/new?category=recruit&crew=${crew.id}`

  return (
    <section aria-labelledby="recruitments-heading">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id="recruitments-heading" className="text-base font-semibold text-ink-700">
          크루 모집
        </h2>
        {active && (
          <Button variant="secondary" onClick={() => navigate(createPath)}>
            크루 모집 올리기
          </Button>
        )}
      </div>

      {posts.isPending && (
        <p role="status" className="py-10 text-center text-sm text-ink-400">
          모집글을 불러오는 중…
        </p>
      )}
      {posts.isError && (
        <div role="alert" className="py-10 text-center">
          <p className="text-sm text-pretty text-danger-500">
            {getErrorMessage(posts.error, '모집글을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => posts.refetch()}>
            다시 시도
          </Button>
        </div>
      )}
      {posts.data && items.length === 0 && (
        <div className="rounded-card border border-chalk-300 bg-white p-8 text-center">
          <p className="text-sm font-medium text-ink-600">크루에서 올린 모집이 아직 없어요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">
            {active
              ? '크루 이름으로 투어 모집을 올려 보세요.'
              : '크루원이 올린 투어 모집이 여기에 모여요.'}
          </p>
          {active && (
            <Link
              to={createPath}
              className="mt-3 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
            >
              첫 모집 올리기
            </Link>
          )}
        </div>
      )}

      {items.length > 0 && (
        <ul className="space-y-3">
          {items.map((post) => (
            <li key={post.id}>
              <PostCard post={post} />
            </li>
          ))}
        </ul>
      )}

      <div ref={sentinelRef} aria-hidden className="h-px" />
      {posts.hasNextPage && (
        <div className="mt-3">
          <Button
            variant="secondary"
            full
            onClick={() => posts.fetchNextPage()}
            disabled={posts.isFetchingNextPage}
          >
            {posts.isFetchingNextPage ? '불러오는 중…' : '더 보기'}
          </Button>
        </div>
      )}
      {posts.isFetchingNextPage && (
        <p role="status" className="sr-only">
          다음 모집글을 불러오는 중
        </p>
      )}
    </section>
  )
}
