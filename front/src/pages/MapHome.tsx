import { useGyms } from '@/hooks/useGyms'

// 서울시청 — 지오로케이션 연동 전 임시 기준점 (M1에서 MapLibre로 교체)
const DEFAULT_CENTER = { lat: 37.5663, lng: 126.9779 }

export default function MapHome() {
  const { data: gyms, isPending, isError } = useGyms(DEFAULT_CENTER)

  return (
    <section>
      <h1 className="mb-4 text-xl font-semibold text-ink-700">주변 클라이밍 암장</h1>

      {isPending && <p className="text-sm text-ink-400">불러오는 중…</p>}
      {isError && (
        <p className="text-sm text-danger-500">암장 목록을 불러오지 못했습니다.</p>
      )}

      <ul className="space-y-3">
        {gyms?.map((gym) => (
          <li
            key={gym.id}
            className="rounded-[14px] border border-chalk-300 bg-white p-4"
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-medium text-ink-700">{gym.name}</span>
              {gym.distanceM !== null && (
                <span className="shrink-0 text-xs text-slate-500">
                  {(gym.distanceM / 1000).toFixed(1)}km
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-ink-400">{gym.address}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
