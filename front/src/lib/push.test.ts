import { describe, expect, it } from 'vitest'

import { uint8ArrayToUrlBase64, urlBase64ToUint8Array } from '@/lib/push'

describe('urlBase64ToUint8Array', () => {
  it('base64url 을 바이트로 푼다 (패딩 없음)', () => {
    expect(Array.from(urlBase64ToUint8Array('AQID'))).toEqual([1, 2, 3])
    // 'AQI' 는 패딩이 빠진 2바이트
    expect(Array.from(urlBase64ToUint8Array('AQI'))).toEqual([1, 2])
  })

  it('url-safe 문자(- _)를 표준 base64(+ /)로 되돌린다', () => {
    // 0xfb 0xff → base64 '+/8=' → base64url '-_8'
    expect(Array.from(urlBase64ToUint8Array('-_8'))).toEqual([0xfb, 0xff])
    expect(uint8ArrayToUrlBase64(new Uint8Array([0xfb, 0xff]))).toBe('-_8')
  })

  it('왕복하면 원래 바이트가 나온다 (VAPID 키 길이 65바이트)', () => {
    const original = new Uint8Array(65)
    for (let i = 0; i < original.length; i++) original[i] = (i * 37 + 11) % 256
    const encoded = uint8ArrayToUrlBase64(original)
    expect(encoded).not.toMatch(/[+/=]/)
    const decoded = urlBase64ToUint8Array(encoded)
    expect(decoded).toBeInstanceOf(Uint8Array)
    expect(Array.from(decoded)).toEqual(Array.from(original))
  })
})
