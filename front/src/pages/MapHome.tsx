import { useGyms } from '@/hooks/useGyms'

// 서울시청 — 지오로케이션 연동 전 임시 기준점 (M1에서 MapLibre로 교체)
const DEFAULT_CENTER = { lat: 37.5663, lng: 126.9779 }

// 하드코딩 포맷 대신 로케일 포맷 (1.2km / 850m)
const km = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 })
const formatDistance = (meters: number) =>
  meters < 1000 ? `${Math.round(meters)}m` : `${km.format(meters / 1000)}km`

export default function MapHome() {
  const { data: gyms, isPending, isError } = useGyms(DEFAULT_CENTER)

  return (
    <section>
      <h1 className="mb-4 text-xl font-semibold text-ink-700">주변 클라이밍 암장</h1>

      {isPending && (
        <p role="status" className="text-sm text-ink-400">
          불러오는 중…
        </p>
      )}
      {isError && (
        <p role="alert" className="text-sm text-danger-500">
          암장 목록을 불러오지 못했습니다. 잠시 후 새로고침해 주세요.
        </p>
      )}
      {gyms && gyms.length === 0 && (
        <div className="rounded-card border border-chalk-300 bg-white p-6 text-center">
          <p className="text-sm font-medium text-ink-600">아직 등록된 암장이 없어요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">
            암장 데이터가 들어오면 여기에 거리순으로 표시됩니다.
          </p>
        </div>
      )}

      <ul className="space-y-3">
        {gyms?.map((gym) => (
          <li key={gym.id} className="rounded-card border border-chalk-300 bg-white p-4">
            <div className="flex items-baseline justify-between gap-2">
              {/* 긴 상호명은 잘라내고, 거리는 자릿수가 바뀌어도 폭이 흔들리지 않게 */}
              <span className="min-w-0 truncate font-medium text-ink-700">{gym.name}</span>
              {gym.distanceM !== null && (
                <span className="shrink-0 text-xs text-slate-500 tabular-nums">
                  {formatDistance(gym.distanceM)}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-pretty break-words text-ink-400">{gym.address}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
