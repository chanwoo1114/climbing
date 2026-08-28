import { Link, useParams, useSearchParams } from 'react-router'

import { getErrorCode } from '@/api/client'
import type { GymDetail } from '@/api/gyms'
import DifficultySection from '@/components/gyms/manage/DifficultySection'
import FacilitySection from '@/components/gyms/manage/FacilitySection'
import ImageSection from '@/components/gyms/manage/ImageSection'
import InfoSection from '@/components/gyms/manage/InfoSection'
import ManagerSection from '@/components/gyms/manage/ManagerSection'
import PriceSection from '@/components/gyms/manage/PriceSection'
import { useGym } from '@/hooks/useGyms'

type Section = 'info' | 'difficulties' | 'images' | 'prices' | 'facilities' | 'managers'

const SECTIONS: { value: Section; label: string }[] = [
  { value: 'info', label: '기본 정보' },
  { value: 'difficulties', label: '난이도' },
  { value: 'images', label: '사진' },
  { value: 'prices', label: '가격' },
  { value: 'facilities', label: '편의시설' },
  { value: 'managers', label: '관리자' },
]

/** ?section= 이 없거나 이상하면 기본 정보 */
function sectionFromParams(params: URLSearchParams): Section {
  const value = params.get('section')
  return SECTIONS.some((s) => s.value === value) ? (value as Section) : 'info'
}

/**
 * 암장 관리 (/gyms/:id/manage) — 서버가 상세에 실어 주는 is_manager 로 진입을 막는다.
 * 섹션 상태는 URL(?section=)에 산다 — 새로고침·공유해도 같은 섹션.
 */
export default function GymManage() {
  const { id } = useParams()
  const gymId = Number(id)
  const validId = Number.isInteger(gymId) && gymId > 0
  const gym = useGym(validId ? gymId : NaN)

  const code = gym.isError ? getErrorCode(gym.error) : undefined
  if (!validId || code === 'http_404' || code === 'not_found') {
    return <Blocked message="암장을 찾을 수 없어요." to="/" label="지도로 돌아가기" />
  }
  if (gym.isPending) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (gym.isError || !gym.data) {
    return (
      <Blocked
        message="암장 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
        to={`/gyms/${gymId}`}
        label="암장 페이지로 돌아가기"
      />
    )
  }
  if (!gym.data.isManager) {
    return (
      <Blocked
        message="암장 관리자만 할 수 있습니다."
        to={`/gyms/${gymId}`}
        label="암장 페이지로 돌아가기"
      />
    )
  }
  return <ManageView gym={gym.data} />
}

function Blocked({ message, to, label }: { message: string; to: string; label: string }) {
  return (
    <div role="alert" className="py-10 text-center">
      <p className="text-sm text-pretty text-danger-500">{message}</p>
      <Link
        to={to}
        className="mt-2 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
      >
        {label}
      </Link>
    </div>
  )
}

const CHIP =
  'inline-flex min-h-11 shrink-0 items-center rounded-xl border px-4 text-sm transition-colors duration-150'
const CHIP_IDLE = 'border-chalk-300 bg-white font-medium text-ink-500 hover:bg-chalk-100'
const CHIP_ACTIVE = 'border-ink-500 bg-chalk-200 font-semibold text-ink-700'

function ManageView({ gym }: { gym: GymDetail }) {
  const [searchParams] = useSearchParams()
  const section = sectionFromParams(searchParams)
  const base = `/gyms/${gym.id}/manage`

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium text-ink-400">암장 관리</p>
          <h1 className="truncate text-2xl font-semibold text-ink-700">{gym.name}</h1>
        </div>
        <Link
          to={`/gyms/${gym.id}`}
          className="-mx-2 inline-flex min-h-11 items-center px-2 text-sm font-medium text-hold-600 hover:underline"
        >
          암장 페이지 보기
        </Link>
      </header>

      {/* 모바일에선 가로 스크롤 칩 (main 의 px-4 만큼 음수 마진), md 이상은 줄바꿈 */}
      <nav
        aria-label="관리 항목"
        className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:flex-wrap md:px-0"
      >
        {SECTIONS.map((item) => {
          const active = item.value === section
          return (
            <Link
              key={item.value}
              to={item.value === 'info' ? base : `${base}?section=${item.value}`}
              replace
              aria-current={active ? 'page' : undefined}
              className={`${CHIP} ${active ? CHIP_ACTIVE : CHIP_IDLE}`}
            >
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* 섹션은 한 번에 하나만 마운트 — 각 섹션의 폼 상태는 전환할 때 서버 값으로 다시 시작한다 */}
      {section === 'info' && <InfoSection gym={gym} />}
      {section === 'difficulties' && <DifficultySection gym={gym} />}
      {section === 'images' && <ImageSection gym={gym} />}
      {section === 'prices' && <PriceSection gym={gym} />}
      {section === 'facilities' && <FacilitySection gym={gym} />}
      {section === 'managers' && <ManagerSection gym={gym} />}
    </div>
  )
}
