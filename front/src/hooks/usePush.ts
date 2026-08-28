import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { getErrorCode, getErrorMessage } from '@/api/client'
import {
  createPushSubscription,
  deletePushSubscription,
  fetchPushPublicKey,
} from '@/api/notifications'
import { urlBase64ToUint8Array } from '@/lib/push'

/**
 * 브라우저 푸시 구독 상태
 * - unsupported     : 서비스워커·PushManager·Notification 중 하나라도 없는 브라우저(iOS 홈화면 미설치 등)
 * - not_configured  : 서버에 VAPID 키가 없다 (503 push_not_configured)
 * - denied          : 사용자가 알림 권한을 거부 — 브라우저 설정에서 풀어야 한다
 * - subscribed / unsubscribed : 이 브라우저의 구독 여부
 * - busy            : 확인 중이거나 구독/해지 진행 중
 */
export type PushStatus =
  | 'unsupported'
  | 'denied'
  | 'not_configured'
  | 'subscribed'
  | 'unsubscribed'
  | 'busy'

/** public/sw.js — Vite 가 public/ 을 루트로 서빙하므로 dev·prod 모두 같은 경로 */
export const SERVICE_WORKER_URL = '/sw.js'

export const pushPublicKeyKey = ['push', 'public-key'] as const

export function isPushSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

type Phase = 'checking' | 'subscribed' | 'unsubscribed' | 'busy'

async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.getRegistration(SERVICE_WORKER_URL)
  return (await registration?.pushManager.getSubscription()) ?? null
}

export function usePushSubscription() {
  const supported = useMemo(isPushSupported, [])
  const publicKey = useQuery({
    queryKey: pushPublicKeyKey,
    queryFn: fetchPushPublicKey,
    enabled: supported,
    retry: false, // 키가 없는 서버는 재시도해도 같다
    staleTime: Infinity,
  })
  const [phase, setPhase] = useState<Phase>('checking')
  const [permission, setPermission] = useState<NotificationPermission>(() =>
    supported ? Notification.permission : 'default',
  )
  const [actionError, setActionError] = useState<string | null>(null)

  // 이 브라우저에 이미 구독이 있는지 — 서비스워커 등록이 없으면 미구독
  useEffect(() => {
    if (!supported) return
    let cancelled = false
    currentSubscription()
      .then((subscription) => {
        if (!cancelled) setPhase(subscription ? 'subscribed' : 'unsubscribed')
      })
      .catch(() => {
        if (!cancelled) setPhase('unsubscribed')
      })
    return () => {
      cancelled = true
    }
  }, [supported])

  const subscribe = useCallback(async () => {
    const key = publicKey.data
    if (!supported || !key) return
    setActionError(null)
    setPhase('busy')
    try {
      const result = await Notification.requestPermission()
      setPermission(result)
      if (result !== 'granted') {
        setPhase('unsubscribed')
        return
      }
      const registration = await navigator.serviceWorker.register(SERVICE_WORKER_URL)
      const subscription =
        (await registration.pushManager.getSubscription()) ??
        (await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(key),
        }))
      const json = subscription.toJSON()
      if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
        throw new Error('브라우저가 구독 정보를 돌려주지 않았습니다.')
      }
      await createPushSubscription({
        endpoint: json.endpoint,
        keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
        userAgent: navigator.userAgent,
      })
      setPhase('subscribed')
    } catch (error) {
      setActionError(getErrorMessage(error, '푸시 구독에 실패했습니다. 잠시 후 다시 시도해 주세요.'))
      setPhase('unsubscribed')
    }
  }, [supported, publicKey.data])

  const unsubscribe = useCallback(async () => {
    if (!supported) return
    setActionError(null)
    setPhase('busy')
    try {
      const subscription = await currentSubscription()
      if (subscription) {
        // 서버 기록이 남아도 다음 발송에서 410 으로 정리되므로 실패는 무시한다
        await deletePushSubscription(subscription.endpoint).catch(() => undefined)
        await subscription.unsubscribe()
      }
      setPhase('unsubscribed')
    } catch (error) {
      setActionError(getErrorMessage(error, '푸시 구독을 해지하지 못했습니다.'))
      setPhase('subscribed')
    }
  }, [supported])

  const notConfigured = getErrorCode(publicKey.error) === 'push_not_configured'

  let status: PushStatus
  if (!supported) status = 'unsupported'
  else if (notConfigured) status = 'not_configured'
  else if (permission === 'denied') status = 'denied'
  else if (phase === 'checking' || phase === 'busy' || publicKey.isPending) status = 'busy'
  else status = phase

  const error =
    actionError ??
    (publicKey.isError && !notConfigured
      ? getErrorMessage(publicKey.error, '푸시 설정을 불러오지 못했습니다.')
      : null)

  return { status, error, subscribe, unsubscribe }
}
