/**
 * 크루장 위임 — 멤버 탭에서 크루장만 "크루장 위임" 을 보고, 확인 모달 → POST transfer → 토스트 + 상세 갱신.
 */
import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import CrewDetail from '@/pages/CrewDetail'
import { useToastStore } from '@/stores/toastStore'
import { ME, renderWithProviders } from '@/test/render'
import { API, fail, http, ok, page, server } from '@/test/server'

const CREW = {
  id: 1,
  name: '볼더팀',
  description: '',
  image: '',
  home_gym: null,
  owner: { id: 1, nickname: '나' },
  join_type: 'instant',
  member_count: 3,
  max_members: 30,
  my_status: 'owner',
  is_feed_public: true,
  chat_room_id: 5,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const member = (id: number, userId: number, nickname: string, role: string) => ({
  id,
  user: { id: userId, nickname, image: null },
  role,
  status: 'active',
  joined_at: '2026-02-01T00:00:00Z',
  created_at: '2026-02-01T00:00:00Z',
})

const MEMBERS = [
  member(11, 1, '나', 'owner'),
  member(12, 2, 'bravo', 'member'),
  member(13, 3, 'charlie', 'staff'),
]

function mockDetail(crew = CREW) {
  server.use(
    http.get(API('/crews/1/'), () => ok(crew)),
    http.get(API('/crews/1/members/'), ({ request }) =>
      new URL(request.url).searchParams.get('status') === 'active' ? page(MEMBERS) : page([]),
    ),
  )
}

function renderMembers() {
  return renderWithProviders(<CrewDetail />, {
    route: '/crews/1?tab=members',
    path: '/crews/:id',
    user: ME,
  })
}

const headerSection = () =>
  screen.getByRole('heading', { name: '볼더팀' }).closest('section') as HTMLElement

afterEach(() => {
  for (const toast of useToastStore.getState().toasts) useToastStore.getState().dismiss(toast.id)
})

describe('CrewDetail owner transfer', () => {
  it('lets the owner hand the crew over to an active member', async () => {
    mockDetail()
    let body: unknown = null
    server.use(
      http.post(API('/crews/1/transfer/'), async ({ request }) => {
        body = await request.json()
        return ok({ ...CREW, owner: { id: 2, nickname: 'bravo' }, my_status: 'staff' })
      }),
    )
    const { user } = renderMembers()

    // 본인·크루장 제외 — bravo, charlie 두 명에게만
    const actions = await screen.findAllByRole('button', { name: '크루장 위임' })
    expect(actions).toHaveLength(2)
    expect(within(headerSection()).getByRole('link', { name: '나' })).toHaveAttribute(
      'href',
      '/users/1',
    )

    await user.click(actions[0])
    const dialog = screen.getByRole('dialog', { name: 'bravo님에게 크루장을 넘길까요?' })
    expect(dialog).toHaveTextContent('크루장을 bravo님에게 넘깁니다. 회원님은 운영진이 됩니다.')
    await user.click(within(dialog).getByRole('button', { name: '위임하기' }))

    await waitFor(() => expect(body).toEqual({ user_id: 2 }))
    // 상세가 응답으로 갈아끼워져 크루장 표시가 바뀌고, 나는 운영진이라 위임 액션이 사라진다
    expect(
      await within(headerSection()).findByRole('link', { name: 'bravo' }),
    ).toHaveAttribute('href', '/users/2')
    expect(within(headerSection()).getByText('운영진')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '크루장 위임' })).not.toBeInTheDocument()
    expect(useToastStore.getState().toasts.map((t) => t.title)).toContain(
      'bravo님이 새 크루장이 됐어요',
    )
  })

  it('hides the action from non-owners', async () => {
    mockDetail({ ...CREW, owner: { id: 3, nickname: 'charlie' }, my_status: 'staff' })
    renderMembers()
    expect(await screen.findByRole('link', { name: 'bravo' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '크루장 위임' })).not.toBeInTheDocument()
  })

  it('shows the field error when the target is rejected', async () => {
    mockDetail()
    server.use(
      http.post(API('/crews/1/transfer/'), () =>
        fail(400, 'invalid', '입력을 확인해 주세요.', {
          user_id: ['활동 중인 크루원에게만 위임할 수 있어요.'],
        }),
      ),
    )
    const { user } = renderMembers()
    const [action] = await screen.findAllByRole('button', { name: '크루장 위임' })
    await user.click(action)
    await user.click(
      within(screen.getByRole('dialog', { name: /크루장을 넘길까요/ })).getByRole('button', {
        name: '위임하기',
      }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '활동 중인 크루원에게만 위임할 수 있어요.',
    )
    // 크루장은 그대로
    expect(within(headerSection()).getByRole('link', { name: '나' })).toBeInTheDocument()
  })

  it('tells the owner to transfer before leaving', async () => {
    mockDetail()
    renderMembers()
    await screen.findAllByRole('button', { name: '크루장 위임' })
    expect(screen.queryByRole('button', { name: '나가기' })).not.toBeInTheDocument()
    expect(screen.getByText(/크루장을 위임한 뒤 나갈 수 있어요/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '크루장 위임하기' })).toHaveAttribute(
      'href',
      '/crews/1?tab=members',
    )
  })
})
