/** 베타 영상 테스트 공용 픽스처 — 응답 본문은 백엔드 스키마(snake_case) 그대로 */

export const GYM = {
  id: 1,
  name: '더클라임 강남',
  address: '서울 강남구',
  lat: 37.5,
  lng: 127.0,
  description: '',
  phone: '',
  website: '',
  images: [],
  prices: [],
  facilities: [],
  difficulties: [
    { id: 10, name: '파랑', color: '#1e40af', order: 1 },
    { id: 11, name: '빨강', color: '#dc2626', order: 2 },
  ],
  review_count: 0,
  rating_avg: null,
}

export const BETA = {
  id: 5,
  user: { id: 1, nickname: '나', image: null },
  gym: { id: 1, name: '더클라임 강남' },
  difficulty: { id: 10, name: '파랑', color: '#1e40af', order: 1 },
  sector: 'A벽',
  title: '하이스텝 베타',
  description: '오른발 하이스텝 후 왼손 크림프',
  video_url: 'https://cdn.test/betas/5.mp4',
  thumbnail_url: '',
  climb_log_id: 3,
  view_count: 1234,
  created_at: '2026-08-27T09:00:00Z',
  is_mine: true,
}

export const OTHERS_BETA = {
  ...BETA,
  id: 6,
  user: { id: 2, nickname: '다른사람', image: null },
  title: '남의 베타',
  climb_log_id: null,
  is_mine: false,
}
