import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import type { ClimbBeta } from '@/api/betas'
import { getErrorCode, getErrorMessage } from '@/api/client'
import { DifficultyPill } from '@/components/betas/BetaCard'
import { formatRelativeDate } from '@/components/climbs/LogCard'
import Avatar from '@/components/common/Avatar'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import { useMe } from '@/hooks/useAuth'
import { useBeta, useDeleteBeta } from '@/hooks/useBetas'
import { useToastStore } from '@/stores/toastStore'

const count = new Intl.NumberFormat('ko-KR')

// 글자가 작은 인라인 액션(수정·삭제)도 44px 터치 영역
const TEXT_ACTION =
  'inline-flex min-h-11 items-center px-2 text-sm font-medium transition-colors duration-150'

/** /betas/:betaId — 읽기는 공개. 수정·삭제는 올린 사람에게만 보인다 */
export default function BetaDetail() {
  const { betaId } = useParams()
  const id = Number(betaId)
  const validId = Number.isInteger(id) && id > 0
  const { data: beta, isPending, isError, error } = useBeta(validId ? id : NaN)

  if (!validId || (isError && getErrorCode(error) === 'http_404')) {
    return <NotFound message="베타 영상을 찾을 수 없어요. 삭제됐을 수 있어요." />
  }
  if (isPending) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (isError || !beta) {
    return <NotFound message="베타 영상을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." />
  }
  return <BetaDetailView beta={beta} />
}

function NotFound({ message }: { message: string }) {
  return (
    <div role="alert" className="py-10 text-center">
      <p className="text-sm text-pretty text-danger-500">{message}</p>
      <Link
        to="/"
        className="mt-2 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
      >
        지도로 돌아가기
      </Link>
    </div>
  )
}

function BetaDetailView({ beta }: { beta: ClimbBeta }) {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const push = useToastStore((s) => s.push)
  const remove = useDeleteBeta()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const isOwner = beta.isMine || (me !== undefined && me.id === beta.user.id)
  const gymBetasPath = `/gyms/${beta.gym.id}?tab=betas`

  const onDelete = () => {
    remove.mutate(
      { id: beta.id, gymId: beta.gym.id },
      {
        onSuccess: () => {
          push({ title: '베타 영상을 삭제했어요.' })
          navigate(gymBetasPath, { replace: true })
        },
      },
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Link
          to={gymBetasPath}
          className="-ml-2 inline-flex min-h-11 min-w-0 items-center px-2 text-sm font-medium text-ink-500 hover:text-ink-700"
        >
          <span aria-hidden className="mr-1 shrink-0">
            ←
          </span>
          <span className="truncate">{beta.gym.name} 베타</span>
        </Link>
        {isOwner && (
          <div className="flex shrink-0 items-center gap-1">
            <Link
              to={`/betas/${beta.id}/edit`}
              className={`${TEXT_ACTION} text-ink-500 hover:text-ink-700`}
            >
              수정
            </Link>
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className={`${TEXT_ACTION} -mr-2 text-danger-500 hover:text-danger-600`}
            >
              삭제
            </button>
          </div>
        )}
      </div>

      <article className="overflow-hidden rounded-card border border-chalk-300 bg-white">
        <video
          controls
          playsInline
          preload="metadata"
          src={beta.videoUrl}
          poster={beta.thumbnailUrl || undefined}
          aria-label={`${beta.title} 베타 영상`}
          className="aspect-video w-full bg-ink-700"
        />

        <div className="space-y-4 p-4 md:p-5">
          <header>
            <h1 className="text-xl font-semibold break-words text-ink-700">{beta.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
              <Link
                to={gymBetasPath}
                className="-my-2 inline-flex min-h-11 max-w-full items-center truncate font-medium text-hold-600 hover:underline"
              >
                {beta.gym.name}
              </Link>
              {beta.difficulty && <DifficultyPill difficulty={beta.difficulty} />}
              {beta.sector && (
                <span className="min-w-0 truncate text-ink-600">{beta.sector}</span>
              )}
            </div>
            <p className="mt-1 flex flex-wrap gap-x-2 text-xs text-ink-400 tabular-nums">
              <span>조회 {count.format(beta.viewCount)}</span>
              <span aria-hidden>·</span>
              <time dateTime={beta.createdAt}>{formatRelativeDate(beta.createdAt)}</time>
            </p>
          </header>

          <div className="flex items-center gap-3">
            {/* 아바타는 닉네임 링크와 같은 곳으로 가는 44px 터치 영역 — 키보드 탭 순서에선 닉네임만 */}
            <Link
              to={`/users/${beta.user.id}`}
              tabIndex={-1}
              className="-m-0.5 shrink-0 rounded-full p-0.5"
            >
              <Avatar user={beta.user} />
            </Link>
            <p className="min-w-0 flex-1 truncate text-sm font-medium text-ink-700">
              <Link to={`/users/${beta.user.id}`} className="hover:underline">
                {beta.user.nickname}
              </Link>
            </p>
          </div>

          {beta.description && (
            <p className="text-sm whitespace-pre-line text-pretty break-words text-ink-600">
              {beta.description}
            </p>
          )}

          {beta.climbLogId !== null && (
            <Link
              to={`/logs/${beta.climbLogId}`}
              className="-mx-1 inline-flex min-h-11 items-center px-1 text-sm font-medium text-hold-600 hover:underline"
            >
              연결된 기록 보기
              <span aria-hidden className="ml-1">
                →
              </span>
            </Link>
          )}
        </div>
      </article>

      {remove.isError && (
        <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {getErrorMessage(remove.error, '베타 영상을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </p>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title="이 베타 영상을 삭제할까요?"
        description="삭제한 영상은 되돌릴 수 없어요."
        confirmLabel="삭제"
        pendingLabel="삭제 중…"
        pending={remove.isPending}
        onConfirm={onDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  )
}
