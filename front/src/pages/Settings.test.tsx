import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Settings from '@/pages/Settings'
import { useAuthStore } from '@/stores/authStore'
import { useToastStore } from '@/stores/toastStore'
import { ME, renderWithProviders } from '@/test/render'
import { API, fail, http, ok, server } from '@/test/server'

const SETTINGS = { push_enabled: true, email_enabled: true }
const NEW_PASSWORD = 'Newpass9!x'

function renderSettings() {
  return renderWithProviders(<Settings />, { route: '/settings', user: ME })
}

/** TextField 는 검증 상태가 생기면 label 안에 ✓/✕ 글자를 덧붙이므로 그걸 빼고 정확히 맞춘다 */
const byLabel = (label: string) =>
  screen.getByLabelText((text) => text.replace(/[✓✕]\s*$/, '').trim() === label)

async function fillPasswordForm(user: ReturnType<typeof renderSettings>['user'], current: string) {
  await user.type(byLabel('현재 비밀번호'), current)
  await user.type(byLabel('새 비밀번호'), NEW_PASSWORD)
  await user.type(byLabel('새 비밀번호 확인'), NEW_PASSWORD)
  await user.click(screen.getByRole('button', { name: '비밀번호 변경' }))
}

describe('Settings', () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] })
    server.use(http.get(API('/notifications/settings/'), () => ok(SETTINGS)))
  })

  it('알림 설정을 불러와 스위치로 보여준다', async () => {
    renderSettings()
    const email = await screen.findByRole('switch', { name: '이메일 알림' })
    expect(email).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('switch', { name: '브라우저 푸시' })).toHaveAttribute(
      'aria-checked',
      'true',
    )
  })

  it('이메일 스위치를 끄면 낙관적으로 바뀌고 {email_enabled:false} 를 PATCH 한다', async () => {
    let body: unknown = null
    server.use(
      http.patch(API('/notifications/settings/'), async ({ request }) => {
        body = await request.json()
        return ok({ ...SETTINGS, email_enabled: false })
      }),
    )
    const { user } = renderSettings()
    const email = await screen.findByRole('switch', { name: '이메일 알림' })
    await user.click(email)
    expect(email).toHaveAttribute('aria-checked', 'false')
    await waitFor(() => expect(body).toEqual({ email_enabled: false }))
    expect(email).toHaveAttribute('aria-checked', 'false')
  })

  it('PATCH 가 500 이면 이전 값으로 되돌리고 오류를 알린다', async () => {
    // 응답을 붙들어 두어야 낙관적으로 바뀐 순간을 볼 수 있다
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(
      http.patch(API('/notifications/settings/'), async () => {
        await gate
        return fail(500, 'server_error', '잠시 후 다시 시도해 주세요.')
      }),
    )
    const { user } = renderSettings()
    const email = await screen.findByRole('switch', { name: '이메일 알림' })
    await user.click(email)
    expect(email).toHaveAttribute('aria-checked', 'false')
    release()
    await waitFor(() => expect(email).toHaveAttribute('aria-checked', 'true'))
    expect(screen.getByRole('alert')).toHaveTextContent('잠시 후 다시 시도해 주세요.')
  })

  it('비밀번호 변경에 성공하면 새 토큰 쌍으로 세션을 바꾸고 토스트를 띄운다', async () => {
    let body: unknown = null
    server.use(
      http.post(API('/auth/password/change/'), async ({ request }) => {
        body = await request.json()
        return ok({ access: 'new-access', refresh: 'new-refresh' })
      }),
    )
    const { user } = renderSettings()
    await screen.findByRole('switch', { name: '이메일 알림' })
    await fillPasswordForm(user, 'oldpass1!')

    await waitFor(() => expect(useAuthStore.getState().accessToken).toBe('new-access'))
    expect(body).toEqual({ current_password: 'oldpass1!', new_password: NEW_PASSWORD })
    expect(window.localStorage.getItem('climbing.refresh')).toBe('new-refresh')
    expect(useToastStore.getState().toasts[0]?.title).toBe('비밀번호를 변경했습니다.')
    // 폼은 비워진다
    expect(byLabel('현재 비밀번호')).toHaveValue('')
    expect(byLabel('새 비밀번호')).toHaveValue('')
  })

  it('현재 비밀번호가 틀리면 필드 아래에 서버 메시지를 보여준다', async () => {
    server.use(
      http.post(API('/auth/password/change/'), () =>
        fail(400, 'invalid', '입력을 확인해 주세요.', {
          current_password: ['현재 비밀번호가 올바르지 않습니다.'],
        }),
      ),
    )
    const { user } = renderSettings()
    await screen.findByRole('switch', { name: '이메일 알림' })
    await fillPasswordForm(user, 'wrongpass1!')

    expect(await screen.findByText('현재 비밀번호가 올바르지 않습니다.')).toBeInTheDocument()
    expect(byLabel('현재 비밀번호')).toHaveAttribute('aria-invalid', 'true')
    expect(useAuthStore.getState().accessToken).toBe('test-access-token')
  })

  it('비밀번호 없는 계정(no_password)이면 재설정 링크를 안내한다', async () => {
    server.use(
      http.post(API('/auth/password/change/'), () =>
        fail(
          400,
          'no_password',
          '비밀번호가 없는 계정입니다. 비밀번호 재설정으로 먼저 만들어 주세요.',
        ),
      ),
    )
    const { user } = renderSettings()
    await screen.findByRole('switch', { name: '이메일 알림' })
    await fillPasswordForm(user, 'anything1!')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('비밀번호가 없는 계정입니다.')
    expect(within(alert).getByRole('link', { name: '비밀번호 재설정하기' })).toHaveAttribute(
      'href',
      '/forgot-password',
    )
  })

  it('탈퇴: 비밀번호로 확인하면 DELETE 후 세션을 지우고 홈으로 간다', async () => {
    let body: unknown = null
    server.use(
      http.delete(API('/users/me/'), async ({ request }) => {
        body = await request.json()
        return new Response(null, { status: 204 })
      }),
    )
    const { user, queryClient } = renderSettings()
    await screen.findByRole('switch', { name: '이메일 알림' })
    await user.click(screen.getByRole('button', { name: '회원 탈퇴' }))

    const dialog = screen.getByRole('dialog', { hidden: true })
    await user.type(within(dialog).getByLabelText('비밀번호 확인'), 'mypass1!')
    await user.click(within(dialog).getByRole('button', { name: '탈퇴하기' }))

    expect(await screen.findByTestId('location')).toHaveTextContent('/')
    expect(body).toEqual({ password: 'mypass1!' })
    expect(useAuthStore.getState().status).toBe('anonymous')
    expect(useAuthStore.getState().accessToken).toBeNull()
    expect(queryClient.getQueryData(['me'])).toBeUndefined()
    expect(useToastStore.getState().toasts[0]?.title).toBe('탈퇴가 완료되었습니다.')
  })

  it('탈퇴: 크루장이면(409 crew_owner) 크루 목록 링크와 함께 알린다', async () => {
    server.use(
      http.delete(API('/users/me/'), () =>
        fail(
          409,
          'crew_owner',
          '크루장인 크루가 있어 탈퇴할 수 없습니다. 크루장을 위임하거나 크루를 먼저 삭제해 주세요.',
        ),
      ),
    )
    const { user } = renderSettings()
    await screen.findByRole('switch', { name: '이메일 알림' })
    await user.click(screen.getByRole('button', { name: '회원 탈퇴' }))
    const dialog = screen.getByRole('dialog', { hidden: true })
    await user.click(within(dialog).getByRole('button', { name: '탈퇴하기' }))

    const alert = await within(dialog).findByRole('alert')
    expect(alert).toHaveTextContent('크루장인 크루가 있어 탈퇴할 수 없습니다.')
    expect(within(alert).getByRole('link', { name: '내 크루 보기' })).toHaveAttribute('href', '/crews')
    expect(useAuthStore.getState().status).toBe('authenticated')
    expect(screen.queryByTestId('location')).not.toBeInTheDocument()
  })

  it('푸시: PushManager 가 없는 브라우저(jsdom)면 미지원 안내와 함께 스위치를 잠근다', async () => {
    renderSettings()
    await screen.findByRole('switch', { name: '이메일 알림' })
    expect(screen.getByText('이 브라우저는 푸시를 지원하지 않습니다.')).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: '이 브라우저에서 받기' })).toBeDisabled()
  })

  describe('푸시를 지원하는 브라우저', () => {
    beforeEach(() => {
      vi.stubGlobal('PushManager', class PushManager {})
      vi.stubGlobal('Notification', { permission: 'default', requestPermission: vi.fn() })
      Object.defineProperty(window.navigator, 'serviceWorker', {
        configurable: true,
        value: { register: vi.fn(), getRegistration: vi.fn().mockResolvedValue(undefined) },
      })
    })
    afterEach(() => {
      vi.unstubAllGlobals()
      delete (window.navigator as { serviceWorker?: unknown }).serviceWorker
    })

    it('서버에 VAPID 키가 없으면(503) 설정되어 있지 않다고 알리고 스위치를 잠근다', async () => {
      server.use(
        http.get(API('/notifications/push/public-key/'), () =>
          fail(503, 'push_not_configured', '푸시가 설정되어 있지 않습니다.'),
        ),
      )
      renderSettings()
      expect(
        await screen.findByText('이 서버에는 푸시가 설정되어 있지 않습니다.'),
      ).toBeInTheDocument()
      expect(screen.getByRole('switch', { name: '이 브라우저에서 받기' })).toBeDisabled()
    })

    it('키가 있고 구독이 없으면 스위치를 켤 수 있다', async () => {
      server.use(http.get(API('/notifications/push/public-key/'), () => ok({ public_key: 'AQID' })))
      renderSettings()
      const toggle = screen.getByRole('switch', { name: '이 브라우저에서 받기' })
      await waitFor(() => expect(toggle).toBeEnabled())
      expect(toggle).toHaveAttribute('aria-checked', 'false')
      expect(screen.getByText('구독하면 탭을 닫아도 새 알림을 받을 수 있어요.')).toBeInTheDocument()
    })
  })
})
