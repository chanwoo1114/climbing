# backend

Django 5 + DRF. 상세 규칙은 저장소 루트 `CLAUDE.md`, 기획은 `docs/개발정의.md` 참고.

## 실행

```bash
cp .env.example .env
alias dc='docker compose -f docker-compose.dev.yml'

dc up -d                             # db(postgis) + redis + web + celery
dc exec web python manage.py migrate
dc exec web python manage.py createsuperuser
```

- API: http://localhost:8010/api/v1/
- Swagger: http://localhost:8010/api/schema/swagger-ui/
- 헬스체크: http://localhost:8010/health/

호스트 포트(8010 / 5442 / 6389)는 `.env`의 `WEB_PORT`, `DB_PORT`, `REDIS_PORT`로 바꾼다.

## 이미지 구성

| 파일 | 스테이지 | 용도 |
|---|---|---|
| `Dockerfile.dev` | `dev` | Django runserver — 소스 마운트 + 저장 시 자동 리로드 |
| `Dockerfile.dev` | `worker-dev` | celery + MediaPipe — watchmedo가 .py 변경 시 워커 재시작 |
| `Dockerfile.prod` | `web` | daphne(ASGI) — 소스를 이미지에 굽는다 |
| `Dockerfile.prod` | `worker` | celery + MediaPipe, 리로드 없음 |

컨테이너 이름은 `climbing-test-web` / `-db` / `-redis` / `-celery`.

## 암장 데이터

전국 암장은 Kakao Local API 크롤러로 수집한다 (정확한 좌표/주소/전화번호):

```bash
# 1. developers.kakao.com 에서 REST API 키 발급 (무료) → .env의 KAKAO_REST_API_KEY
dc exec web python manage.py import_gyms_kakao --dry-run   # 수집 결과 미리보기
dc exec web python manage.py import_gyms_kakao             # DB 적재 (이름 기준 upsert)
```

전국을 격자로 쪼개 rect 검색을 재귀 반복하므로 카카오의 45건 제한을 우회한다.
용품점/학원은 상호·카테고리로 필터링하고, 난이도가 없는 암장엔 기본 8색 체계를 부여한다.
재실행하면 upsert되므로 주기적 갱신에도 그대로 쓴다.

영상 분석 의존성이 web 이미지에 들어가지 않도록 requirements를 나눠 뒀다
(`requirements/base.txt`, `dev.txt`, `worker.txt`).
의존성을 추가했을 때만 `dc build`가 필요하고, 코드 수정은 재빌드 없이 반영된다.

## 테이블 코멘트

DB 툴(PyCharm 등)의 public 스키마에서 각 테이블 용도가 보이도록 코멘트를 달아 뒀다.

- 우리 모델: `Meta.db_table_comment` + 필드 `db_comment=` → 마이그레이션에 자동 반영
- Django/서드파티 내장 테이블(auth, session, token_blacklist 등):
  `common/migrations/0001_table_comments.py` 에서 `COMMENT ON TABLE` 로 직접 관리
- PostGIS geometry 컬럼은 AlterField 로 코멘트가 반영되지 않아 `gyms/migrations/0002_location_column_comment.py` 에서 SQL 로 처리

새 모델을 만들 때 `db_table_comment` 를 함께 적는다.

## 검증 규칙 (모델 ↔ 시리얼라이저)

- 시리얼라이저 필드를 **직접 선언하면 모델 제약이 자동으로 딸려오지 않는다.**
  `max_length`, validator, 필수 여부를 직접 옮겨 적을 것. 빠뜨리면 DB까지 내려가
  `DataError`(500)가 난다 — 검증 실패는 400이어야 한다.
- soft delete 모델의 **중복 검사는 `all_objects` 기준**으로 한다.
  DB의 UNIQUE 제약은 `is_deleted` 를 구분하지 않으므로, `objects` 로 검사하면
  탈퇴 계정의 값이 통과해 `IntegrityError`(500)가 난다.
- 커스텀 Manager 를 쓰는 모델은 `objects` 가 `is_deleted=False` 를 거르는지 확인한다.
  `AUTH_USER_MODEL` 은 `Meta.default_manager_name = "objects"` 도 필요하다
  (`authenticate()` 가 `_default_manager` 를 참조).

## 컬럼 순서 규칙

테이블은 `id → 도메인 컬럼 → FK → 감사 컬럼(created_at, updated_at, is_deleted,
deleted_at)` 순으로 읽히게 맞춰 뒀다.

- Django 는 추상 부모(BaseModel)의 필드를 자식보다 먼저 배치하므로,
  `common/models.py` 의 `AuditFieldsLastMeta` 메타클래스가 `_meta.local_fields` 를
  재배치해 감사 컬럼을 맨 뒤로 보낸다.
- FK 는 마이그레이션 최적화 과정에서 `CreateModel` 끝에 붙는다. 새 모델 추가 후
  생성된 마이그레이션에서 FK 튜플이 감사 컬럼 뒤에 있으면 앞으로 옮긴다.
  (순환 참조로 `AddField` 가 생기면 `accounts/0002_userprofile.py` 처럼
  `CreateModel` 에 인라인으로 합친다.)
- 컬럼 순서는 CREATE TABLE 시점에만 정해진다. 이미 만들어진 테이블의 순서를
  바꾸려면 테이블을 다시 만들어야 한다 (dumpdata → 재생성 → loaddata).

## 구조

```
config/     settings, urls, asgi(Channels), celery
common/     BaseModel(soft delete), 응답 래퍼 렌더러, 커서 페이지네이션, 예외 핸들러
accounts/   User(email 로그인) + UserProfile
gyms/ climbs/ social/ community/ crews/ chat/ analysis/   — 마일스톤별로 채워나감
```
