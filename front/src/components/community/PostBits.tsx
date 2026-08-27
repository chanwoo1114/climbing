import {
  CATEGORY_LABEL,
  RECRUITMENT_STATUS_LABEL,
  isRecruitmentFull,
  type PostCategory,
  type Recruitment,
  type RecruitmentStatus,
} from '@/api/posts'

/** 게시판 공용 조각 — 배지·날짜 포맷·인원 표기. PostCard/PostDetail/PostList 가 같이 쓴다 */

export const count = new Intl.NumberFormat('ko-KR')

/** 목록 상태줄용 — "8월 30일 (토) 19:00" */
const meetAtShort = new Intl.DateTimeFormat('ko-KR', {
  month: 'long',
  day: 'numeric',
  weekday: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** 상세 패널용 — "2026. 8. 30. 오후 7:00" */
const meetAtLong = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'short' })

export const formatMeetAtShort = (iso: string) => meetAtShort.format(new Date(iso))
export const formatMeetAtLong = (iso: string) => meetAtLong.format(new Date(iso))

/** 작성자를 포함한 현재 인원 — "3/6" 의 3 */
export const memberCount = (recruitment: Recruitment) => recruitment.approvedCount + 1

// 자유 = slate(정보), 모집 = ochre(서브 포인트)
const CATEGORY_CLASS: Record<PostCategory, string> = {
  free: 'bg-slate-100 text-slate-500',
  recruit: 'bg-ochre-100 text-ochre-500',
}

export function CategoryBadge({ category }: { category: PostCategory }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-xl px-2 py-0.5 text-xs font-medium ${CATEGORY_CLASS[category]}`}
    >
      {CATEGORY_LABEL[category]}
    </span>
  )
}

// 모집중은 ochre(모집 색), 마감·취소는 중립. 마감은 오류가 아니라 danger 를 쓰지 않는다
const STATUS_CLASS: Record<RecruitmentStatus, string> = {
  open: 'bg-ochre-100 text-ochre-500',
  closed: 'bg-chalk-200 text-ink-500',
  canceled: 'bg-chalk-200 text-ink-500',
}

export function RecruitmentStatusBadge({ recruitment }: { recruitment: Recruitment }) {
  // 열려 있어도 정원이 찼으면 "정원 마감" 으로 보여준다 (서버는 곧 자동 마감한다)
  const label =
    recruitment.status === 'open' && isRecruitmentFull(recruitment)
      ? '정원 마감'
      : RECRUITMENT_STATUS_LABEL[recruitment.status]
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-xl px-2 py-0.5 text-xs font-medium ${STATUS_CLASS[recruitment.status]}`}
    >
      {label}
    </span>
  )
}
