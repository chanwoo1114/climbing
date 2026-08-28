import { Link } from 'react-router'

import { getErrorMessage } from '@/api/client'
import Button from '@/components/common/Button'
import { useManagedGyms } from '@/hooks/useGyms'

/** 내가 관리하는 암장 (/gyms/managed) — 각 항목이 관리 화면으로 간다 */
export default function ManagedGyms() {
  const gyms = useManagedGyms()

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-4 text-2xl font-semibold text-ink-700">내 암장 관리</h1>

      {gyms.isPending && (
        <p role="status" className="py-10 text-center text-sm text-ink-400">
          불러오는 중…
        </p>
      )}

      {gyms.isError && (
        <div role="alert" className="py-10 text-center">
          <p className="text-sm text-pretty text-danger-500">
            {getErrorMessage(gyms.error, '관리하는 암장을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => gyms.refetch()}>
            다시 시도
          </Button>
        </div>
      )}

      {gyms.data && gyms.data.length === 0 && (
        <div role="status" className="rounded-card border border-chalk-300 bg-white p-8 text-center">
          <p className="text-sm font-medium text-ink-600">관리하는 암장이 없어요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">
            운영자에게 관리자 지정을 요청하세요.
          </p>
        </div>
      )}

      {gyms.data && gyms.data.length > 0 && (
        <ul className="space-y-3">
          {gyms.data.map((gym) => (
            <li key={gym.id}>
              <Link
                to={`/gyms/${gym.id}/manage`}
                className="flex items-center gap-3 rounded-card border border-chalk-300 bg-white p-4 transition-colors duration-150 hover:bg-chalk-50"
              >
                {gym.thumbnail ? (
                  <img
                    src={gym.thumbnail}
                    alt=""
                    loading="lazy"
                    className="size-14 shrink-0 rounded-xl object-cover"
                  />
                ) : (
                  <span
                    aria-hidden
                    className="inline-flex size-14 shrink-0 items-center justify-center rounded-xl bg-chalk-200 text-xl"
                  >
                    🧗
                  </span>
                )}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-base font-semibold text-ink-700">
                    {gym.name}
                  </span>
                  <span className="block text-sm text-pretty break-words text-ink-400">
                    {gym.address}
                  </span>
                </span>
                <span className="shrink-0 text-sm font-medium text-hold-600">관리</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
