import maplibregl, { type GeoJSONSource, type LngLatBoundsLike } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'

import type { GymPoint } from '@/api/gyms'

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
  /** 전국 좌표. MapLibre 가 줌에 따라 클러스터로 묶는다 */
  points: GymPoint[]
  selectedId: number | null
  onSelect: (id: number | null) => void
  /** 최초 1회만 반영. 이후 이동은 flyTo 로 */
  initialViewport: Viewport
  /** 지도 이동이 멈춘 뒤(디바운스) 호출 */
  onViewportChange: (viewport: ViewportBox) => void
  /** 점으로 표시할 사용자 위치 */
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

const SOURCE_ID = 'gyms'
/** 이 줌까지는 묶고, 그 위(동네 단위)부터는 낱개로 보여준다 */
const CLUSTER_MAX_ZOOM = 13
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

function toFeatureCollection(points: GymPoint[]): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: 'FeatureCollection',
    features: points.map((p) => ({
      type: 'Feature',
      id: p.id,
      geometry: { type: 'Point', coordinates: [p.lng, p.lat] },
      properties: { id: p.id, name: p.name },
    })),
  }
}

const count = new Intl.NumberFormat('ko-KR')

function buttonElement(className: string, onClick: () => void) {
  const el = document.createElement('button')
  el.type = 'button'
  el.className = className
  // 지도 자체의 click(선택 해제)까지 번지지 않게
  el.addEventListener('click', (e) => {
    e.stopPropagation()
    onClick()
  })
  return el
}

function clusterElement(n: number, onClick: () => void) {
  const size = n >= 50 ? ' is-lg' : n >= 10 ? ' is-md' : ''
  const el = buttonElement(`gym-cluster${size}`, onClick)
  el.textContent = count.format(n)
  return el
}

type ClusterProps = { cluster: true; cluster_id: number; point_count: number }
type PointProps = { cluster?: undefined; id: number; name: string }

export default function GymMap({
  points,
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
  // key: 낱개는 `p{id}`, 클러스터는 `c{cluster_id}`
  const markersRef = useRef(new Map<string, maplibregl.Marker>())
  const userMarkerRef = useRef<maplibregl.Marker | null>(null)
  const pointsRef = useRef(points)
  const selectedRef = useRef(selectedId)
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

    const markers = markersRef.current

    const applySelection = () => {
      markers.forEach((marker, key) => {
        if (!key.startsWith('p')) return
        const selected = key === `p${selectedRef.current}`
        marker.getElement().classList.toggle('is-selected', selected)
        marker.getElement().setAttribute('aria-pressed', String(selected))
      })
    }

    const expandCluster = async (clusterId: number, center: [number, number]) => {
      const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined
      if (!source) return
      const zoom = await source.getClusterExpansionZoom(clusterId)
      const target = { center, zoom: Math.min(zoom, 18) }
      if (reducedMotion()) map.jumpTo(target)
      else map.easeTo({ ...target, duration: 400 })
    }

    // 화면에 보이는 클러스터/낱개를 DOM 마커로 맞춘다 (MapLibre 공식 HTML 클러스터 패턴).
    // 레이어 대신 DOM 을 쓰는 이유: 글리프 폰트 없이 숫자를 찍고, 기존 마커 CSS·aria 를 재사용.
    const syncMarkers = () => {
      if (!map.getSource(SOURCE_ID)) return
      const seen = new Set<string>()
      for (const feature of map.querySourceFeatures(SOURCE_ID)) {
        const props = feature.properties as ClusterProps | PointProps
        const coords = (feature.geometry as GeoJSON.Point).coordinates as [number, number]
        const key = props.cluster ? `c${props.cluster_id}` : `p${props.id}`
        if (seen.has(key)) continue // 타일 경계에 걸친 피처는 중복으로 온다
        seen.add(key)
        if (markers.has(key)) continue
        const element = props.cluster
          ? clusterElement(props.point_count, () => expandCluster(props.cluster_id, coords))
          : buttonElement('gym-marker', () => onSelectRef.current(props.id))
        const marker = new maplibregl.Marker({ element, anchor: 'center' })
          .setLngLat(coords)
          .addTo(map)
        // addTo 가 aria-label 을 "Map marker" 로 덮어쓰므로 그 뒤에 설정한다
        marker
          .getElement()
          .setAttribute(
            'aria-label',
            props.cluster ? `암장 ${count.format(props.point_count)}곳 — 확대해서 보기` : props.name,
          )
        markers.set(key, marker)
      }
      markers.forEach((marker, key) => {
        if (!seen.has(key)) {
          marker.remove()
          markers.delete(key)
        }
      })
      applySelection()
    }

    let timer: ReturnType<typeof setTimeout> | undefined
    const emit = () => onViewportChangeRef.current(readViewport(map))
    map.on('moveend', () => {
      clearTimeout(timer)
      timer = setTimeout(emit, MOVE_DEBOUNCE_MS)
    })

    map.once('load', () => {
      map.addSource(SOURCE_ID, {
        type: 'geojson',
        data: toFeatureCollection(pointsRef.current),
        cluster: true,
        clusterRadius: 50,
        clusterMaxZoom: CLUSTER_MAX_ZOOM,
      })
      // 소스는 레이어가 하나라도 써야 타일이 로드된다 — 그리지는 않는다
      map.addLayer({
        id: 'gyms-anchor',
        type: 'circle',
        source: SOURCE_ID,
        paint: { 'circle-radius': 0, 'circle-opacity': 0 },
      })
      map.on('sourcedata', (e) => {
        if (e.sourceId === SOURCE_ID && e.isSourceLoaded) syncMarkers()
      })
      map.on('move', syncMarkers)
      map.on('moveend', syncMarkers)
      emit()
    })

    mapRef.current = map
    return () => {
      clearTimeout(timer)
      markers.forEach((m) => m.remove())
      markers.clear()
      userMarkerRef.current = null
      map.remove()
      mapRef.current = null
    }
    // 초기 뷰포트는 생성 시점 값만 쓴다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 좌표 데이터 갱신
  useEffect(() => {
    pointsRef.current = points
    const source = mapRef.current?.getSource(SOURCE_ID) as GeoJSONSource | undefined
    source?.setData(toFeatureCollection(points))
  }, [points])

  // 선택 상태 표시
  useEffect(() => {
    selectedRef.current = selectedId
    markersRef.current.forEach((marker, key) => {
      if (!key.startsWith('p')) return
      const selected = key === `p${selectedId}`
      marker.getElement().classList.toggle('is-selected', selected)
      marker.getElement().setAttribute('aria-pressed', String(selected))
    })
  }, [selectedId])

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
      // 낱개 마커가 보이는 줌까지는 들어간다 — 카드로 고른 암장이 클러스터에 묻히지 않게
      zoom: flyTo.zoom ?? Math.max(map.getZoom(), CLUSTER_MAX_ZOOM + 1),
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
