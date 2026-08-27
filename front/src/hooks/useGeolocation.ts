import { useCallback, useEffect, useState } from 'react'

export interface LatLng {
  lat: number
  lng: number
}

export type GeolocationStatus =
  | 'idle' // 아직 요청 안 함
  | 'locating'
  | 'granted'
  | 'denied'
  | 'unsupported'

/**
 * 현재 위치. 페이지 진입 시 권한 프롬프트를 띄우지 않는다 —
 * 이미 허용된 상태(permissions API)일 때만 자동으로 읽고, 아니면 locate() 호출을 기다린다.
 */
export function useGeolocation() {
  const [position, setPosition] = useState<LatLng | null>(null)
  const [status, setStatus] = useState<GeolocationStatus>(() =>
    typeof navigator !== 'undefined' && 'geolocation' in navigator ? 'idle' : 'unsupported',
  )

  const locate = useCallback(() => {
    if (!('geolocation' in navigator)) {
      setStatus('unsupported')
      return
    }
    setStatus('locating')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPosition({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setStatus('granted')
      },
      (err) => {
        setStatus(err.code === err.PERMISSION_DENIED ? 'denied' : 'idle')
      },
      { enableHighAccuracy: false, timeout: 8_000, maximumAge: 60_000 },
    )
  }, [])

  useEffect(() => {
    if (status !== 'idle' || !('permissions' in navigator)) return
    let cancelled = false
    navigator.permissions
      .query({ name: 'geolocation' })
      .then((result) => {
        if (!cancelled && result.state === 'granted') locate()
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
    // 마운트 시 1회만 확인
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { position, status, locate }
}
