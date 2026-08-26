# CLAUDE.md

클라이밍 암장 정보 + 등반 기록 SNS + 커뮤니티 + AI 자세 분석 서비스.
포트폴리오/학습용 모노레포. 상세 기획은 `docs/개발정의.md` 참고.

## 저장소 구조

```
backend/   Django 5.x + DRF        (accounts, gyms, climbs, social, community, crews, chat, analysis)
front/     React 19 + TS + Vite    (SPA, React Router v7 라이브러리 모드 — SSR 사용 안 함)
docs/      개발정의.md (개발 정의서 v3 — 마일스톤/모델/API 초안)
```

공용 코드는 `backend/common/` (BaseModel, 소프트삭제 매니저, 응답 래퍼 렌더러,
커서 페이지네이션, 예외 핸들러). 도메인 앱은 이걸 상속/재사용한다.

## 포트 (이 머신 기준 — 다른 프로젝트와 충돌 회피용)

| 대상 | 호스트 | 컨테이너 | 설정 위치 |
|---|---|---|---|
| Django API | 8010 | 8000 | `backend/.env` → `WEB_PORT` |
| PostGIS | 5442 | 5432 | `backend/.env` → `DB_PORT` |
| Redis | 6389 | 6379 | `backend/.env` → `REDIS_PORT` |
| Vite dev | 5180 | 5180 | `front/.env`(FRONT_PORT), `front/vite.config.ts` |

8000/8001/5173/5432/5433은 다른 프로젝트(lottomap, disaster)가 점유 중이므로 쓰지 말 것.
외부 공개는 공유기 포트포워딩으로 5180 하나만 연다 —
브라우저는 항상 vite(5180)와 통신하고 /api·/ws는 vite가 백엔드로 프록시한다.
front 컨테이너는 백엔드 도커 네트워크(climbing-test_default)에 합류해 web:8000을 직접 바라본다
(호스트 경유는 방화벽에 막힘). 따라서 backend 스택을 먼저 띄워야 한다.

## 명령어

개발 스택은 `docker-compose.dev.yml`이라 `-f`가 필요하다. 아래처럼 별칭을 잡으면 편하다.

```bash
# Backend (컨테이너 안에서 실행)
cd backend
cp .env.example .env                          # 최초 1회
alias dc='docker compose -f docker-compose.dev.yml'

dc up -d                                      # web + db(postgis) + redis + celery
dc exec web python manage.py migrate
dc exec web python manage.py test             # 전체 테스트
dc exec web python manage.py test accounts    # 앱 단위 테스트
dc exec web python manage.py spectacular --file schema.yml
dc exec web sh -c "black . && flake8"         # 포맷 + 린트
dc exec web python manage.py verify_email a@b.com   # 개발용: 메일 없이 이메일 인증 처리
dc restart celery                             # tasks.py 추가/변경 후 (아래 주의 참고)

# Frontend
cd front
npm run dev          # localhost:5180
npm run build
npm run typecheck    # tsc --noEmit
npm test             # vitest (lib/validation 등 순수 로직)
```

소스는 볼륨 마운트되어 있어 코드 수정이 즉시 반영된다 (web=runserver 자동 리로드,
celery=watchmedo 재시작, front=vite HMR). 재빌드가 필요한 건 의존성 변경 시뿐이다.
주의: Windows 바인드 마운트에서는 watchmedo 파일 감지가 동작하지 않아 celery 는
자동 재시작되지 않는다. 새 태스크를 만들거나 tasks.py 를 고치면 `dc restart celery`.
개발 기본 EMAIL_BACKEND 는 콘솔이라 인증/재설정 메일 본문(링크)은 `dc logs celery` 에 찍힌다.

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
- 입력 규칙(비밀번호·닉네임·이메일)을 바꾸면 `accounts/validators.py`·`serializers.py` 와
  `front/src/lib/validation.ts` 를 함께 고치고, 양쪽 테스트에 같은 입력값을 추가한다
  (`accounts/tests/test_password_rules.py` ↔ `front/src/lib/validation.test.ts`)

## Frontend 규칙

- SPA 전용: `react-router.config.ts`의 `ssr: false` 유지. loader/action 패턴 사용 금지
- 서버 상태는 TanStack Query (`hooks/`에 도메인별 훅), 클라이언트 상태는 Zustand (`stores/`)
- API 호출은 `api/` 디렉토리의 axios 인스턴스만 사용 (컴포넌트에서 직접 fetch 금지)
- axios 인터셉터에서 JWT 첨부 + snake_case↔camelCase 변환 처리
- 토큰: access는 메모리(store), refresh는 별도 저장 전략 — 변경 시 `authStore` 주석 참고
- 스타일은 Tailwind 유틸리티 클래스, 공통 컴포넌트는 `components/common/`
- WebSocket은 `useChatSocket` 훅으로만 접근

### 디자인 시스템 (Chalk & Hold)
- 팔레트는 index.css의 @theme 토큰만 사용, 임의 hex 금지
- 토큰: chalk(배경/보더 — 차가운 초크 회색, 따뜻한 크림 금지), ink(텍스트 — 매트 차콜, 순수 black/gray-900 금지),
  hold(primary CTA — 암장 홀드 코발트), ochre(서브 포인트), moss(success), slate(정보), danger(삭제/오류 전용)
- hold-500은 화면당 주요 CTA 1개에만, danger는 삭제/오류 전용
- 팔레트 근거: 초크(배경)·매트(텍스트)·홀드(액센트). 크림+테라코타+세리프 조합은 AI 기본값이라 피한다 (frontend-design 스킬)
- 배경 chalk-100, 카드 white + chalk-300 보더, radius 12~18px
- 난이도 색상은 토큰이 아닌 GymDifficulty.color(DB 값)를 렌더링
- 그라데이션/그림자 최소화, 플랫하게. 모바일 퍼스트, md: 이상에서 데스크톱 확장
- 다크 모드는 범위 외 (M8 선택)

### UI 품질 규칙 (Vercel Web Interface Guidelines + make-interfaces-feel-better 기준)
- 버튼은 `components/common/Button`(primary/secondary) 사용. 직접 `<button className=...>` 만들지 말 것
- 터치 영역 최소 44px (`min-h-11`). 텍스트 링크·아이콘 버튼도 패딩으로 확보
- 카드 radius는 `rounded-card`(14px) 토큰, 안쪽 요소는 `rounded-xl`(12px). `rounded-[14px]` 하드코딩 금지
- 포커스: 링크·버튼은 전역 `:focus-visible` 링(index.css)이 담당. `outline-none`은 대체 표시가 있을 때만
- 전환은 바뀌는 속성만 명시 (`transition-colors`, `transition-[transform,opacity]`). `transition-all` 금지
- 애니메이션은 `transform`/`opacity`만. 모션 축소는 index.css 전역 규칙이 처리
- 동적 숫자(거리·개수·가격)는 `tabular-nums`, 짧은 본문·설명은 `text-pretty`, 제목은 전역 `text-wrap: balance`
- 긴 사용자 텍스트(닉네임·상호명)는 `min-w-0 truncate` 또는 `break-words`. 빈 목록은 빈 상태 UI 필수
- 동적 알림: 오류 `role="alert"`, 진행·완료 안내 `role="status"`. 아이콘만 있는 버튼은 `aria-label`
- 이메일 입력은 `TextField type="email"`이 spellCheck/autoCapitalize/inputMode 를 알아서 끈다
- 날짜·숫자 포맷은 `Intl.*` (하드코딩 금지). 파괴적 액션(삭제)은 확인 모달 또는 undo
- 목록 50개 이상은 가상화. 탭·필터·페이지 상태는 URL 쿼리에 반영
- 폰트는 Pretendard(index.html CDN) + 시스템 폴백. `--font-sans` 토큰 외 font-family 지정 금지

## Docker 파일 규칙

- 개발용: `Dockerfile.dev` + `docker-compose.dev.yml` — 소스 볼륨 마운트 + 자동 리로드
- 프로덕션용: `Dockerfile.prod` — 소스를 이미지에 굽고 리로드 없음 (web은 daphne, front는 nginx)
- 컨테이너·이미지 이름은 `climbing-test-*` (web/db/redis/celery/front)
- 개발 중 `Dockerfile.prod`는 건드리지 않는다. 의존성 추가 시 두 파일 모두 반영 확인

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
