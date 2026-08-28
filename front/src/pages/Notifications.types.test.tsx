import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import Notifications from '@/pages/Notifications'
import { ME, renderWithProviders } from '@/test/render'
import { API, http, ok, page, server } from '@/test/server'

const ITEMS = [
  {
    id: 1,
    type: 'crew_owner',
    actor: null,
    target_type: 'crew',
    target_id: 2,
    message: '초크팀 크루의 크루장이 되었어요',
    is_read: false,
    created_at: '2026-08-28T00:00:00Z',
  },
  {
    id: 2,
    type: 'analysis_done',
    actor: null,
    target_type: 'climb_log',
    target_id: 3,
    message: '자세 분석이 끝났어요',
    is_read: true,
    created_at: '2026-08-28T00:00:00Z',
  },
  {
    id: 3,
    type: 'analysis_failed',
    actor: null,
    target_type: 'climb_log',
    target_id: 3,
    message: '자세 분석에 실패했어요',
    is_read: true,
    created_at: '2026-08-28T00:00:00Z',
  },
  {
    id: 4,
    type: 'report_done',
    actor: null,
    target_type: 'climb_log',
    target_id: 3,
    message: '분석 리포트가 준비됐어요',
    is_read: true,
    created_at: '2026-08-28T00:00:00Z',
  },
  {
    id: 5,
    type: 'report_failed',
    actor: null,
    target_type: 'climb_log',
    target_id: 3,
    message: '리포트 생성에 실패했어요',
    is_read: true,
    created_at: '2026-08-28T00:00:00Z',
  },
  {
    id: 6,
    type: 'something_new',
    actor: null,
    target_type: 'post',
    target_id: 9,
    message: '아직 모르는 종류의 알림',
    is_read: true,
    created_at: '2026-08-28T00:00:00Z',
  },
]

describe('Notifications new types', () => {
  it('renders labels for the new types and links to their targets', async () => {
    server.use(
      http.get(API('/notifications/'), () => page(ITEMS)),
      http.get(API('/notifications/unread-count/'), () => ok({ count: 1 })),
    )
    renderWithProviders(<Notifications />, { route: '/notifications', user: ME })

    expect(await screen.findByText('크루장 위임')).toBeInTheDocument()
    expect(screen.getByText('분석 완료')).toBeInTheDocument()
    expect(screen.getByText('분석 실패')).toBeInTheDocument()
    expect(screen.getByText('리포트 완료')).toBeInTheDocument()
    expect(screen.getByText('리포트 실패')).toBeInTheDocument()

    const linkOf = (message: string) => screen.getByText(message).closest('a')
    expect(linkOf('초크팀 크루의 크루장이 되었어요')).toHaveAttribute('href', '/crews/2')
    expect(linkOf('자세 분석이 끝났어요')).toHaveAttribute('href', '/logs/3')
    expect(linkOf('자세 분석에 실패했어요')).toHaveAttribute('href', '/logs/3')
    expect(linkOf('분석 리포트가 준비됐어요')).toHaveAttribute('href', '/logs/3')
    expect(linkOf('리포트 생성에 실패했어요')).toHaveAttribute('href', '/logs/3')

    // 모르는 type 도 기본 라벨로 렌더된다
    expect(linkOf('아직 모르는 종류의 알림')).toHaveAttribute('href', '/posts/9')
    expect(screen.getByText('알림', { selector: 'p > span' })).toBeInTheDocument()
  })
})
