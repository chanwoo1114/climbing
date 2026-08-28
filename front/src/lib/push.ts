/**
 * Web Push 보조 함수.
 * VAPID 공개키는 base64url 문자열로 내려오는데 PushManager.subscribe() 의
 * applicationServerKey 는 바이트 배열이어야 한다.
 */

/** base64url(패딩 유무 무관) → Uint8Array */
export function urlBase64ToUint8Array(base64url: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64url.length % 4)) % 4)
  const base64 = (base64url + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const bytes = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes
}

/** Uint8Array → base64url (패딩 없음). 테스트·디버깅용 역변환 */
export function uint8ArrayToUrlBase64(bytes: Uint8Array): string {
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}
