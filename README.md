# 🧗 Climbing

클라이밍 암장 정보 검색부터 등반 기록, 커뮤니티, AI 자세 분석까지 — 클라이머를 위한 올인원 서비스

> 포트폴리오/학습 목적 프로젝트입니다. 실운용 대비 의도적으로 생략한 부분은 [실서비스라면?](#실서비스라면) 섹션에 정리했습니다.

## 주요 기능

- **암장 지도 검색** — 지도 뷰포트 기반 암장 탐색, 거리순 정렬 (PostGIS), 가격표/편의시설/리뷰
- **클라이밍 로그 & 피드** — 난이도별 등반 기록(영상 포함), 팔로잉/탐색 피드, 좋아요/댓글
- **커뮤니티 & 투어 모집** — 자유글/모집글 게시판, 모집 마감 시 참여자 그룹 채팅방 자동 생성
- **크루** — 크루 생성/가입, 크루 단톡방, 크루 피드, 크루 주최 투어 모집, 프로필 크루 뱃지
- **실시간 채팅** — 1:1 DM 및 그룹 채팅 (Django Channels + WebSocket)
- **AI 자세 분석** — 등반 영상에서 관절 좌표 추출(MediaPipe), 무게중심 궤적·무브 분석 리포트

## 기술 스택

**Backend**
- Django 5.x + Django REST Framework
- PostgreSQL + PostGIS (위치 검색), Redis
- Django Channels (WebSocket), Celery (영상 분석 파이프라인)
- MediaPipe Pose + OpenCV (CPU 기반 비동기 영상 분석)
- SimpleJWT, drf-spectacular, S3 presigned URL 업로드

**Frontend**
- React 19 + TypeScript + Vite (SPA)
- React Router v7 (라이브러리 모드), TanStack Query, Zustand
- Tailwind CSS v4, MapLibre GL

## 아키텍처

```
┌──────────┐     REST / WS      ┌─────────────┐
│  React    │ ◄───────────────► │  Django      │──► PostgreSQL(+PostGIS)
│  SPA      │                   │  DRF/Channels│──► Redis (채널레이어/브로커)
└──────────┘                    └──────┬──────┘
      │  presigned URL 직접 업로드      │ 분석 태스크
      ▼                                ▼
     S3  ◄──────────────────── Celery Worker (MediaPipe)
```

## 프로젝트 구조

```
climbing/
├── backend/          # Django + DRF
│   ├── accounts/     # 인증, 프로필
│   ├── gyms/         # 암장, 리뷰, 난이도, 베타
│   ├── climbs/       # 등반 로그, 좋아요, 댓글, 피드
│   ├── social/       # 팔로우
│   ├── community/    # 게시판, 투어 모집
│   ├── crews/        # 크루, 크루 멤버십
│   ├── chat/         # 실시간 채팅
│   └── analysis/     # AI 영상 자세 분석
├── front/            # React SPA
└── docs/             # 개발정의서, API 명세
```

## 실행 방법

```bash
# Backend (web + db + redis + celery)
cd backend
docker compose up -d

# Frontend
cd front
npm install
npm run dev   # http://localhost:5173
```

API 문서: http://localhost:8000/api/schema/swagger-ui/

## 개발 문서

- [개발 정의서](./docs/개발정의.md) — 마일스톤, 모델 설계, API 초안

## 실서비스라면?

학습용으로 의도적으로 단순화한 부분과, 실운용 시 필요한 개선안:

| 현재 구현 | 실서비스 시 |
|---|---|
| 영상 원본 그대로 서빙 | MediaConvert 등으로 HLS 트랜스코딩 + CDN |
| AI 분석 CPU 처리 (수 분 소요) | 서버리스 GPU(Replicate 등) 또는 GPU 워커로 처리 시간 단축 |
| 단일 서버 docker compose 배포 | 로드밸런서 + 오토스케일링, 무중단 배포 |
| 알림 = 폴링 | 푸시 알림 (FCM), WebSocket 알림 채널 |
| 신고/차단 기능 없음 | UGC 신고·차단, 운영 어드민 (커뮤니티 필수) |
| 시드 데이터 기반 암장 정보 | 암장 데이터 수집 파이프라인 + 갱신 크롤러 |

## License

MIT
