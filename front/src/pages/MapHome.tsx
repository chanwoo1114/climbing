import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'

import type { GymSummary } from '@/api/gyms'
import Button from '@/components/common/Button'
import GymMap, { type Viewport, type ViewportBox } from '@/components/map/GymMap'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useGyms } from '@/hooks/useGyms'

// 서울시청 — 위치 권한이 없을 때의 기본 시작점
const DEFAULT_VIEWPORT: Viewport = { lat: 37.5663, lng: 126.9779, zoom: 12 }
/** 백엔드 GymListView.MAX_MAP_RESULTS 와 같다 — 꽉 차면 "더 있을 수 있음" 안내 */
const MAX_RESULTS = 100

// 하드코딩 포맷 대신 로케일 포맷 (1.2km / 850m)
const km = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 })
const count = new Intl.NumberFormat('ko-KR')
const formatDistance = (meters: number) =>
  meters < 1000 ? `${Math.round(meters)}m` : `${km.format(meters / 1000)}km`

/** URL ?lat=&lng=&z= → 뷰포트. 하나라도 이상하면 기본값 */
function viewportFromParams(params: URLSearchParams): Viewport | null {
  const lat = Number(params.get('lat'))
  const lng = Number(params.get('lng'))
  const zoom = Number(params.get('z'))
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || !Number.isFinite(zoom)) return null
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180 || zoom < 1 || zoom > 20) return null
  return { lat, lng, zoom }
}

export default function MapHome() {
  const [searchParams, setSearchParams] = useSearchParams()
  // 최초 1회만 URL 에서 읽는다 — 이후엔 지도가 URL 을 갱신한다
  const [initialViewport] = useState<Viewport>(
    () => viewportFromParams(searchParams) ?? DEFAULT_VIEWPORT,
  )
  const startedFromUrl = useRef(viewportFromParams(searchParams) !== null)

  const [viewport, setViewport] = useState<ViewportBox | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [flyTo, setFlyTo] = useState<{ lat: number; lng: number; zoom?: number; key: number } | null>(
    null,
  )
  const geo = useGeolocation()

  const onViewportChange = useCallback(
    (next: ViewportBox) => {
      setViewport(next)
      setSearchParams(
        { lat: String(next.lat), lng: String(next.lng), z: String(next.zoom) },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  // 거리 기준: 내 위치를 알면 내 위치, 모르면 지도 중심
  const origin = geo.position ?? (viewport ? { lat: viewport.lat, lng: viewport.lng } : null)
  const params = useMemo(
    () => (viewport && origin ? { bbox: viewport.bbox, lat: origin.lat, lng: origin.lng } : {}),
    [viewport, origin],
  )
  const { data, isPending, isError, isFetching } = useGyms(params, viewport !== null)
  const gyms = data ?? []

  // 위치를 받으면 그리로 이동한다. 단, URL 로 특정 지점에 들어왔고 사용자가 직접
  // 누른 게 아니면(권한이 이미 있어 자동으로 읽힌 경우) 그 지점을 유지한다.
  const prevPosition = useRef<typeof geo.position>(null)
  const userRequested = useRef(false)
  useEffect(() => {
    if (!geo.position || geo.position === prevPosition.current) return
    const first = prevPosition.current === null
    prevPosition.current = geo.position
    if (first && startedFromUrl.current && !userRequested.current) return
    setFlyTo({ ...geo.position, zoom: first && !userRequested.current ? 13 : 14, key: Date.now() })
  }, [geo.position])

  const goToMyLocation = () => {
    userRequested.current = true
    if (geo.position) setFlyTo({ ...geo.position, zoom: 14, key: Date.now() })
    else geo.locate()
  }

  // 마커로 고른 암장은 목록에서도 보이게 스크롤
  const itemRefs = useRef(new Map<number, HTMLLIElement>())
  useEffect(() => {
    if (selectedId === null) return
    itemRefs.current.get(selectedId)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selectedId])

  const selectFromList = (gym: GymSummary) => {
    setSelectedId(gym.id)
    setFlyTo({ lat: gym.lat, lng: gym.lng, key: Date.now() })
  }

  const locating = geo.status === 'locating'

  return (
    <section className="md:grid md:grid-cols-[minmax(0,1fr)_360px] md:gap-4">
      <div className="relative">
        <GymMap
          className="h-[48vh] min-h-72 md:h-[calc(100vh-8rem)]"
          gyms={gyms}
          selectedId={selectedId}
          onSelect={setSelectedId}
          initialViewport={initialViewport}
          onViewportChange={onViewportChange}
          userLocation={geo.position}
          flyTo={flyTo}
        />
        {geo.status !== 'unsupported' && (
          <div className="absolute bottom-3 left-3">
            <Button
              variant="secondary"
              onClick={goToMyLocation}
              disabled={locating || geo.status === 'denied'}
              aria-label="내 위치로 이동"
              title={geo.status === 'denied' ? '브라우저에서 위치 권한이 거부되었습니다' : undefined}
            >
              <span aria-hidden>◎</span>
              {locating ? '찾는 중…' : '내 위치'}
            </Button>
          </div>
        )}
      </div>

      <div className="mt-4 md:mt-0 md:max-h-[calc(100vh-8rem)] md:overflow-y-auto md:pr-1">
        <div className="mb-3 flex items-baseline justify-between gap-2">
          <h1 className="text-xl font-semibold text-ink-700">
            이 지역 암장{' '}
            {data && (
              <span className="text-base font-medium text-ink-400 tabular-nums">
                {count.format(gyms.length)}
                {gyms.length >= MAX_RESULTS ? '+' : ''}곳
              </span>
            )}
          </h1>
          {isFetching && !isPending && (
            <span role="status" className="text-xs text-ink-300">
              갱신 중…
            </span>
          )}
        </div>
        {origin && (
          <p className="mb-3 text-xs text-ink-400">
            거리는 {geo.position ? '내 위치' : '지도 중심'} 기준
            {gyms.length >= MAX_RESULTS && ' · 지도를 확대하면 더 정확히 보여요'}
          </p>
        )}

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
        {data && gyms.length === 0 && (
          <div className="rounded-card border border-chalk-300 bg-white p-6 text-center">
            <p className="text-sm font-medium text-ink-600">이 지역엔 암장이 없어요</p>
            <p className="mt-1 text-xs text-pretty text-ink-400">
              지도를 움직이거나 축소해서 다른 지역을 살펴보세요.
            </p>
          </div>
        )}

        <ul className="space-y-3">
          {gyms.map((gym) => {
            const selected = gym.id === selectedId
            return (
              <li
                key={gym.id}
                ref={(el) => {
                  if (el) itemRefs.current.set(gym.id, el)
                  else itemRefs.current.delete(gym.id)
                }}
              >
                {/* 선택형 카드 — 공통 Button 의 CTA 스타일과 달라 직접 만든다 (aria-pressed 로 상태 노출) */}
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => selectFromList(gym)}
                  className={`block w-full rounded-card border bg-white p-4 text-left transition-colors duration-150 hover:border-chalk-400 ${
                    selected ? 'border-hold-500' : 'border-chalk-300'
                  }`}
                >
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
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}
