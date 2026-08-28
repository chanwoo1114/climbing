import { useState, type FormEvent } from 'react'

import { getErrorMessage, getFieldError } from '@/api/client'
import type { GymDetail } from '@/api/gyms'
import Button from '@/components/common/Button'
import TextArea from '@/components/common/TextArea'
import TextField from '@/components/common/TextField'
import { Card, ErrorBanner } from '@/components/gyms/manage/ManageBits'
import { useUpdateGym } from '@/hooks/useGyms'
import { useToastStore } from '@/stores/toastStore'
import type { FieldCheck } from '@/lib/validation'

const FIELDS = ['name', 'description', 'address', 'phone', 'website'] as const
type Field = (typeof FIELDS)[number]
type Values = Record<Field, string>

const fromGym = (gym: GymDetail): Values => ({
  name: gym.name,
  description: gym.description,
  address: gym.address,
  phone: gym.phone,
  website: gym.website,
})

const invalid = (message: string): FieldCheck => ({ state: 'invalid', message })

/** 기본 정보 — 이름·소개·주소·전화·웹사이트를 PATCH 한다 */
export default function InfoSection({ gym }: { gym: GymDetail }) {
  const update = useUpdateGym(gym.id)
  const pushToast = useToastStore((s) => s.push)
  const [values, setValues] = useState<Values>(() => fromGym(gym))

  const error = update.error
  const serverError = (field: Field) => getFieldError(error, field)
  const check = (field: Field): FieldCheck | undefined => {
    const message = serverError(field)
    return message ? invalid(message) : undefined
  }
  const hasFieldError = FIELDS.some((field) => serverError(field))
  const generalError =
    error && !hasFieldError
      ? getErrorMessage(error, '암장 정보를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      : null

  const pending = update.isPending
  const canSubmit = values.name.trim().length > 0

  const edit = (field: Field) => (e: { target: { value: string } }) => {
    if (update.isError) update.reset()
    setValues((v) => ({ ...v, [field]: e.target.value }))
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || pending) return
    update.mutate(
      {
        name: values.name.trim(),
        description: values.description.trim(),
        address: values.address.trim(),
        phone: values.phone.trim(),
        website: values.website.trim(),
      },
      {
        onSuccess: (saved) => {
          setValues(fromGym(saved))
          pushToast({ title: '암장 정보를 저장했습니다.' })
        },
      },
    )
  }

  return (
    <Card id="manage-info" title="기본 정보" description="암장 상세 페이지 상단에 보이는 정보예요.">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <TextField
          label="암장 이름"
          id="gym-name"
          name="name"
          autoComplete="organization"
          required
          value={values.name}
          check={check('name')}
          onChange={edit('name')}
          disabled={pending}
        />
        <TextArea
          label="소개"
          id="gym-description"
          name="description"
          placeholder="세팅 주기, 운영 시간, 주차 안내 같은 걸 적어 주세요"
          rows={5}
          value={values.description}
          check={check('description')}
          onChange={edit('description')}
          disabled={pending}
        />
        <TextField
          label="주소"
          id="gym-address"
          name="address"
          autoComplete="street-address"
          value={values.address}
          check={check('address')}
          onChange={edit('address')}
          disabled={pending}
        />
        <TextField
          label="전화번호"
          id="gym-phone"
          name="phone"
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          placeholder="02-000-0000"
          value={values.phone}
          check={check('phone')}
          onChange={edit('phone')}
          disabled={pending}
        />
        <TextField
          label="웹사이트"
          id="gym-website"
          name="website"
          type="url"
          inputMode="url"
          autoComplete="url"
          spellCheck={false}
          autoCapitalize="none"
          placeholder="https://"
          value={values.website}
          check={check('website')}
          onChange={edit('website')}
          disabled={pending}
        />

        {generalError && <ErrorBanner>{generalError}</ErrorBanner>}

        <div className="flex justify-end">
          {/* 이 섹션의 유일한 primary CTA */}
          <Button type="submit" disabled={!canSubmit || pending}>
            {pending ? '저장 중…' : '저장'}
          </Button>
        </div>
      </form>
    </Card>
  )
}
