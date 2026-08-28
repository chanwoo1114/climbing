import { screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import GymManage from '@/pages/GymManage'
import { useToastStore } from '@/stores/toastStore'
import { GYM } from '@/test/betaFixtures'
import { ME, renderWithProviders } from '@/test/render'
import { API, fail, http, ok, page, server } from '@/test/server'

const MANAGED_GYM = {
  ...GYM,
  is_manager: true,
  images: [
    { id: 1, image: 'https://cdn.test/gyms/1-a.jpg', order: 0 },
    { id: 2, image: 'https://cdn.test/gyms/1-b.jpg', order: 1 },
  ],
  prices: [{ id: 1, name: '1일권', price: 20000, note: '' }],
  facilities: [{ id: 1, name: '샤워실' }],
}

const MANAGERS = [
  {
    id: 1,
    user: { id: 1, nickname: '나', image: null },
    note: '',
    created_at: '2026-08-01T00:00:00Z',
  },
]

function renderManage(search = '') {
  return renderWithProviders(<GymManage />, {
    route: `/gyms/1/manage${search}`,
    path: '/gyms/:id/manage',
    user: ME,
  })
}

/** TextField 는 검증 상태가 생기면 label 안에 ✓/✕ 글자를 덧붙이므로 그걸 빼고 정확히 맞춘다 */
const labelMatcher = (label: string) => (text: string) =>
  text.replace(/[✓✕]\s*$/, '').trim() === label
const byLabel = (label: string) => screen.getByLabelText(labelMatcher(label))
const allByLabel = (label: string) => screen.getAllByLabelText(labelMatcher(label))

describe('GymManage', () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] })
    server.use(
      http.get(API('/gyms/1/'), () => ok(MANAGED_GYM)),
      http.get(API('/gyms/1/managers/'), () => ok(MANAGERS)),
    )
  })

  it('관리자가 아니면 안내만 보여주고 폼을 렌더하지 않는다', async () => {
    server.use(http.get(API('/gyms/1/'), () => ok({ ...MANAGED_GYM, is_manager: false })))
    renderManage()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('암장 관리자만 할 수 있습니다.')
    expect(within(alert).getByRole('link', { name: '암장 페이지로 돌아가기' })).toHaveAttribute(
      'href',
      '/gyms/1',
    )
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '관리 항목' })).not.toBeInTheDocument()
  })

  describe('기본 정보', () => {
    it('이름을 고쳐 저장하면 전체 필드를 PATCH 하고 토스트를 띄운다', async () => {
      let body: unknown = null
      server.use(
        http.patch(API('/gyms/1/'), async ({ request }) => {
          body = await request.json()
          return ok({ ...MANAGED_GYM, name: '더클라임 강남점' })
        }),
      )
      const { user } = renderManage()
      const name = await screen.findByLabelText(labelMatcher('암장 이름'))
      expect(screen.getByRole('link', { name: '기본 정보' })).toHaveAttribute('aria-current', 'page')
      await user.clear(name)
      await user.type(name, '더클라임 강남점')
      await user.click(screen.getByRole('button', { name: '저장' }))

      await waitFor(() =>
        expect(body).toEqual({
          name: '더클라임 강남점',
          description: '',
          address: '서울 강남구',
          phone: '',
          website: '',
        }),
      )
      await waitFor(() =>
        expect(useToastStore.getState().toasts[0]?.title).toBe('암장 정보를 저장했습니다.'),
      )
    })

    it('필드 오류(400 fields.website)는 해당 입력칸 아래에 보여준다', async () => {
      server.use(
        http.patch(API('/gyms/1/'), () =>
          fail(400, 'invalid', '입력을 확인해 주세요.', { website: ['올바른 URL 을 입력하세요.'] }),
        ),
      )
      const { user } = renderManage()
      await user.type(await screen.findByLabelText(labelMatcher('웹사이트')), 'not a url')
      await user.click(screen.getByRole('button', { name: '저장' }))

      expect(await screen.findByText('올바른 URL 을 입력하세요.')).toBeInTheDocument()
      expect(byLabel('웹사이트')).toHaveAttribute('aria-invalid', 'true')
      expect(useToastStore.getState().toasts).toHaveLength(0)
    })
  })

  describe('난이도', () => {
    it('추가 폼은 색을 소문자 hex 로 맞춰 POST 한다', async () => {
      let body: unknown = null
      server.use(
        http.post(API('/gyms/1/difficulties/'), async ({ request }) => {
          body = await request.json()
          return ok({ id: 12, name: '초록', color: '#16a34a', order: 3 }, 201)
        }),
      )
      const { user } = renderManage('?section=difficulties')
      // DB 값 그대로 렌더링 — 파랑 #1e40af
      const name = await screen.findByText('파랑')
      expect(name.closest('li')?.querySelector('[aria-hidden]')).toHaveStyle({
        backgroundColor: '#1e40af',
      })

      await user.type(byLabel('이름'), '초록')
      const hex = byLabel('색 (hex)')
      await user.clear(hex)
      await user.type(hex, '#16A34A')
      // 순서는 기존 최댓값 + 1 이 미리 채워져 있다
      expect(byLabel('순서')).toHaveValue(3)
      await user.click(screen.getByRole('button', { name: '추가' }))

      await waitFor(() => expect(body).toEqual({ name: '초록', color: '#16a34a', order: 3 }))
      await waitFor(() =>
        expect(useToastStore.getState().toasts[0]?.title).toBe("'초록' 난이도를 추가했습니다."),
      )
      // 폼은 이름만 비우고 순서는 다음 값으로 넘어간다
      expect(byLabel('이름')).toHaveValue('')
      expect(byLabel('순서')).toHaveValue(4)
    })

    it('삭제는 확인 모달을 거쳐 DELETE 한다', async () => {
      let deleted = false
      server.use(
        http.delete(API('/gyms/1/difficulties/10/'), () => {
          deleted = true
          return new Response(null, { status: 204 })
        }),
      )
      const { user } = renderManage('?section=difficulties')
      await user.click(await screen.findByRole('button', { name: '파랑 삭제' }))
      const dialog = screen.getByRole('dialog', { hidden: true, name: /'파랑' 난이도를 삭제할까요/ })
      expect(dialog).toHaveTextContent('이 난이도를 쓰는 기록은 그대로 남아요')
      expect(deleted).toBe(false)
      await user.click(within(dialog).getByRole('button', { name: '삭제' }))
      await waitFor(() => expect(deleted).toBe(true))
    })
  })

  describe('사진', () => {
    it('"아래로" 를 누르면 바뀐 순서의 id 전체를 PUT 한다', async () => {
      let body: unknown = null
      server.use(
        http.put(API('/gyms/1/images/order/'), async ({ request }) => {
          body = await request.json()
          return ok([
            { id: 2, image: 'https://cdn.test/gyms/1-b.jpg', order: 0 },
            { id: 1, image: 'https://cdn.test/gyms/1-a.jpg', order: 1 },
          ])
        }),
      )
      const { user } = renderManage('?section=images')
      const down = await screen.findAllByRole('button', { name: '아래로' })
      expect(down).toHaveLength(2)
      expect(down[1]).toBeDisabled()
      expect(screen.getAllByRole('button', { name: '위로' })[0]).toBeDisabled()
      await user.click(down[0]!)
      await waitFor(() => expect(body).toEqual({ ids: [2, 1] }))
    })
  })

  describe('가격', () => {
    it('행을 추가해 저장하면 전체 목록을 PUT 하고 미리보기는 원화로 보여준다', async () => {
      let body: unknown = null
      server.use(
        http.put(API('/gyms/1/prices/'), async ({ request }) => {
          body = await request.json()
          return ok([
            { id: 1, name: '1일권', price: 20000, note: '' },
            { id: 2, name: '월 회원권', price: 150000, note: '락커 포함' },
          ])
        }),
      )
      const { user } = renderManage('?section=prices')
      await screen.findByDisplayValue('1일권')
      expect(screen.getByText('₩20,000')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: '행 추가' }))
      await user.type(allByLabel('항목')[1]!, '월 회원권')
      await user.type(allByLabel('가격 (원)')[1]!, '150000')
      await user.type(allByLabel('메모 (선택)')[1]!, '락커 포함')
      expect(screen.getByText('₩150,000')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: '저장' }))

      await waitFor(() =>
        expect(body).toEqual([
          { name: '1일권', price: 20000, note: '' },
          { name: '월 회원권', price: 150000, note: '락커 포함' },
        ]),
      )
      expect(await screen.findByText('₩150,000')).toBeInTheDocument()
      expect(useToastStore.getState().toasts[0]?.title).toBe('가격표를 저장했습니다.')
    })

    it('행을 모두 지우고 저장하면 빈 목록을 PUT 한다', async () => {
      let body: unknown = null
      server.use(
        http.put(API('/gyms/1/prices/'), async ({ request }) => {
          body = await request.json()
          return ok([])
        }),
      )
      const { user } = renderManage('?section=prices')
      await user.click(await screen.findByRole('button', { name: '1일권 삭제' }))
      expect(screen.getByText(/가격 항목이 없어요/)).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: '저장' }))
      await waitFor(() => expect(body).toEqual([]))
    })
  })

  describe('편의시설', () => {
    it('칩을 넣고 빼서 저장하면 전체 목록을 PUT 한다', async () => {
      let body: unknown = null
      server.use(
        http.put(API('/gyms/1/facilities/'), async ({ request }) => {
          body = await request.json()
          return ok([{ id: 2, name: '주차' }])
        }),
      )
      const { user } = renderManage('?section=facilities')
      await user.type(await screen.findByLabelText(labelMatcher('편의시설 이름')), '주차')
      await user.click(screen.getByRole('button', { name: '추가' }))
      expect(within(screen.getByRole('list', { name: '편의시설 목록' })).getByText('주차')).toBeInTheDocument()
      expect(byLabel('편의시설 이름')).toHaveValue('')

      await user.click(screen.getByRole('button', { name: '샤워실 삭제' }))
      expect(screen.queryByText('샤워실')).not.toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: '저장' }))

      await waitFor(() => expect(body).toEqual([{ name: '주차' }]))
      expect(useToastStore.getState().toasts[0]?.title).toBe('편의시설을 저장했습니다.')
    })
  })

  describe('관리자', () => {
    it('닉네임을 검색해 고른 회원을 POST 한다', async () => {
      let body: unknown = null
      server.use(
        http.get(API('/users/search/'), ({ request }) => {
          const q = new URL(request.url).searchParams.get('q')
          return page(q === '홍' ? [{ id: 2, nickname: '홍길동', image: null, is_following: false }] : [])
        }),
        http.post(API('/gyms/1/managers/'), async ({ request }) => {
          body = await request.json()
          return ok(
            {
              id: 2,
              user: { id: 2, nickname: '홍길동', image: null },
              note: '점장',
              created_at: '2026-08-28T00:00:00Z',
            },
            201,
          )
        }),
      )
      const { user } = renderManage('?section=managers')
      // Avatar 의 첫 글자도 '나' 라 닉네임 <p> 로 좁힌다
      expect(await screen.findByText('나', { selector: 'p' })).toBeInTheDocument()
      await user.type(byLabel('닉네임 검색'), '홍')
      await user.click(await screen.findByRole('button', { name: '홍길동 선택' }))
      await user.type(byLabel('메모 (선택)'), '점장')
      await user.click(screen.getByRole('button', { name: '관리자로 추가' }))

      await waitFor(() => expect(body).toEqual({ user_id: 2, note: '점장' }))
      expect(useToastStore.getState().toasts[0]?.title).toBe("'홍길동' 님을 관리자로 추가했습니다.")
      // 폼은 검색 단계로 돌아간다
      expect(byLabel('닉네임 검색')).toHaveValue('')
    })

    it('마지막 관리자를 지우려 하면(409 last_manager) 서버 메시지를 alert 로 보여준다', async () => {
      server.use(
        http.delete(API('/gyms/1/managers/1/'), () =>
          fail(409, 'last_manager', '마지막 관리자는 삭제할 수 없습니다.'),
        ),
      )
      const { user } = renderManage('?section=managers')
      await user.click(await screen.findByRole('button', { name: '나 삭제' }))
      const dialog = screen.getByRole('dialog', { hidden: true, name: /'나' 님을 관리자에서 뺄까요/ })
      await user.click(within(dialog).getByRole('button', { name: '삭제' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('마지막 관리자는 삭제할 수 없습니다.')
      // 목록은 그대로
      expect(screen.getByText('나', { selector: 'p' })).toBeInTheDocument()
    })
  })
})
