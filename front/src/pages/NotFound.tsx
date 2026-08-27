import { Link, isRouteErrorResponse, useRouteError } from 'react-router'

import Button from '@/components/common/Button'

const HOME_LINK =
  'mt-4 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline'

/**
 * 두 자리에서 쓴다.
 * - path '*' 의 element: 없는 주소 → 404 안내
 * - 라우트 errorElement: 렌더 중 던져진 Response(404) 는 같은 안내, 그 밖의 오류는 "문제가 생겼어요"
 */
export default function NotFound() {
  const error = useRouteError()
  const notFound =
    error === undefined || error === null || (isRouteErrorResponse(error) && error.status === 404)

  if (notFound) {
    return (
      <div className="py-16 text-center">
        <p aria-hidden className="text-5xl font-semibold text-chalk-400 tabular-nums">
          404
        </p>
        <h1 className="mt-2 text-xl font-semibold text-ink-700">페이지를 찾을 수 없어요</h1>
        <p className="mt-1 text-sm text-pretty text-ink-400">
          주소가 잘못됐거나 사라진 페이지예요.
        </p>
        <Link to="/" className={HOME_LINK}>
          지도로 돌아가기
        </Link>
      </div>
    )
  }

  const detail = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : ''

  return (
    <div role="alert" className="py-16 text-center">
      <h1 className="text-xl font-semibold text-ink-700">문제가 생겼어요</h1>
      <p className="mt-1 text-sm text-pretty text-ink-400">
        잠시 후 다시 시도해 주세요. 계속되면 새로고침해 보세요.
      </p>
      {detail && <p className="mt-2 text-xs break-words text-ink-300">{detail}</p>}
      <div className="mt-4 flex items-center justify-center gap-2">
        <Button variant="secondary" onClick={() => window.location.reload()}>
          다시 시도
        </Button>
        <Link to="/" className={`${HOME_LINK} mt-0`}>
          지도로 돌아가기
        </Link>
      </div>
    </div>
  )
}
