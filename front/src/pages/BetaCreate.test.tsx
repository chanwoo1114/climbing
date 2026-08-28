import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import BetaCreate from '@/pages/BetaCreate'
import { BETA, GYM } from '@/test/betaFixtures'
import { ME, renderWithProviders } from '@/test/render'
import { API, http, ok, page, server } from '@/test/server'

// presigned 발급 + S3 PUT 은 서버를 거치지 않는 흐름이라 API 모듈 단에서 흉내낸다.
// (kind 별로 다른 fileUrl 을 돌려줘 영상/썸네일이 제 자리에 들어가는지 본다)
vi.mock('@/api/uploads', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/uploads')>()
  return {
    ...actual,
    requestPresignedUpload: vi.fn(async ({ kind }: { kind: string }) => ({
      uploadUrl: `https://s3.test/${kind}`,
      method: 'PUT' as const,
      headers: {},
      fileUrl: `https://cdn.test/${kind}/file`,
      key: `${kind}/file`,
      expiresIn: 600,
      maxBytes: 200 * 1024 * 1024,
    })),
    putFileToPresignedUrl: vi.fn(async () => undefined),
  }
})

const MY_LOG = {
  id: 3,
  user: { id: 1, nickname: '나', image: null },
  gym: { id: 1, name: '더클라임 강남' },
  difficulty: { id: 10, name: '파랑', color: '#1e40af' },
  is_success: true,
  attempts: 2,
  memo: '',
  video_url: '',
  climbed_at: '2026-08-20',
  is_shared: true,
  like_count: 0,
  comment_count: 0,
  is_liked: false,
  created_at: '2026-08-20T10:00:00Z',
}

describe('BetaCreate', () => {
  beforeEach(() => {
    server.use(
      http.get(API('/gyms/1/'), () => ok(GYM)),
      http.get(API('/gyms/1/betas/sectors/'), () => ok([{ sector: 'A벽', count: 3 }])),
      http.get(API('/logs/'), ({ request }) => {
        expect(new URL(request.url).searchParams.get('gym')).toBe('1')
        return page([MY_LOG], null)
      }),
    )
  })

  describe('생성', () => {
    const renderCreate = () =>
      renderWithProviders(<BetaCreate />, {
        route: '/gyms/1/betas/new',
        path: '/gyms/:gymId/betas/new',
        user: ME,
      })

    it('제목과 영상이 있어야 올릴 수 있다', async () => {
      const { user } = renderCreate()
      const submit = await screen.findByRole('button', { name: '베타 올리기' })
      expect(submit).toBeDisabled()

      await user.type(screen.getByLabelText('제목'), '하이스텝 베타')
      expect(submit).toBeDisabled() // 영상이 아직 없다

      const file = new File(['video'], 'beta.mp4', { type: 'video/mp4' })
      await user.upload(screen.getByLabelText('영상 (필수)'), file)
      expect(await screen.findByText('beta.mp4')).toBeInTheDocument()
      expect(submit).toBeEnabled()

      await user.clear(screen.getByLabelText('제목'))
      expect(submit).toBeDisabled() // 제목이 비면 다시 막힌다
    })

    it('올리면 기대한 본문으로 POST 하고 상세로 간다', async () => {
      let body: Record<string, unknown> | null = null
      server.use(
        http.post(API('/gyms/1/betas/'), async ({ request }) => {
          body = (await request.json()) as Record<string, unknown>
          return ok({ ...BETA, id: 42 }, 201)
        }),
      )
      const { user } = renderCreate()
      await user.type(await screen.findByLabelText('제목'), '하이스텝 베타')
      await user.type(screen.getByLabelText('섹터 (선택)'), 'A벽')
      await user.selectOptions(screen.getByLabelText(/난이도 \(선택\)/), '10')
      await user.type(screen.getByLabelText('설명 (선택)'), '오른발 하이스텝')
      await user.upload(
        screen.getByLabelText('영상 (필수)'),
        new File(['video'], 'beta.mp4', { type: 'video/mp4' }),
      )
      await user.upload(
        screen.getByLabelText('썸네일 (선택)'),
        new File(['img'], 'thumb.png', { type: 'image/png' }),
      )
      await screen.findByText('thumb.png')
      await user.selectOptions(await screen.findByLabelText(/내 기록 연결 \(선택\)/), '3')

      await user.click(screen.getByRole('button', { name: '베타 올리기' }))

      await waitFor(() => expect(body).not.toBeNull())
      expect(body).toEqual({
        title: '하이스텝 베타',
        sector: 'A벽',
        difficulty: 10,
        description: '오른발 하이스텝',
        video_url: 'https://cdn.test/beta_video/file',
        thumbnail_url: 'https://cdn.test/beta_thumbnail/file',
        climb_log: 3,
      })
      await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/betas/42'))
    })
  })

  describe('수정', () => {
    const renderEdit = () =>
      renderWithProviders(<BetaCreate />, {
        route: '/betas/5/edit',
        path: '/betas/:betaId/edit',
        user: ME,
      })

    it('영상 필드 대신 안내를 보여주고, PATCH 본문에 video_url 을 싣지 않는다', async () => {
      let body: Record<string, unknown> | null = null
      server.use(
        http.get(API('/betas/5/'), () => ok(BETA)),
        http.patch(API('/betas/5/'), async ({ request }) => {
          body = (await request.json()) as Record<string, unknown>
          return ok({ ...BETA, title: '하이스텝 베타 v2' })
        }),
      )
      const { user } = renderEdit()
      expect(await screen.findByText(/영상은 바꿀 수 없어요/)).toBeInTheDocument()
      expect(screen.queryByLabelText('영상 (필수)')).not.toBeInTheDocument()
      expect(screen.getByLabelText('제목')).toHaveValue('하이스텝 베타')

      await user.type(screen.getByLabelText('제목'), ' v2')
      await user.click(screen.getByRole('button', { name: '저장' }))

      await waitFor(() => expect(body).not.toBeNull())
      expect(body).not.toHaveProperty('video_url')
      expect(body).toMatchObject({ title: '하이스텝 베타 v2', sector: 'A벽', climb_log: 3 })
      await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/betas/5'))
    })

    it('남의 베타는 수정할 수 없다', async () => {
      server.use(
        http.get(API('/betas/5/'), () =>
          ok({ ...BETA, user: { id: 2, nickname: '남', image: null }, is_mine: false }),
        ),
      )
      renderEdit()
      expect(await screen.findByRole('alert')).toHaveTextContent('본인이 올린 베타만 수정할 수 있어요')
    })
  })
})
