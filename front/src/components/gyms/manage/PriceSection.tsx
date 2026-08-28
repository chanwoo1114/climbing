import { useRef, useState } from 'react'

import { getErrorMessage } from '@/api/client'
import type { GymDetail, GymPrice } from '@/api/gyms'
import Button from '@/components/common/Button'
import TextField from '@/components/common/TextField'
import { Card, Empty, ErrorBanner, krw } from '@/components/gyms/manage/ManageBits'
import { useReplaceGymPrices } from '@/hooks/useGyms'
import { useToastStore } from '@/stores/toastStore'
import type { FieldCheck } from '@/lib/validation'

interface Row {
  /** 저장된 항목은 id, 새 행은 음수 임시 키 */
  key: number
  name: string
  price: string
  note: string
}

const fromPrices = (prices: GymPrice[]): Row[] =>
  prices.map((p) => ({ key: p.id, name: p.name, price: String(p.price), note: p.note }))

const isPrice = (value: string) =>
  value !== '' && Number.isInteger(Number(value)) && Number(value) >= 0

const invalid = (message: string): FieldCheck => ({ state: 'invalid', message })

/** 가격표 — 화면에서 행을 고치고 '저장' 한 번에 전체 목록을 PUT 한다 (빈 목록이면 모두 지움) */
export default function PriceSection({ gym }: { gym: GymDetail }) {
  const replace = useReplaceGymPrices(gym.id)
  const pushToast = useToastStore((s) => s.push)
  const [rows, setRows] = useState<Row[]>(() => fromPrices(gym.prices))
  const nextKey = useRef(-1)

  const edit = (key: number, patch: Partial<Row>) => {
    if (replace.isError) replace.reset()
    setRows((list) => list.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  }
  const addRow = () => {
    if (replace.isError) replace.reset()
    setRows((list) => [...list, { key: nextKey.current--, name: '', price: '', note: '' }])
  }
  const removeRow = (key: number) => {
    if (replace.isError) replace.reset()
    setRows((list) => list.filter((row) => row.key !== key))
  }

  const valid = rows.every((row) => row.name.trim().length > 0 && isPrice(row.price))
  const pending = replace.isPending

  const onSave = () => {
    if (!valid || pending) return
    replace.mutate(
      rows.map((row) => ({
        name: row.name.trim(),
        price: Number(row.price),
        note: row.note.trim(),
      })),
      {
        onSuccess: (saved) => {
          setRows(fromPrices(saved))
          pushToast({ title: '가격표를 저장했습니다.' })
        },
      },
    )
  }

  return (
    <Card id="manage-prices" title="가격" description="일일권, 회원권처럼 항목별로 적어 주세요. 단위는 원이에요.">
      {rows.length === 0 ? (
        <Empty>가격 항목이 없어요. 행을 추가하거나, 빈 채로 저장하면 가격표가 비워져요.</Empty>
      ) : (
        <ul className="space-y-3">
          {rows.map((row, index) => {
            const label = row.name.trim() || `${index + 1}번 항목`
            return (
              <li
                key={row.key}
                className="grid gap-3 rounded-xl border border-chalk-200 bg-chalk-50 p-3 sm:grid-cols-[minmax(0,1fr)_150px_minmax(0,1fr)_auto] sm:items-start"
              >
                <TextField
                  label="항목"
                  id={`price-${row.key}-name`}
                  name={`price-${row.key}-name`}
                  autoComplete="off"
                  placeholder="예) 1일 이용권"
                  maxLength={50}
                  required
                  value={row.name}
                  onChange={(e) => edit(row.key, { name: e.target.value })}
                  disabled={pending}
                />
                <div>
                  <TextField
                    label="가격 (원)"
                    id={`price-${row.key}-price`}
                    name={`price-${row.key}-price`}
                    type="number"
                    inputMode="numeric"
                    min={0}
                    step={1}
                    required
                    value={row.price}
                    check={
                      row.price !== '' && !isPrice(row.price)
                        ? invalid('0 이상의 정수로 적어 주세요.')
                        : undefined
                    }
                    onChange={(e) => edit(row.key, { price: e.target.value })}
                    disabled={pending}
                  />
                  {isPrice(row.price) && (
                    <p className="mt-1 text-xs text-ink-400 tabular-nums">
                      {krw.format(Number(row.price))}
                    </p>
                  )}
                </div>
                <TextField
                  label="메모 (선택)"
                  id={`price-${row.key}-note`}
                  name={`price-${row.key}-note`}
                  autoComplete="off"
                  placeholder="예) 암벽화 대여 포함"
                  maxLength={100}
                  value={row.note}
                  onChange={(e) => edit(row.key, { note: e.target.value })}
                  disabled={pending}
                />
                <div className="sm:pt-6">
                  <Button
                    variant="secondary"
                    aria-label={`${label} 삭제`}
                    onClick={() => removeRow(row.key)}
                    disabled={pending}
                  >
                    삭제
                  </Button>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {replace.isError && (
        <ErrorBanner>
          {getErrorMessage(replace.error, '가격표를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
        </ErrorBanner>
      )}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <Button variant="secondary" onClick={addRow} disabled={pending}>
          행 추가
        </Button>
        {/* 이 섹션의 유일한 primary CTA — 전체 목록을 한 번에 저장 */}
        <Button onClick={onSave} disabled={!valid || pending}>
          {pending ? '저장 중…' : '저장'}
        </Button>
      </div>
    </Card>
  )
}
