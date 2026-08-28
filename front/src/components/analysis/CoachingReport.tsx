import Markdown, { type Components } from 'react-markdown'

/**
 * AI 코칭 리포트 본문 — 서버가 주는 한국어 마크다운(## 제목, 글머리표, **강조**)을 렌더링한다.
 * 허용 목록 밖의 요소(링크·이미지·표·코드 등)는 태그만 벗기고 글자는 남기며(unwrapDisallowed),
 * 원문 HTML 은 통째로 버린다(skipHtml) — 모델 출력이 화면에 스크립트를 심을 수 없게.
 */
const ALLOWED_ELEMENTS = ['h1', 'h2', 'h3', 'h4', 'p', 'ul', 'ol', 'li', 'strong', 'em', 'br']

const components: Components = {
  // 리포트는 h2 섹션으로만 구성되니 그 위/아래 수준도 같은 두 단계로 접는다
  h1: ({ children }) => <h2 className="mt-5 mb-2 text-base font-semibold text-ink-700">{children}</h2>,
  h2: ({ children }) => <h2 className="mt-5 mb-2 text-base font-semibold text-ink-700">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-4 mb-1 text-sm font-semibold text-ink-700">{children}</h3>,
  h4: ({ children }) => <h3 className="mt-4 mb-1 text-sm font-semibold text-ink-700">{children}</h3>,
  p: ({ children }) => <p className="text-pretty">{children}</p>,
  ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
  li: ({ children }) => <li className="text-pretty">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-ink-700">{children}</strong>,
  em: ({ children }) => <em>{children}</em>,
}

interface Props {
  markdown: string
}

export default function CoachingReport({ markdown }: Props) {
  return (
    <div className="space-y-2 text-sm leading-relaxed break-words text-ink-600 [&>h2:first-child]:mt-0">
      <Markdown
        allowedElements={ALLOWED_ELEMENTS}
        unwrapDisallowed
        skipHtml
        components={components}
      >
        {markdown}
      </Markdown>
    </div>
  )
}
