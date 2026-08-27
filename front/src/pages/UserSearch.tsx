import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'

import { getErrorMessage } from '@/api/client'
import Button from '@/components/common/Button'
import TextField from '@/components/common/TextField'
import UserList from '@/components/users/UserList'
import { useSearchUsers } from '@/hooks/useUsers'

const DEBOUNCE_MS = 300

/**
 * 닉네임 검색. 입력은 로컬 상태, 300ms 뒤 ?q= 에 반영하고 쿼리는 URL 값으로 돈다 —
 * 새로고침·뒤로가기·공유해도 같은 결과가 뜬다.
 */
export default function UserSearch() {
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q')?.trim() ?? ''
  const [input, setInput] = useState(q)
  const results = useSearchUsers(q)
  const users = results.data?.pages.flatMap((page) => page.results) ?? []

  // 입력 → URL (디바운스)
  useEffect(() => {
    const next = input.trim()
    if (next === q) return
    const timer = setTimeout(() => {
      setSearchParams(next ? { q: next } : {}, { replace: true })
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [input, q, setSearchParams])

  // URL → 입력 (뒤로가기 등으로 바깥에서 바뀐 경우만)
  useEffect(() => {
    setInput((current) => (current.trim() === q ? current : q))
  }, [q])

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-4 text-2xl font-semibold text-ink-700">클라이머 검색</h1>
      <form role="search" onSubmit={(e) => e.preventDefault()} noValidate>
        <TextField
          label="닉네임"
          name="q"
          type="search"
          autoFocus
          autoComplete="off"
          spellCheck={false}
          placeholder="닉네임을 입력하세요"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
      </form>

      <div className="mt-4">
        {!q && (
          <p className="py-10 text-center text-sm text-pretty text-ink-400">
            닉네임으로 클라이머를 찾아보세요
          </p>
        )}

        {q && results.isPending && (
          <p role="status" className="py-10 text-center text-sm text-ink-400">
            검색 중…
          </p>
        )}

        {results.isError && (
          <div role="alert" className="py-10 text-center">
            <p className="text-sm text-pretty text-danger-500">
              {getErrorMessage(results.error, '검색에 실패했습니다. 잠시 후 다시 시도해 주세요.')}
            </p>
            <Button variant="secondary" className="mt-3" onClick={() => results.refetch()}>
              다시 시도
            </Button>
          </div>
        )}

        {q && results.data && users.length === 0 && (
          <div
            role="status"
            className="rounded-card border border-chalk-300 bg-white p-8 text-center"
          >
            <p className="text-sm font-medium text-pretty break-words text-ink-600">
              '{q}'에 해당하는 클라이머가 없어요
            </p>
          </div>
        )}

        {users.length > 0 && <UserList users={users} />}

        {results.hasNextPage && (
          <div className="mt-3">
            <Button
              variant="secondary"
              full
              onClick={() => results.fetchNextPage()}
              disabled={results.isFetchingNextPage}
            >
              {results.isFetchingNextPage ? '불러오는 중…' : '더 보기'}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
