// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearKakaoRoundTrip,
  readKakaoRoundTrip,
  safeReturnPath,
  saveKakaoRoundTrip,
} from './kakaoLogin'

describe('safeReturnPath', () => {
  it('앱 내부 절대 경로만 그대로 돌려준다', () => {
    expect(safeReturnPath('/')).toBe('/')
    expect(safeReturnPath('/logs/3?tab=comments')).toBe('/logs/3?tab=comments')
  })

  it('외부·상대·비문자열 경로는 홈으로 바꾼다', () => {
    expect(safeReturnPath('//evil.example')).toBe('/')
    expect(safeReturnPath('https://evil.example/x')).toBe('/')
    expect(safeReturnPath('logs')).toBe('/')
    expect(safeReturnPath(undefined)).toBe('/')
    expect(safeReturnPath(42)).toBe('/')
  })
})

describe('kakao round trip storage', () => {
  beforeEach(() => sessionStorage.clear())

  it('저장한 state 와 from 을 그대로 읽는다', () => {
    saveKakaoRoundTrip({ state: 'abc:123', from: '/profile' })
    expect(readKakaoRoundTrip()).toEqual({ state: 'abc:123', from: '/profile' })
  })

  it('from 이 외부 주소면 읽을 때 홈으로 정규화한다', () => {
    saveKakaoRoundTrip({ state: 's', from: 'https://evil.example' })
    expect(readKakaoRoundTrip()?.from).toBe('/')
  })

  it('비어 있거나 깨진 값은 null', () => {
    expect(readKakaoRoundTrip()).toBeNull()
    sessionStorage.setItem('climbing.kakao', '{not json')
    expect(readKakaoRoundTrip()).toBeNull()
    sessionStorage.setItem('climbing.kakao', JSON.stringify({ from: '/' }))
    expect(readKakaoRoundTrip()).toBeNull()
  })

  it('clear 하면 사라진다', () => {
    saveKakaoRoundTrip({ state: 's', from: '/' })
    clearKakaoRoundTrip()
    expect(readKakaoRoundTrip()).toBeNull()
  })
})
