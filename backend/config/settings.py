import sys
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5180"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# --- Applications ---------------------------------------------------------
DJANGO_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "channels",
]

LOCAL_APPS = [
    "common",
    "accounts",
    "gyms",
    "climbs",
    "social",
    "community",
    "crews",
    "chat",
    "analysis",
    "notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database (PostGIS) ---------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": env("POSTGRES_DB", default="climbing"),
        "USER": env("POSTGRES_USER", default="climbing"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="climbing"),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env.int("POSTGRES_PORT", default=5432),
        "CONN_MAX_AGE": 60,
        # TEST_DB_NAME: 테스트를 동시에 여러 개 돌릴 때(에이전트 병렬 작업 등) 이름 충돌 방지.
        #   dc exec -e TEST_DB_NAME=test_climbing_x web python manage.py test <app>
        "TEST": {
            "TEMPLATE": "template_postgis",
            "NAME": env("TEST_DB_NAME", default=None),
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
        # 기본값은 username/first_name/last_name/email 이라 nickname 이 빠진다.
        # 이 검사는 validate_password(password, user=...) 로 user 를 넘겨야 동작한다.
        "OPTIONS": {"user_attributes": ("email", "nickname"), "max_similarity": 0.7},
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    # 한국 웹 관행 (accounts/validators.py — 프론트 체크리스트와 동일 유지)
    {"NAME": "accounts.validators.MaximumLengthValidator"},
    {"NAME": "accounts.validators.CharacterComboValidator"},
    {"NAME": "accounts.validators.SequentialCharacterValidator"},
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- DRF ------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # 기본은 인증 필수. 공개 엔드포인트만 명시적으로 AllowAny.
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("common.renderers.EnvelopeJSONRenderer",),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.DefaultCursorPagination",
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "EXCEPTION_HANDLER": "common.exceptions.envelope_exception_handler",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # 전역 throttle 은 걸지 않는다. accounts/throttles.py 의 클래스를 뷰에 직접 붙인다.
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",  # 비밀번호 무차별 대입
        "register": "5/hour",  # 봇 대량 가입
        "email_send": "5/hour",  # 인증 메일 재전송·재설정 요청
        "token_confirm": "10/min",  # 토큰 추측
        "social_login": "10/min",  # 카카오 콜백 (code 는 1회용)
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Climbing API",
    # 같은 필드명(join_type) 의 enum 이 앱마다 달라 이름이 충돌한다 — 명시적으로 분리
    "ENUM_NAME_OVERRIDES": {
        "RecruitmentJoinTypeEnum": "community.models.RECRUITMENT_JOIN_TYPE_CHOICES",
        "CrewJoinTypeEnum": "crews.models.CREW_JOIN_TYPE_CHOICES",
        "NotificationTypeEnum": "notifications.models.NOTIFICATION_TYPE_CHOICES",
    },
    "DESCRIPTION": "클라이밍 암장 정보 + 등반 기록 SNS + 커뮤니티 + AI 자세 분석",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
}

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# --- 이메일 인증 / 비밀번호 재설정 ----------------------------------------
# 메일 링크가 가리키는 프론트 주소 (/verify-email, /reset-password 라우트).
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:5180").rstrip(
    "/"
)
EMAIL_VERIFICATION_TIMEOUT = env.int("EMAIL_VERIFICATION_TIMEOUT", default=60 * 60 * 24)
PASSWORD_RESET_TIMEOUT = env.int("PASSWORD_RESET_TIMEOUT", default=60 * 60)

# --- 카카오 소셜 로그인 (accounts/social) ---------------------------------
# client_id 는 카카오 developers 의 REST API 키. 암장 수집용 KAKAO_REST_API_KEY 와
# 같은 앱을 쓰면 그 값을 그대로 재사용한다. 비어 있으면 API 가 503 kakao_not_configured.
KAKAO_CLIENT_ID = env("KAKAO_CLIENT_ID", default=env("KAKAO_REST_API_KEY", default=""))
# 카카오 콘솔에서 "Client Secret" 을 켠 경우에만 채운다.
KAKAO_CLIENT_SECRET = env("KAKAO_CLIENT_SECRET", default="")
# 카카오 콘솔 Redirect URI 에 등록한 프론트 라우트. 콜백은 프론트가 받아서
# code/state 를 POST /api/v1/auth/kakao/callback/ 으로 넘긴다.
KAKAO_REDIRECT_URI = env(
    "KAKAO_REDIRECT_URI", default=f"{FRONTEND_BASE_URL}/auth/kakao/callback"
)
# authorize 에서 발급한 state 의 유효 시간(초)
KAKAO_STATE_TIMEOUT = env.int("KAKAO_STATE_TIMEOUT", default=600)

# 개발 기본은 콘솔 출력 — 메일 본문이 celery 워커 로그에 찍힌다.
# 프로덕션은 .env 에서 smtp 백엔드와 호스트 정보를 채운다.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Climbing <noreply@localhost>")

# --- Redis / Channels / Celery -------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")

# throttle 카운터 저장소. 프로세스 메모리(LocMem)면 워커마다 따로 세서 한도가
# 사실상 N배가 되므로 Redis 로 공유한다. 브로커(db 0)와 DB 번호를 분리.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("CACHE_URL", default="redis://redis:6379/2"),
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TIMEZONE = TIME_ZONE

# --- S3 (presigned URL 업로드) -------------------------------------------
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="ap-northeast-2")
# MinIO / Cloudflare R2 등 S3 호환 스토리지용. 비우면 AWS 기본 엔드포인트.
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="") or None
# 업로드된 파일의 공개 URL 베이스 (CDN). 비우면 버킷 URL 로 만든다.
MEDIA_PUBLIC_BASE_URL = env("MEDIA_PUBLIC_BASE_URL", default="").rstrip("/")
S3_PRESIGNED_EXPIRE_SECONDS = env.int("S3_PRESIGNED_EXPIRE_SECONDS", default=300)

# --- 영상 분석 제약 (docs/개발정의.md 4장) --------------------------------
ANALYSIS_MAX_VIDEO_SECONDS = env.int("ANALYSIS_MAX_VIDEO_SECONDS", default=120)
ANALYSIS_SAMPLE_FPS = env.int("ANALYSIS_SAMPLE_FPS", default=10)

# --- 알림 팬아웃 (notifications) ---------------------------------------------
# Web Push (VAPID). 키가 비어 있으면 푸시 팬아웃은 조용히 건너뛰고 구독 등록 API 는
# 503 push_not_configured 를 돌려준다. 키 생성은 `dc exec web vapid --gen` (pywebpush 동봉)
# — 자세한 절차는 .env.example 참고.
WEBPUSH_VAPID_PUBLIC_KEY = env("WEBPUSH_VAPID_PUBLIC_KEY", default="")
WEBPUSH_VAPID_PRIVATE_KEY = env("WEBPUSH_VAPID_PRIVATE_KEY", default="")
# VAPID claims 의 sub (mailto:). 푸시 서비스가 문제 발생 시 연락할 주소.
WEBPUSH_VAPID_CLAIMS_EMAIL = env("WEBPUSH_VAPID_CLAIMS_EMAIL", default="")
WEBPUSH_TTL_SECONDS = env.int("WEBPUSH_TTL_SECONDS", default=86400)
# 이메일 팬아웃 전체 스위치 (사용자별 설정과 AND). 발송 자체는 EMAIL_BACKEND 설정을 따른다.
NOTIFICATION_EMAIL_ENABLED = env.bool("NOTIFICATION_EMAIL_ENABLED", default=True)

# --- AI 코칭 리포트 (analysis.coaching) ---------------------------------------
# 비어 있으면 리포트 생성 API 가 503 coaching_not_configured 를 돌려준다.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
COACHING_MODEL = env("COACHING_MODEL", default="claude-opus-5")
COACHING_MAX_TOKENS = env.int("COACHING_MAX_TOKENS", default=4096)
COACHING_EFFORT = env("COACHING_EFFORT", default="medium")

# --- 테스트 전용 오버라이드 --------------------------------------------------
if "test" in sys.argv:
    # throttle 카운터가 테스트 간에 누적되지 않게 (throttle 테스트는 LocMem 으로 override).
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    # 메일 태스크를 큐에 넣지 않고 즉시 실행 → mail.outbox 로 검증.
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
