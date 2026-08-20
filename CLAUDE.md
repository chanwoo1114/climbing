# CLAUDE.md

클라이밍 암장 정보 + 등반 기록 SNS + 커뮤니티 + AI 자세 분석 서비스.
포트폴리오/학습용 모노레포. 상세 기획은 `docs/개발정의.md` 참고.

## 저장소 구조

```
backend/   Django 5.x + DRF        (accounts, gyms, climbs, social, community, crews, chat, analysis)
front/     React 19 + TS + Vite    (SPA, React Router v7 라이브러리 모드 — SSR 사용 안 함)
docs/      개발정의서, API 명세
```

## 명령어

```bash
# Backend
cd backend
docker compose up -d                          # web + db(postgis) + redis + celery
python manage.py migrate
python manage.py test                         # 전체 테스트
python manage.py test accounts                # 앱 단위 테스트
python manage.py spectacular --file schema.yml
black . && flake8                             # 포맷 + 린트

# Frontend
cd front
npm run dev          # localhost:5173
npm run build
npm run typecheck    # react-router typegen && tsc
```

## Backend 규칙

### 모델
- 모든 모델은 공용 `BaseModel` 상속: `created_at`, `updated_at`, `is_deleted`, `deleted_at`
- soft delete 통일: `is_active` 필드 새로 만들지 말 것. 삭제는 `is_deleted=True` + `deleted_at` 기록
- 기본 Manager(`objects`)는 `is_deleted=False`만 반환, 전체 조회는 `all_objects`
- 위치 데이터는 PostGIS `PointField(geography=True)` 사용 (lat/lng Float 필드 금지)
- 난이도는 자유 문자열 금지 → `GymDifficulty` FK 참조

### API
- URL prefix: `/api/v1/`, 라우팅은 앱별 `urls.py` 분리
- 응답 래퍼 통일: `{ "success": bool, "data": ..., "error": {"code", "message"} }`
- 목록 API는 커서 기반 페이지네이션 (`cursor`, `limit` 쿼리 파라미터)
- 필드 네이밍: API는 snake_case (프론트에서 camelCase 변환)
- 권한: 기본 `IsAuthenticated`, 공개 엔드포인트만 명시적으로 `AllowAny`
- 새 엔드포인트는 drf-spectacular 스키마에 반영되는지 확인 (`@extend_schema`)

### 비즈니스 로직
- 뷰는 얇게, 복잡한 로직(모집 마감→채팅방 생성 등)은 서비스 함수로 분리
- 다중 모델 변경은 `transaction.atomic` 필수
- 선착순 모집 참여 등 경합 구간은 `select_for_update()` 사용
- 파일 업로드는 서버 경유 금지 → S3 presigned URL 발급 후 클라이언트 직접 업로드
- 영상 분석은 반드시 Celery 태스크로 (동기 처리 금지), 상태는 `VideoAnalysis.status`로 관리

### 테스트
- 앱별 `tests/` 디렉토리, 파일 단위 분리 (예: `test_jwt_login.py`)
- 새 API 추가 시 최소 정상 케이스 + 권한 실패 케이스 테스트 작성

## Frontend 규칙

- SPA 전용: `react-router.config.ts`의 `ssr: false` 유지. loader/action 패턴 사용 금지
- 서버 상태는 TanStack Query (`hooks/`에 도메인별 훅), 클라이언트 상태는 Zustand (`stores/`)
- API 호출은 `api/` 디렉토리의 axios 인스턴스만 사용 (컴포넌트에서 직접 fetch 금지)
- axios 인터셉터에서 JWT 첨부 + snake_case↔camelCase 변환 처리
- 토큰: access는 메모리(store), refresh는 별도 저장 전략 — 변경 시 `authStore` 주석 참고
- 스타일은 Tailwind 유틸리티 클래스, 공통 컴포넌트는 `components/common/`
- WebSocket은 `useChatSocket` 훅으로만 접근

### 디자인 시스템 (Chalk & Terra)
- 팔레트는 index.css의 @theme 토큰만 사용, 임의 hex 금지
- 토큰: chalk(배경/보더), ink(텍스트 — 순수 black/gray-900 금지),
  terra(primary CTA), ochre(서브 포인트), moss(success), slate(정보), danger(삭제/오류 전용)
- terra-500은 화면당 주요 CTA 1개에만, danger는 삭제/오류 전용
- 배경 chalk-100, 카드 white + chalk-300 보더, radius 12~18px
- 난이도 색상은 토큰이 아닌 GymDifficulty.color(DB 값)를 렌더링
- 그라데이션/그림자 최소화, 플랫하게. 모바일 퍼스트, md: 이상에서 데스크톱 확장
- 다크 모드는 범위 외 (M8 선택)

## 하지 말 것

- ORM 우회 raw SQL (이 프로젝트는 Django ORM 사용 — LottoMap과 다름)
- 모델에 `is_active`/`is_deleted` 혼용 추가
- 서버를 경유하는 파일 업로드
- 프론트에 SSR/loader 패턴 도입
- `access_token` 등 민감 값의 DB 평문 저장

## 작업 흐름

- 마일스톤 순서는 `docs/개발정의.md`의 M1→M7. 현재 진행 단계 확인 후 작업
- 마이그레이션 파일은 임의 수정 금지, 모델 변경 시 새로 생성
- 커밋 전 `black . && flake8` (backend), `npm run typecheck` (front) 통과 확인
