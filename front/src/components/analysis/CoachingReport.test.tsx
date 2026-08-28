import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import CoachingReport from '@/components/analysis/CoachingReport'

const REPORT = `## 한눈에 보기
상승 높이 **42%**, 동적 무브 비율 35%.

## 잘한 점
- 무게중심이 벽에 가깝게 유지됐어요
- 발 놓기가 안정적이에요

## 개선 포인트
1. 팔꿈치를 더 펴 보세요
`

describe('CoachingReport', () => {
  it('renders headings as h2, bullets as li and bold as strong', () => {
    render(<CoachingReport markdown={REPORT} />)
    const headings = screen.getAllByRole('heading', { level: 2 })
    expect(headings.map((h) => h.textContent)).toEqual(['한눈에 보기', '잘한 점', '개선 포인트'])
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getByText('42%').tagName).toBe('STRONG')
  })

  it('never injects raw HTML from the model output', () => {
    const { container } = render(
      <CoachingReport
        markdown={'## 주의\n<script>window.pwned = 1</script>\n\n아래 <b>굵게</b> 참고 <img src=x onerror="alert(1)">'}
      />,
    )
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect(container.textContent).not.toContain('pwned')
    // 인라인 HTML 태그만 빠지고 글자는 남는다
    expect(screen.getByText(/아래 굵게 참고/)).toBeInTheDocument()
  })

  it('unwraps disallowed elements but keeps their text', () => {
    const { container } = render(
      <CoachingReport markdown={'[링크 글자](https://example.com) 와 `코드`\n\n| a | b |\n|---|---|\n| 1 | 2 |'} />,
    )
    expect(container.querySelector('a')).toBeNull()
    expect(container.querySelector('code')).toBeNull()
    expect(container.textContent).toContain('링크 글자')
    expect(container.textContent).toContain('코드')
  })
})
