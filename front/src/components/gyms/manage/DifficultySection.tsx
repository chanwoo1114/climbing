import { useState, type FormEvent } from 'react'

import { getErrorMessage, getFieldError } from '@/api/client'
import type { GymDetail, GymDifficulty } from '@/api/gyms'
import Button from '@/components/common/Button'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import TextField from '@/components/common/TextField'
import { Card, Empty, ErrorBanner } from '@/components/gyms/manage/ManageBits'
import { useCreateDifficulty, useDeleteDifficulty, useUpdateDifficulty } from '@/hooks/useGyms'
import { useToastStore } from '@/stores/toastStore'
import type { FieldCheck } from '@/lib/validation'

/** 서버가 받는 색 형식 — "#rrggbb" */
const HEX = /^#[0-9a-f]{6}$/i
const normalizeHex = (value: string) => value.trim().toLowerCase()
const isOrder = (value: string) => value !== '' && Number.isInteger(Number(value)) && Number(value) >= 0

const invalid = (message: string): FieldCheck => ({ state: 'invalid', message })

interface Values {
  name: string
  color: string
  order: string
}

/** 난이도 — 색은 토큰이 아니라 암장이 정한 값(GymDifficulty.color)을 그대로 그린다 */
export default function DifficultySection({ gym }: { gym: GymDetail }) {
  const difficulties = [...gym.difficulties].sort((a, b) => a.order - b.order)
  const nextOrder = difficulties.reduce((max, d) => Math.max(max, d.order), 0) + 1

  return (
    <Card
      id="manage-difficulties"
      title="난이도"
      description="기록·베타 작성 폼의 난이도 선택지가 돼요. 순서가 낮을수록 먼저 보여요."
    >
      {difficulties.length === 0 ? (
        <Empty>등록된 난이도가 없어요. 아래에서 추가해 보세요.</Empty>
      ) : (
        <ul className="divide-y divide-chalk-200">
          {difficulties.map((difficulty) => (
            <DifficultyRow key={difficulty.id} gymId={gym.id} difficulty={difficulty} />
          ))}
        </ul>
      )}
      <AddDifficultyForm gymId={gym.id} nextOrder={nextOrder} />
    </Card>
  )
}

/**
 * 이름·색·순서 입력 묶음. 색은 color picker 와 hex 텍스트가 같은 값을 본다 —
 * picker 는 유효한 hex 만 보여줄 수 있어 텍스트가 깨진 동안엔 검정으로 둔다.
 */
function DifficultyFields({
  idPrefix,
  values,
  onChange,
  error,
  disabled,
}: {
  idPrefix: string
  values: Values
  onChange: (next: Partial<Values>) => void
  error: unknown
  disabled: boolean
}) {
  const server = (field: string) => getFieldError(error, field)
  const nameCheck = server('name') ? invalid(server('name')!) : undefined
  const colorCheck = server('color')
    ? invalid(server('color')!)
    : values.color !== '' && !HEX.test(values.color)
      ? invalid('#rrggbb 형식으로 적어 주세요.')
      : undefined
  const orderCheck = server('order')
    ? invalid(server('order')!)
    : values.order !== '' && !isOrder(values.order)
      ? invalid('0 이상의 정수로 적어 주세요.')
      : undefined

  return (
    <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_96px] sm:items-start">
      <TextField
        label="이름"
        id={`${idPrefix}-name`}
        name={`${idPrefix}-name`}
        autoComplete="off"
        placeholder="예) 파랑"
        maxLength={20}
        required
        value={values.name}
        check={nameCheck}
        onChange={(e) => onChange({ name: e.target.value })}
        disabled={disabled}
      />
      <div>
        <span className="mb-1 block text-sm font-medium text-ink-500">색</span>
        <input
          type="color"
          aria-label="색 고르기"
          value={HEX.test(values.color) ? normalizeHex(values.color) : '#000000'}
          onChange={(e) => onChange({ color: e.target.value })}
          disabled={disabled}
          className="block size-11 cursor-pointer rounded-xl border border-chalk-300 bg-white p-1 disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>
      <TextField
        label="색 (hex)"
        id={`${idPrefix}-color`}
        name={`${idPrefix}-color`}
        autoComplete="off"
        spellCheck={false}
        autoCapitalize="none"
        placeholder="#1e40af"
        maxLength={7}
        required
        value={values.color}
        check={colorCheck}
        onChange={(e) => onChange({ color: e.target.value })}
        disabled={disabled}
      />
      <TextField
        label="순서"
        id={`${idPrefix}-order`}
        name={`${idPrefix}-order`}
        type="number"
        inputMode="numeric"
        min={0}
        step={1}
        required
        value={values.order}
        check={orderCheck}
        onChange={(e) => onChange({ order: e.target.value })}
        disabled={disabled}
      />
    </div>
  )
}

const isValid = (values: Values) =>
  values.name.trim().length > 0 && HEX.test(values.color) && isOrder(values.order)

function DifficultyRow({ gymId, difficulty }: { gymId: number; difficulty: GymDifficulty }) {
  const update = useUpdateDifficulty(gymId)
  const remove = useDeleteDifficulty(gymId)
  const [editing, setEditing] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [values, setValues] = useState<Values>({
    name: difficulty.name,
    color: difficulty.color,
    order: String(difficulty.order),
  })

  const startEdit = () => {
    setValues({ name: difficulty.name, color: difficulty.color, order: String(difficulty.order) })
    update.reset()
    setEditing(true)
  }

  const onSave = (e: FormEvent) => {
    e.preventDefault()
    if (!isValid(values) || update.isPending) return
    update.mutate(
      {
        difficultyId: difficulty.id,
        name: values.name.trim(),
        color: normalizeHex(values.color),
        order: Number(values.order),
      },
      { onSuccess: () => setEditing(false) },
    )
  }

  const onDelete = () => {
    remove.mutate(difficulty.id, { onSettled: () => setConfirm(false) })
  }

  const updateFieldError = ['name', 'color', 'order'].some((f) => getFieldError(update.error, f))
  const updateError =
    update.error && !updateFieldError
      ? getErrorMessage(update.error, '난이도를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      : null

  return (
    <li className="py-3">
      {editing ? (
        <form onSubmit={onSave} noValidate className="space-y-3">
          <DifficultyFields
            idPrefix={`difficulty-${difficulty.id}`}
            values={values}
            onChange={(next) => {
              if (update.isError) update.reset()
              setValues((v) => ({ ...v, ...next }))
            }}
            error={update.error}
            disabled={update.isPending}
          />
          {updateError && <ErrorBanner>{updateError}</ErrorBanner>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setEditing(false)} disabled={update.isPending}>
              취소
            </Button>
            {/* 섹션의 primary 는 아래 '추가' 하나 — 행 저장은 secondary */}
            <Button
              type="submit"
              variant="secondary"
              disabled={!isValid(values) || update.isPending}
            >
              {update.isPending ? '저장 중…' : '저장'}
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="size-6 shrink-0 rounded-full border border-chalk-400"
            style={{ backgroundColor: difficulty.color }}
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink-700">{difficulty.name}</p>
            <p className="text-xs text-ink-400">
              <span className="tabular-nums">순서 {difficulty.order}</span>
              <span aria-hidden> · </span>
              <span className="font-mono">{difficulty.color}</span>
            </p>
          </div>
          <div className="flex shrink-0 gap-1">
            <Button
              variant="secondary"
              aria-label={`${difficulty.name} 수정`}
              onClick={startEdit}
              disabled={remove.isPending}
            >
              수정
            </Button>
            <Button
              variant="secondary"
              aria-label={`${difficulty.name} 삭제`}
              onClick={() => {
                remove.reset()
                setConfirm(true)
              }}
              disabled={remove.isPending}
            >
              삭제
            </Button>
          </div>
        </div>
      )}
      {remove.isError && (
        <div className="mt-2">
          <ErrorBanner>
            {getErrorMessage(remove.error, '난이도를 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')}
          </ErrorBanner>
        </div>
      )}
      <ConfirmDialog
        open={confirm}
        title={`'${difficulty.name}' 난이도를 삭제할까요?`}
        description="이 난이도를 쓰는 기록은 그대로 남아요. 새 기록에서만 고를 수 없게 돼요."
        confirmLabel="삭제"
        pendingLabel="삭제 중…"
        pending={remove.isPending}
        onConfirm={onDelete}
        onCancel={() => setConfirm(false)}
      />
    </li>
  )
}

function AddDifficultyForm({ gymId, nextOrder }: { gymId: number; nextOrder: number }) {
  const create = useCreateDifficulty(gymId)
  const pushToast = useToastStore((s) => s.push)
  const [values, setValues] = useState<Values>({
    name: '',
    color: '#1e40af',
    order: String(nextOrder),
  })

  const fieldError = ['name', 'color', 'order'].some((f) => getFieldError(create.error, f))
  const generalError =
    create.error && !fieldError
      ? getErrorMessage(create.error, '난이도를 추가하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      : null

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!isValid(values) || create.isPending) return
    create.mutate(
      { name: values.name.trim(), color: normalizeHex(values.color), order: Number(values.order) },
      {
        onSuccess: (created) => {
          setValues((v) => ({ ...v, name: '', order: String(created.order + 1) }))
          pushToast({ title: `'${created.name}' 난이도를 추가했습니다.` })
        },
      },
    )
  }

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      aria-labelledby="add-difficulty-heading"
      className="space-y-3 border-t border-chalk-200 pt-4"
    >
      <h3 id="add-difficulty-heading" className="text-sm font-semibold text-ink-700">
        난이도 추가
      </h3>
      <DifficultyFields
        idPrefix="difficulty-new"
        values={values}
        onChange={(next) => {
          if (create.isError) create.reset()
          setValues((v) => ({ ...v, ...next }))
        }}
        error={create.error}
        disabled={create.isPending}
      />
      {generalError && <ErrorBanner>{generalError}</ErrorBanner>}
      <div className="flex justify-end">
        {/* 이 섹션의 유일한 primary CTA */}
        <Button type="submit" disabled={!isValid(values) || create.isPending}>
          {create.isPending ? '추가 중…' : '추가'}
        </Button>
      </div>
    </form>
  )
}
