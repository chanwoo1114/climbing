/* global self, clients */
/**
 * 브라우저 푸시 서비스워커 — 번들 없이 그대로 서빙된다 (Vite public/ → /sw.js).
 * 구독·해지는 src/hooks/usePush.ts, 발송은 backend notifications (Web Push 페이로드는
 * NotificationSerializer 와 같은 키: id, type, message, target_type, target_id, url, created_at).
 */

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('push', (event) => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = { message: event.data ? event.data.text() : '' }
  }
  const message = payload.message || '새 알림이 도착했어요'
  const url = payload.url || '/notifications'
  event.waitUntil(
    self.registration.showNotification(message, {
      body: '',
      data: { url: url, id: payload.id },
      tag: 'n-' + (payload.id || Date.now()),
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    // 이미 열린 탭이 있으면 거기로, 없으면 새 창
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      const target = new URL(url, self.location.origin).href
      for (const client of windowClients) {
        if ('navigate' in client && 'focus' in client) {
          return client.navigate(target).then((c) => (c ? c.focus() : undefined))
        }
      }
      return clients.openWindow(target)
    }),
  )
})
