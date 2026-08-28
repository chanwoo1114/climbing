/**
 * AnalysisPanel 의 "AI 코칭 리포트" 카드 — 분석이 done 인 기록에서 리포트 요청/폴링/표시.
 * 응답 본문은 백엔드 스키마(snake_case) 그대로 적는다.
 */
import { screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import AnalysisPanel from '@/components/analysis/AnalysisPanel'
import { ANALYSIS_POLL } from '@/hooks/useAnalysis'
import { useToastStore } from '@/stores/toastStore'
import { ME, renderWithProviders } from '@/test/render'
import { API, fail, http, ok, page, server } from '@/test/server'

const LOG = { id: 9, videoUrl: 'https://cdn.example.com/v.mp4' }

const REPORT = `## 한눈에 보기
상승 높이 **42%** 로 좋아요.

## 잘한 점
- 무게중심이 안정적이에요
- 정적 무브 비율이 높아요
<script>window.pwned = 1</script>
`

function analysis(over: Record<string, unknown> = {}) {
  return {
    id: 5,
    climb_log: LOG.id,
    status: 'done',
    error_message: '',
    metrics: {
      duration: 12.5,
      sample_fps: 10,
      frame_count: 125,
      detected_frames: 120,
      detection_rate: 0.96,
      com: null,
      joint_angles: {},
      move_ratio: null,
    },
    processed_at: '2026-08-01T03:00:00Z',
    retry_count: 0,
    created_at: '2026-08-01T02:00:00Z',
    updated_at: '2026-08-01T03:00:00Z',
    report_status: 'none',
    report: '',
    report_error: '',
    report_model: '',
    report_input_tokens: 0,
    report_output_tokens: 0,
    report_generated_at: null,
    ...over,
  }
}

function renderPanel(isOwner: boolean) {
  return renderWithProviders(<AnalysisPanel log={LOG} isOwner={isOwner} />, { user: ME })
}

const DEFAULT_INTERVAL = ANALYSIS_POLL.intervalMs

describe('AnalysisPanel — AI 코칭 리포트', () => {
  beforeEach(() => {
    // 가짜 타이머 대신 폴링 간격만 줄여서 실제로 두 번째 GET 이 나가는지 본다
    ANALYSIS_POLL.intervalMs = 20
  })
  afterEach(() => {
    ANALYSIS_POLL.intervalMs = DEFAULT_INTERVAL
    const store = useToastStore.getState()
    store.toasts.forEach((t) => store.dismiss(t.id))
  })

  it('none: owner sees the explainer and the create button', async () => {
    server.use(http.get(API('/analyses/'), () => page([analysis()])))
    renderPanel(true)
    expect(await screen.findByRole('heading', { name: 'AI 코칭 리포트' })).toBeInTheDocument()
    expect(screen.getByText(/AI 코치가 잘한 점과 개선 포인트를/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '리포트 만들기' })).toBeEnabled()
  })

  it('none: non-owner sees no report card at all', async () => {
    server.use(http.get(API('/analyses/'), () => page([analysis()])))
    renderPanel(false)
    // 결과 카드는 뜨지만 리포트 카드는 없다
    expect(await screen.findByText('자세 감지율')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'AI 코칭 리포트' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '리포트 만들기' })).not.toBeInTheDocument()
  })

  it('click → POST /analyses/5/report/ → status text, disabled button, and polling until done', async () => {
    let gets = 0
    let posts = 0
    server.use(
      http.get(API('/analyses/'), () => {
        gets += 1
        if (gets === 1) return page([analysis()])
        if (gets < 3) return page([analysis({ report_status: 'processing' })])
        return page([
          analysis({
            report_status: 'done',
            report: REPORT,
            report_model: 'claude-test',
            report_generated_at: '2026-08-02T05:06:00Z',
          }),
        ])
      }),
      http.post(API('/analyses/5/report/'), () => {
        posts += 1
        return ok(analysis({ report_status: 'pending' }), 202)
      }),
    )
    const { user } = renderPanel(true)

    await user.click(await screen.findByRole('button', { name: '리포트 만들기' }))

    // 202 응답이 캐시에 바로 들어가 "쓰고 있어요" 로 바뀐다
    const status = await screen.findByText(/AI 코치가 리포트를 쓰고 있어요/)
    expect(status.closest('[role="status"]')).not.toBeNull()
    expect(posts).toBe(1)
    expect(screen.getByRole('button', { name: '리포트 만들기' })).toBeDisabled()

    // 폴링이 이어지고(두 번째 GET), done 이 오면 본문이 그려진다
    await waitFor(() => expect(gets).toBeGreaterThanOrEqual(2))
    expect(await screen.findByRole('heading', { level: 2, name: '한눈에 보기' })).toBeInTheDocument()
    expect(screen.queryByText(/쓰고 있어요/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '다시 만들기' })).toBeEnabled()
  })

  it('done: renders markdown safely with the footer (date + model)', async () => {
    const generatedAt = '2026-08-02T05:06:00Z'
    server.use(
      http.get(API('/analyses/'), () =>
        page([
          analysis({
            report_status: 'done',
            report: REPORT,
            report_model: 'claude-test',
            report_generated_at: generatedAt,
          }),
        ]),
      ),
    )
    const { container } = renderPanel(false)

    expect(await screen.findByRole('heading', { level: 2, name: '한눈에 보기' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: '잘한 점' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('42%').tagName).toBe('STRONG')
    expect(container.querySelector('script')).toBeNull()
    expect(container.textContent).not.toContain('pwned')

    const expectedDate = new Intl.DateTimeFormat('ko-KR', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(generatedAt))
    const footer = screen.getByText(/^생성/)
    expect(footer.textContent).toContain(expectedDate)
    expect(footer.textContent).toContain('claude-test')
    // 남의 기록에는 다시 만들기 버튼이 없다
    expect(screen.queryByRole('button', { name: '다시 만들기' })).not.toBeInTheDocument()
  })

  it('failed: alert with the error and a retry button for the owner', async () => {
    server.use(
      http.get(API('/analyses/'), () =>
        page([analysis({ report_status: 'failed', report_error: '모델 응답이 비어 있습니다.' })]),
      ),
    )
    renderPanel(true)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('모델 응답이 비어 있습니다.')
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeEnabled()
  })

  it('503 coaching_not_configured: calm notice, button hidden, no toast', async () => {
    server.use(
      http.get(API('/analyses/'), () => page([analysis()])),
      http.post(API('/analyses/5/report/'), () =>
        fail(503, 'coaching_not_configured', '리포트 기능이 설정되지 않았습니다.'),
      ),
    )
    const { user } = renderPanel(true)
    await user.click(await screen.findByRole('button', { name: '리포트 만들기' }))

    expect(await screen.findByText(/리포트 기능이 아직 설정되지 않았어요/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '리포트 만들기' })).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('409 analysis_not_done: server message shows as a toast and the button stays', async () => {
    const message = '자세 분석이 완료된 뒤 리포트를 만들 수 있습니다.'
    server.use(
      http.get(API('/analyses/'), () => page([analysis()])),
      http.post(API('/analyses/5/report/'), () => fail(409, 'analysis_not_done', message)),
    )
    const { user } = renderPanel(true)
    await user.click(await screen.findByRole('button', { name: '리포트 만들기' }))

    await waitFor(() => expect(useToastStore.getState().toasts[0]?.title).toBe(message))
    expect(screen.getByRole('button', { name: '리포트 만들기' })).toBeEnabled()
  })
})
