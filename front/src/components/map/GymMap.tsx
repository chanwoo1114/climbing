import maplibregl, { type LngLatBoundsLike } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'

import type { GymSummary } from '@/api/gyms'

export interface Viewport {
  lat: number
  lng: number
  zoom: number
}

export interface ViewportBox extends Viewport {
  /** minLng,minLat,maxLng,maxLat — 백엔드 bbox 파라미터 형식 */
  bbox: string
}

interface Props {
  gyms: GymSummary[]
  selectedId: number | null
  onSelect: (id: number | null) => void
  /** 최초 1회만 반영. 이후 이동은 flyTo 로 */
  initialViewport: Viewport
  /** 지도 이동이 멈춘 뒤(디바운스) 호출 */
  onViewportChange: (viewport: ViewportBox) => void
  /** 파란 점으로 표시할 사용자 위치 */
  userLocation: { lat: number; lng: number } | null
  /** 바뀌면 그 위치로 이동한다 (카드 클릭·내 위치 버튼) */
  flyTo: { lat: number; lng: number; zoom?: number; key: number } | null
  className?: string
}

// OpenStreetMap 표준 래스터 타일 — 키 없이 쓸 수 있고 한국 지역은 한글 표기.
// (CARTO 베이스맵은 2025년부터 API 키가 필요해져 워터마크가 찍힌다.)
// 원색 타일을 채도·대비로 눌러 초크 팔레트 위에 얹어도 튀지 않게 한다.
// 트래픽이 커지면 OSM 타일 정책상 MapTiler 등 키 기반 제공자로 바꿔야 한다.
const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      maxzoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [
    {
      id: 'osm',
      type: 'raster',
      source: 'osm',
      paint: { 'raster-saturation': -0.7, 'raster-contrast': -0.1, 'raster-brightness-min': 0.05 },
    },
  ],
}

// 남한 밖으로 끝없이 끌려가지 않게 (제주·독도 포함)
const KOREA_BOUNDS: LngLatBoundsLike = [
  [122, 31],
  [134, 40],
]

const MOVE_DEBOUNCE_MS = 300

const reducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** 좌표는 소수 4자리(≈10m)면 충분 — 쿼리키가 미세 흔들림마다 바뀌지 않게 */
const round4 = (n: number) => Math.round(n * 1e4) / 1e4

function readViewport(map: maplibregl.Map): ViewportBox {
  const center = map.getCenter()
  const b = map.getBounds()
  return {
    lat: round4(center.lat),
    lng: round4(center.lng),
    zoom: Math.round(map.getZoom() * 10) / 10,
    bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(round4).join(','),
  }
}

function markerElement(onClick: () => void) {
  const el = document.createElement('button')
  el.type = 'button'
  el.className = 'gym-marker'
  el.addEventListener('click', (e) => {
    e.stopPropagation()
    onClick()
  })
  return el
}

export default function GymMap({
  gyms,
  selectedId,
  onSelect,
  initialViewport,
  onViewportChange,
  userLocation,
  flyTo,
  className = '',
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef(new Map<number, maplibregl.Marker>())
  const userMarkerRef = useRef<maplibregl.Marker | null>(null)
  // 콜백은 ref 로 들고 있어 지도 인스턴스를 다시 만들지 않는다
  const onViewportChangeRef = useRef(onViewportChange)
  const onSelectRef = useRef(onSelect)
  useEffect(() => {
    onViewportChangeRef.current = onViewportChange
    onSelectRef.current = onSelect
  })

  // 지도 생성 — 최초 1회. StrictMode 의 가짜 리마운트는 cleanup 으로 정리된다.
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const map = new maplibregl.Map({
      container,
      style: STYLE,
      center: [initialViewport.lng, initialViewport.lat],
      zoom: initialViewport.zoom,
      maxBounds: KOREA_BOUNDS,
      minZoom: 6,
      maxZoom: 18,
      attributionControl: { compact: true },
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.on('click', () => onSelectRef.current(null))

    let timer: ReturnType<typeof setTimeout> | undefined
    const emit = () => onViewportChangeRef.current(readViewport(map))
    map.on('moveend', () => {
      clearTimeout(timer)
      timer = setTimeout(emit, MOVE_DEBOUNCE_MS)
    })
    map.once('load', emit)

    mapRef.current = map
    return () => {
      clearTimeout(timer)
      markersRef.current.forEach((m) => m.remove())
      markersRef.current.clear()
      userMarkerRef.current = null
      map.remove()
      mapRef.current = null
    }
    // 초기 뷰포트는 생성 시점 값만 쓴다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 마커 동기화 — 들어온 것만 추가, 빠진 것만 제거
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const markers = markersRef.current
    const next = new Set(gyms.map((g) => g.id))
    markers.forEach((marker, id) => {
      if (!next.has(id)) {
        marker.remove()
        markers.delete(id)
      }
    })
    gyms.forEach((gym) => {
      if (markers.has(gym.id)) return
      const marker = new maplibregl.Marker({
        element: markerElement(() => onSelectRef.current(gym.id)),
        anchor: 'center',
      })
        .setLngLat([gym.lng, gym.lat])
        .addTo(map)
      // addTo 가 aria-label 을 "Map marker" 로 덮어쓰므로 그 뒤에 상호명으로 되돌린다
      marker.getElement().setAttribute('aria-label', gym.name)
      markers.set(gym.id, marker)
    })
  }, [gyms])

  // 선택 상태 표시
  useEffect(() => {
    markersRef.current.forEach((marker, id) => {
      const selected = id === selectedId
      marker.getElement().classList.toggle('is-selected', selected)
      marker.getElement().setAttribute('aria-pressed', String(selected))
    })
  }, [selectedId, gyms])

  // 사용자 위치 점
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (!userLocation) {
      userMarkerRef.current?.remove()
      userMarkerRef.current = null
      return
    }
    if (!userMarkerRef.current) {
      const el = document.createElement('div')
      el.className = 'user-marker'
      el.setAttribute('aria-hidden', 'true')
      userMarkerRef.current = new maplibregl.Marker({ element: el, anchor: 'center' }).addTo(
        map,
      )
    }
    userMarkerRef.current.setLngLat([userLocation.lng, userLocation.lat])
  }, [userLocation])

  // 외부 요청 이동
  useEffect(() => {
    const map = mapRef.current
    if (!map || !flyTo) return
    const target = {
      center: [flyTo.lng, flyTo.lat] as [number, number],
      zoom: flyTo.zoom ?? Math.max(map.getZoom(), 14),
    }
    if (reducedMotion()) map.jumpTo(target)
    else map.flyTo({ ...target, duration: 600, essential: true })
  }, [flyTo])

  return (
    <div
      ref={containerRef}
      role="region"
      aria-label="암장 지도"
      className={`relative overflow-hidden rounded-card border border-chalk-300 bg-chalk-200 ${className}`}
    />
  )
}
