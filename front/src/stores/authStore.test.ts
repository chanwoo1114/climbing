// @vitest-environment jsdom
/**
 * 세션 복원 + refresh single-flight.
 * 서버는 refresh 토큰을 회전하고 이전 토큰을 블랙리스트에 넣으므로, 동시에 401 을 받은
 * 요청들이 각자 refresh 를 부르면 두 번째부터 실패해 강제 로그아웃된다. 반드시 한 번만.
 */
import axios from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getRefreshToken, useAuthStore } from './authStore'

vi.mock('axios', async (importOriginal) => {
  const actual = await importOriginal<typeof import('axios')>()
  return { ...actual, default: { ...actual.default, post: vi.fn(), isAxiosError: actual.default.isAxiosError } }
})

const post = vi.mocked(axios.post)
const KEY = 'climbing.refresh'

function deferred<T>() {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function rejection(status: number) {
  return Object.assign(new axios.AxiosError('nope'), { response: { status } })
}

beforeEach(() => {
  localStorage.clear()
  post.mockReset()
  useAuthStore.setState({ status: 'anonymous', accessToken: null, user: null })
})

describe('refresh', () => {
  it('동시에 여러 번 불러도 서버 요청은 한 번이고 모두 같은 결과를 받는다', async () => {
    localStorage.setItem(KEY, 'old-refresh')
    const d = deferred<{ data: unknown }>()
    post.mockReturnValueOnce(d.promise)

    const { refresh } = useAuthStore.getState()
    const results = Promise.all([refresh(), refresh(), refresh()])
    expect(post).toHaveBeenCalledTimes(1)

    d.resolve({ data: { success: true, data: { access: 'new-access', refresh: 'new-refresh' } } })
    expect(await results).toEqual([true, true, true])

    expect(useAuthStore.getState().accessToken).toBe('new-access')
    expect(useAuthStore.getState().status).toBe('authenticated')
    expect(getRefreshToken()).toBe('new-refresh') // 회전된 토큰으로 교체
  })

  it('앞선 refresh 가 끝난 뒤에는 다시 요청할 수 있다', async () => {
    localStorage.setItem(KEY, 'r1')
    post.mockResolvedValueOnce({ data: { data: { access: 'a1', refresh: 'r2' } } })
    await useAuthStore.getState().refresh()
    post.mockResolvedValueOnce({ data: { data: { access: 'a2', refresh: 'r3' } } })
    await useAuthStore.getState().refresh()
    expect(post).toHaveBeenCalledTimes(2)
    expect(post.mock.calls[1][1]).toEqual({ refresh: 'r2' }) // 두 번째는 회전된 토큰으로
  })

  it('서버가 401 로 거부하면 세션을 지운다 (토큰 삭제 + anonymous)', async () => {
    localStorage.setItem(KEY, 'blacklisted')
    useAuthStore.setState({ accessToken: 'stale', status: 'authenticated' })
    post.mockRejectedValueOnce(rejection(401))

    expect(await useAuthStore.getState().refresh()).toBe(false)
    expect(useAuthStore.getState().status).toBe('anonymous')
    expect(useAuthStore.getState().accessToken).toBeNull()
    expect(getRefreshToken()).toBeNull()
  })

  it('네트워크 오류면 토큰은 남기고 비로그인으로만 취급한다 (다음에 재시도 가능)', async () => {
    localStorage.setItem(KEY, 'keep-me')
    post.mockRejectedValueOnce(new axios.AxiosError('Network Error'))

    expect(await useAuthStore.getState().refresh()).toBe(false)
    expect(useAuthStore.getState().status).toBe('anonymous')
    expect(getRefreshToken()).toBe('keep-me')
  })

  it('저장된 refresh 토큰이 없으면 요청 없이 false', async () => {
    expect(await useAuthStore.getState().refresh()).toBe(false)
    expect(post).not.toHaveBeenCalled()
  })
})

describe('bootstrap (새로고침 시 세션 복원)', () => {
  it('토큰이 있으면 access 를 재발급받아 authenticated 가 된다', async () => {
    localStorage.setItem(KEY, 'saved')
    useAuthStore.setState({ status: 'booting' })
    post.mockResolvedValueOnce({ data: { data: { access: 'restored', refresh: 'rotated' } } })

    await useAuthStore.getState().bootstrap()
    expect(useAuthStore.getState()).toMatchObject({ status: 'authenticated', accessToken: 'restored' })
  })

  it('토큰이 없으면 요청 없이 anonymous', async () => {
    useAuthStore.setState({ status: 'booting' })
    await useAuthStore.getState().bootstrap()
    expect(useAuthStore.getState().status).toBe('anonymous')
    expect(post).not.toHaveBeenCalled()
  })
})

describe('setSession / clear', () => {
  it('로그인하면 authenticated + refresh 저장, 로그아웃하면 전부 제거', () => {
    useAuthStore.getState().setSession('acc', 'ref', { id: 1, email: 'a@b.com', nickname: 'a' })
    expect(useAuthStore.getState()).toMatchObject({ status: 'authenticated', accessToken: 'acc' })
    expect(getRefreshToken()).toBe('ref')

    useAuthStore.getState().clear()
    expect(useAuthStore.getState()).toMatchObject({ status: 'anonymous', accessToken: null, user: null })
    expect(getRefreshToken()).toBeNull()
  })
})
