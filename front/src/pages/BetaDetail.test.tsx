import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import BetaDetail from '@/pages/BetaDetail'
import { BETA, OTHERS_BETA } from '@/test/betaFixtures'
import { ME, renderWithProviders } from '@/test/render'
import { API, fail, http, ok, server } from '@/test/server'

function renderDetail(id: number, user = ME) {
  return renderWithProviders(<BetaDetail />, {
    route: `/betas/${id}`,
    path: '/betas/:betaId',
    user,
  })
}

describe('BetaDetail', () => {
  it('영상·제목·난이도·연결된 기록 링크를 보여준다', async () => {
    server.use(http.get(API('/betas/5/'), () => ok(BETA)))
    const { container } = renderDetail(5)
    expect(await screen.findByRole('heading', { name: '하이스텝 베타' })).toBeInTheDocument()
    const video = container.querySelector('video')
    expect(video).toHaveAttribute('src', BETA.video_url)
    expect(video).toHaveAttribute('controls')
    expect(screen.getByText('파랑')).toBeInTheDocument()
    expect(screen.getByText('조회 1,234')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /연결된 기록 보기/ })).toHaveAttribute('href', '/logs/3')
    expect(screen.getByRole('link', { name: '더클라임 강남' })).toHaveAttribute(
      'href',
      '/gyms/1?tab=betas',
    )
  })

  it('올린 사람에게는 수정·삭제가 보이고, 삭제 확인 뒤 암장 베타 탭으로 돌아간다', async () => {
    let deleted = false
    server.use(
      http.get(API('/betas/5/'), () => ok(BETA)),
      http.delete(API('/betas/5/'), () => {
        deleted = true
        return new Response(null, { status: 204 })
      }),
    )
    const { user } = renderDetail(5)
    await screen.findByRole('heading', { name: '하이스텝 베타' })
    expect(screen.getByRole('link', { name: '수정' })).toHaveAttribute('href', '/betas/5/edit')

    await user.click(screen.getByRole('button', { name: '삭제' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(deleted).toBe(true))
    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent('/gyms/1?tab=betas'),
    )
  })

  it('남의 베타에는 수정·삭제가 없다', async () => {
    server.use(http.get(API('/betas/6/'), () => ok(OTHERS_BETA)))
    renderDetail(6)
    await screen.findByRole('heading', { name: '남의 베타' })
    expect(screen.queryByRole('link', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /연결된 기록 보기/ })).not.toBeInTheDocument()
  })

  it('비로그인도 볼 수 있다', async () => {
    server.use(http.get(API('/betas/6/'), () => ok(OTHERS_BETA)))
    renderWithProviders(<BetaDetail />, { route: '/betas/6', path: '/betas/:betaId' })
    expect(await screen.findByRole('heading', { name: '남의 베타' })).toBeInTheDocument()
  })

  it('없는 베타는 찾을 수 없다고 안내한다', async () => {
    server.use(http.get(API('/betas/999/'), () => fail(404, 'http_404', '찾을 수 없습니다.')))
    renderDetail(999)
    expect(await screen.findByRole('alert')).toHaveTextContent('베타 영상을 찾을 수 없어요')
  })
})
