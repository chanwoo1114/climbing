import { useState, type FormEvent } from 'react'

import { getErrorMessage } from '@/api/client'
import type { GymDetail } from '@/api/gyms'
import Button from '@/components/common/Button'
import TextField from '@/components/common/TextField'
import { Card, Empty, ErrorBanner } from '@/components/gyms/manage/ManageBits'
import { useReplaceGymFacilities } from '@/hooks/useGyms'
import { useToastStore } from '@/stores/toastStore'

const FACILITY_MAX_LENGTH = 30

/** 편의시설 — 칩으로 넣고 빼다가 '저장' 한 번에 전체 목록을 PUT 한다 */
export default function FacilitySection({ gym }: { gym: GymDetail }) {
  const replace = useReplaceGymFacilities(gym.id)
  const pushToast = useToastStore((s) => s.push)
  const [names, setNames] = useState<string[]>(() => gym.facilities.map((f) => f.name))
  const [input, setInput] = useState('')

  const trimmed = input.trim()
  const duplicate = names.includes(trimmed)
  const canAdd = trimmed.length > 0 && !duplicate
  const pending = replace.isPending

  const onAdd = (e: FormEvent) => {
    e.preventDefault()
    if (!canAdd) return
    if (replace.isError) replace.reset()
    setNames((list) => [...list, trimmed])
    setInput('')
  }

  const onRemove = (name: string) => {
    if (replace.isError) replace.reset()
    setNames((list) => list.filter((n) => n !== name))
  }

  const onSave = () => {
    if (pending) return
    replace.mutate(
      names.map((name) => ({ name })),
      {
        onSuccess: (saved) => {
          setNames(saved.map((f) => f.name))
          pushToast({ title: '편의시설을 저장했습니다.' })
        },
      },
    )
  }

  return (
    <Card id="manage-facilities" title="편의시설" description="샤워실, 주차, 대여 같은 항목을 넣어 주세요.">
      {names.length === 0 ? (
        <Empty>편의시설이 없어요. 아래에서 추가해 보세요.</Empty>
      ) : (
        <ul aria-label="편의시설 목록" className="flex flex-wrap gap-2">
          {names.map((name) => (
            <li
              key={name}
              className="inline-flex items-center rounded-xl bg-chalk-100 pl-3 text-sm text-ink-600"
            >
              <span className="break-words">{name}</span>
              {/* 칩 안의 아이콘 버튼 — 44px 터치 영역 (Switch 와 같은 규칙) */}
              <button
                type="button"
                aria-label={`${name} 삭제`}
                onClick={() => onRemove(name)}
                disabled={pending}
                className="inline-flex size-11 items-center justify-center rounded-xl text-ink-400 transition-colors duration-150 hover:text-danger-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span aria-hidden>✕</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={onAdd} noValidate className="flex items-end gap-2">
        <div className="min-w-0 flex-1">
          <TextField
            label="편의시설 이름"
            id="facility-name"
            name="facility-name"
            autoComplete="off"
            placeholder="예) 샤워실"
            maxLength={FACILITY_MAX_LENGTH}
            value={input}
            check={duplicate ? { state: 'invalid', message: '이미 있는 항목이에요.' } : undefined}
            onChange={(e) => setInput(e.target.value)}
            disabled={pending}
          />
        </div>
        {/* TextField 의 메시지 줄만큼 아래 여백을 맞춘다 */}
        <div className="mb-5">
          <Button type="submit" variant="secondary" disabled={!canAdd || pending}>
            추가
          </Button>
        </div>
      </form>

      {replace.isError && (
        <ErrorBanner>
          {getErrorMessage(replace.error, '편의시설을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </ErrorBanner>
      )}

      <div className="flex justify-end">
        {/* 이 섹션의 유일한 primary CTA */}
        <Button onClick={onSave} disabled={pending}>
          {pending ? '저장 중…' : '저장'}
        </Button>
      </div>
    </Card>
  )
}
