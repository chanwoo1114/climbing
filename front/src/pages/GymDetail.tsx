import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'

import { getErrorCode, getErrorMessage, getFieldError } from '@/api/client'
import type { GymDetail as Gym, GymReview } from '@/api/gyms'
import Button from '@/components/common/Button'
import { RatingInput, RatingStars } from '@/components/common/Rating'
import TextArea from '@/components/common/TextArea'
import { useCreateGymReview, useGym, useGymReviews } from '@/hooks/useGyms'
import { useAuthStore } from '@/stores/authStore'

/** 리뷰 본문 상한 — 서버 TextField 는 제한이 없어 화면에서만 막는다 */
export const REVIEW_MAX_LENGTH = 500

const won = new Intl.NumberFormat('ko-KR')
const count = new Intl.NumberFormat('ko-KR')
const average = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 })
const reviewDate = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium' })

// 헤더의 전화·웹사이트·지도 링크 — 글자가 작아도 44px 터치 영역
const CONTACT_LINK =
  '-mx-1 inline-flex min-h-11 items-center px-1 font-medium text-hold-600 hover:underline'

export default function GymDetail() {
  const { id } = useParams()
  const gymId = Number(id)
  const validId = Number.isInteger(gymId) && gymId > 0
  const { data: gym, isPending, isError, error } = useGym(validId ? gymId : NaN)

  if (!validId || (isError && getErrorCode(error) === 'http_404')) {
    return <NotFound message="암장을 찾을 수 없어요." />
  }
  if (isPending) {
    return (
      <p role="status" className="py-10 text-center text-sm text-ink-400">
        불러오는 중…
      </p>
    )
  }
  if (isError || !gym) {
    return <NotFound message="암장 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." />
  }
  return <GymDetailView gym={gym} />
}

function NotFound({ message }: { message: string }) {
  return (
    <div role="alert" className="py-10 text-center">
      <p className="text-sm text-danger-500">{message}</p>
      <Link
        to="/"
        className="mt-2 inline-flex min-h-11 items-center px-3 text-sm font-medium text-hold-600 hover:underline"
      >
        지도로 돌아가기
      </Link>
    </div>
  )
}

/** 표시용 호스트명. 이상한 URL 이면 원문 그대로 */
function websiteLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function GymDetailView({ gym }: { gym: Gym }) {
  // MapHome 이 ?lat=&lng=&z= 를 읽어 그 지점에서 시작한다
  const mapLink = `/?${new URLSearchParams({
    lat: String(gym.lat),
    lng: String(gym.lng),
    z: '15',
  })}`
  const images = [...gym.images].sort((a, b) => a.order - b.order)
  const difficulties = [...gym.difficulties].sort((a, b) => a.order - b.order)

  return (
    <div className="md:grid md:grid-cols-[minmax(0,1fr)_380px] md:items-start md:gap-6">
      <div className="space-y-4">
        <header>
          <h1 className="text-2xl font-semibold text-ink-700">{gym.name}</h1>
          <p className="mt-1 text-sm text-pretty break-words text-ink-400">{gym.address}</p>
          <div className="mt-1 flex flex-wrap items-center gap-x-4 text-sm">
            {gym.phone && (
              <a href={`tel:${gym.phone}`} className={CONTACT_LINK}>
                <span aria-hidden className="mr-1">
                  ☎
                </span>
                <span className="tabular-nums">{gym.phone}</span>
              </a>
            )}
            {gym.website && (
              <a href={gym.website} target="_blank" rel="noreferrer" className={CONTACT_LINK}>
                {websiteLabel(gym.website)}
                <span className="sr-only"> (새 창에서 열림)</span>
              </a>
            )}
            <Link to={mapLink} className={CONTACT_LINK}>
              지도에서 보기
            </Link>
          </div>
        </header>

        <Gallery images={images} name={gym.name} />

        <Section title="가격표">
          {gym.prices.length === 0 ? (
            <Empty>등록된 가격 정보가 없어요</Empty>
          ) : (
            <ul className="divide-y divide-chalk-200">
              {gym.prices.map((price) => (
                <li key={price.id} className="flex items-baseline justify-between gap-3 py-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium break-words text-ink-700">{price.name}</p>
                    {price.note && (
                      <p className="text-xs text-pretty break-words text-ink-400">{price.note}</p>
                    )}
                  </div>
                  <p className="shrink-0 text-sm font-medium text-ink-700 tabular-nums">
                    {won.format(price.price)}원
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="편의시설">
          {gym.facilities.length === 0 ? (
            <Empty>등록된 편의시설 정보가 없어요</Empty>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {gym.facilities.map((facility) => (
                <li
                  key={facility.id}
                  className="rounded-xl bg-chalk-100 px-3 py-1.5 text-sm break-words text-ink-600"
                >
                  {facility.name}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="난이도">
          {difficulties.length === 0 ? (
            <Empty>등록된 난이도 정보가 없어요</Empty>
          ) : (
            // 색은 토큰이 아니라 암장이 정한 값(GymDifficulty.color)을 그대로 쓴다
            <ol className="flex flex-wrap gap-x-4 gap-y-2">
              {difficulties.map((difficulty) => (
                <li key={difficulty.id} className="flex items-center gap-1.5 text-sm text-ink-600">
                  <span
                    aria-hidden
                    className="size-4 shrink-0 rounded-full border border-chalk-400"
                    style={{ backgroundColor: difficulty.color }}
                  />
                  {difficulty.name}
                </li>
              ))}
            </ol>
          )}
        </Section>

        {gym.description && (
          <Section title="소개">
            <p className="text-sm whitespace-pre-line text-pretty break-words text-ink-600">
              {gym.description}
            </p>
          </Section>
        )}
      </div>

      <Reviews gymId={gym.id} reviewCount={gym.reviewCount} ratingAvg={gym.ratingAvg} />
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-card border border-chalk-300 bg-white p-5">
      <h2 className="mb-3 text-base font-semibold text-ink-700">{title}</h2>
      {children}
    </section>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-pretty text-ink-400">{children}</p>
}

function Gallery({ images, name }: { images: Gym['images']; name: string }) {
  if (images.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-card border border-dashed border-chalk-400 bg-chalk-50 text-sm text-ink-400">
        등록된 사진이 없어요
      </div>
    )
  }
  return (
    // 모바일에선 화면 가장자리까지 흘려 보낸다 (main 의 px-4 만큼 음수 마진)
    <ul
      aria-label={`${name} 사진`}
      className="-mx-4 flex snap-x gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:px-0"
    >
      {images.map((image, index) => (
        <li key={image.id} className="shrink-0 snap-start">
          <img
            src={image.image}
            alt={`${name} 사진 ${index + 1}`}
            loading="lazy"
            className="h-44 w-64 rounded-xl object-cover"
          />
        </li>
      ))}
    </ul>
  )
}

// --- 리뷰 ---

function Reviews({
  gymId,
  reviewCount,
  ratingAvg,
}: {
  gymId: number
  reviewCount: number
  ratingAvg: number | null
}) {
  const reviews = useGymReviews(gymId)
  const loaded = reviews.data?.pages.flatMap((page) => page.results) ?? []

  return (
    <section aria-labelledby="reviews-heading" className="mt-6 space-y-3 md:mt-0">
      <div className="rounded-card border border-chalk-300 bg-white p-5">
        <h2 id="reviews-heading" className="text-base font-semibold text-ink-700">
          리뷰{' '}
          <span className="font-medium text-ink-400 tabular-nums">
            {count.format(reviewCount)}개
          </span>
        </h2>
        {ratingAvg !== null && (
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-ink-500">
            <RatingStars value={ratingAvg} />
            <span className="tabular-nums">평균 {average.format(ratingAvg)}점</span>
          </p>
        )}
        <ReviewForm gymId={gymId} />
      </div>

      {reviews.isPending && (
        <p role="status" className="text-sm text-ink-400">
          리뷰를 불러오는 중…
        </p>
      )}
      {reviews.isError && (
        <p role="alert" className="text-sm text-danger-500">
          리뷰를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.
        </p>
      )}
      {reviews.data && loaded.length === 0 && (
        <div className="rounded-card border border-chalk-300 bg-white p-6 text-center">
          <p className="text-sm font-medium text-ink-600">아직 리뷰가 없어요</p>
          <p className="mt-1 text-xs text-pretty text-ink-400">첫 리뷰를 남겨보세요.</p>
        </div>
      )}
      {loaded.length > 0 && (
        <ul className="space-y-3">
          {loaded.map((review) => (
            <li key={review.id}>
              <ReviewItem review={review} />
            </li>
          ))}
        </ul>
      )}
      {reviews.hasNextPage && (
        <Button
          variant="secondary"
          full
          onClick={() => reviews.fetchNextPage()}
          disabled={reviews.isFetchingNextPage}
        >
          {reviews.isFetchingNextPage ? '불러오는 중…' : '더 보기'}
        </Button>
      )}
    </section>
  )
}

function ReviewItem({ review }: { review: GymReview }) {
  return (
    <article className="rounded-card border border-chalk-300 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate text-sm font-medium text-ink-700">
          {review.user.nickname}
        </span>
        <time
          dateTime={review.createdAt}
          className="shrink-0 text-xs text-ink-400 tabular-nums"
        >
          {reviewDate.format(new Date(review.createdAt))}
        </time>
      </div>
      <RatingStars value={review.rating} className="mt-1 text-sm" />
      <p className="mt-2 text-sm whitespace-pre-line text-pretty break-words text-ink-600">
        {review.content}
      </p>
    </article>
  )
}

/**
 * 리뷰 작성 — 로그인 상태에 따라 갈린다.
 * booting: 세션 복원 중이라 자리만 비워둔다 / anonymous: 로그인 유도 / authenticated: 폼
 */
function ReviewForm({ gymId }: { gymId: number }) {
  const status = useAuthStore((s) => s.status)
  const navigate = useNavigate()
  const location = useLocation()
  const create = useCreateGymReview(gymId)
  const [rating, setRating] = useState(0)
  const [content, setContent] = useState('')
  const [saved, setSaved] = useState(false)

  if (status === 'booting') {
    return <div aria-hidden className="mt-4 h-11 rounded-xl bg-chalk-100" />
  }
  if (status === 'anonymous') {
    return (
      <div className="mt-4">
        <Button
          variant="secondary"
          full
          onClick={() => navigate('/login', { state: { from: location.pathname } })}
        >
          로그인하고 리뷰 쓰기
        </Button>
      </div>
    )
  }

  const error = create.error
  const ratingError = getFieldError(error, 'rating')
  const contentError = getFieldError(error, 'content')
  // 필드별로 표시된 오류는 공통 배너에서 중복 노출하지 않는다
  const generalError =
    error && !ratingError && !contentError
      ? getErrorMessage(error, '리뷰를 남기지 못했습니다. 잠시 후 다시 시도해 주세요.')
      : null

  const trimmed = content.trim()
  const canSubmit = rating >= 1 && trimmed.length > 0 && content.length <= REVIEW_MAX_LENGTH
  const pending = create.isPending

  // 입력을 고치기 시작하면 이전 서버 오류와 "남겼습니다" 를 지운다
  const touch = () => {
    if (create.isError) create.reset()
    setSaved(false)
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit || pending) return
    create.mutate(
      { rating, content: trimmed },
      {
        onSuccess: () => {
          setRating(0)
          setContent('')
          setSaved(true)
        },
      },
    )
  }

  return (
    <form onSubmit={onSubmit} noValidate className="mt-4 space-y-3 border-t border-chalk-200 pt-4">
      <RatingInput
        value={rating}
        onChange={(next) => {
          touch()
          setRating(next)
        }}
        error={ratingError}
        disabled={pending}
      />
      <TextArea
        label="리뷰"
        name="content"
        placeholder="홀드 상태, 세팅 주기, 붐비는 시간대 같은 걸 적어 보세요"
        maxLength={REVIEW_MAX_LENGTH}
        showCount
        value={content}
        check={contentError ? { state: 'invalid', message: contentError } : undefined}
        onChange={(e) => {
          touch()
          setContent(e.target.value)
        }}
        disabled={pending}
      />

      {generalError && (
        <p role="alert" className="rounded-xl bg-danger-100 px-3 py-2 text-sm text-danger-600">
          {generalError}
        </p>
      )}
      {saved && (
        <p role="status" className="text-sm text-moss-500">
          리뷰를 남겼습니다.
        </p>
      )}

      {/* 이 페이지의 유일한 primary CTA */}
      <Button type="submit" full disabled={!canSubmit || pending}>
        {pending ? '남기는 중…' : '리뷰 남기기'}
      </Button>
    </form>
  )
}
