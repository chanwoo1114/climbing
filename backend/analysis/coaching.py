"""AI 코칭 리포트 — 자세 분석 metrics 를 LLM(Anthropic Messages API)에 넣어 한국어 리포트 생성.

    is_configured()               API 키가 설정돼 있는지
    build_user_prompt(analysis)   metrics + 기록 맥락 + 지표 용어집을 담은 사용자 프롬프트
    generate_report(analysis)     API 호출 → report_* 필드 저장 (Celery 태스크에서만 부른다)

SDK 오류는 CoachingError 로 바꿔 던진다. retryable=True(429/5xx/네트워크)만 태스크가 1회 재시도.
테스트는 `analysis.coaching._client` 를 mock 한다.
"""

import json
import logging

import anthropic
from django.conf import settings
from django.utils import timezone

from analysis.models import VideoAnalysis
from notifications.services import notify_report_status

logger = logging.getLogger(__name__)

MEMO_MAX_CHARS = 300
TRUNCATED_NOTE = (
    "\n\n> 리포트가 길이 제한으로 잘렸습니다. 다시 생성하면 전체 내용을 볼 수 있습니다."
)

ERROR_MESSAGES = {
    "refusal": "리포트를 생성할 수 없는 내용입니다.",
    "empty": "리포트 내용을 받지 못했습니다. 다시 시도해 주세요.",
    "auth": "AI 코칭 서비스 인증에 실패했습니다. 관리자에게 문의해 주세요.",
    "bad_request": "AI 코칭 요청이 거부되었습니다. 관리자에게 문의해 주세요.",
    "rate_limit": "AI 코칭 서비스 요청이 많습니다. 잠시 후 다시 시도해 주세요.",
    "server": "AI 코칭 서비스에 일시적인 문제가 있습니다. 잠시 후 다시 시도해 주세요.",
    "connection": "AI 코칭 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    "timeout": "리포트 생성 시간이 초과되었습니다. 다시 시도해 주세요.",
    "unknown": "리포트 생성 중 오류가 발생했습니다.",
}

SYSTEM_PROMPT = """당신은 볼더링·스포츠클라이밍 전문 코치입니다.
사용자의 등반 영상 한 편을 MediaPipe Pose 로 분석한 지표(JSON)와 기록 정보를 받아,
간결하고 격려하는 어조의 한국어 코칭 리포트를 **markdown** 으로 작성합니다.

반드시 아래 섹션 구성과 순서를 지키세요.

## 한눈에 보기
이번 등반을 2~3문장으로 요약합니다.

## 잘한 점
지표로 확인되는 좋은 부분을 항목별로 적습니다.

## 개선 포인트
항목마다 "관찰된 지표 → 왜 중요한지 → 구체적인 교정 팁" 순서로 씁니다.

## 추천 훈련
개선 포인트와 연결되는 드릴 2~3개를 제안합니다 (방법과 반복 횟수/시간 포함).

## 주의
이 분석의 한계를 짧게 밝힙니다: 2D 추정(깊이 없음), 카메라 각도·거리에 따른 오차,
가려진 관절, 벽 각도나 홀드 정보는 알 수 없음 등.

규칙:
- 데이터에 없는 숫자를 지어내지 마세요. 지표가 비어 있거나(null) 없으면 그 사실을 짧게 언급하고
  해당 항목은 일반적인 조언으로 대신합니다.
- 지표 값을 인용할 때는 단위와 의미(정규화 좌표, 도 등)를 자연스럽게 풀어 씁니다.
- 초보자도 이해할 수 있는 말로 쓰되, 전문 용어는 한 번 설명한 뒤 사용합니다.
- 전체 분량은 한국어 기준 600단어 이내로 유지합니다.
- 앞뒤 인사말 없이 첫 줄부터 `## 한눈에 보기` 로 시작합니다."""

# analysis/pipeline.py compute_metrics() 가 만드는 키 설명 — 프롬프트에 그대로 들어간다.
METRICS_GLOSSARY = """지표(metrics) 용어집 — 좌표는 프레임 크기로 정규화한 0~1 값이고 y 는 아래로 갈수록 커집니다.
- duration: 분석한 영상 길이(초)
- sample_fps: 자세를 추출한 샘플링 fps
- frame_count / detected_frames / detection_rate: 샘플링 프레임 수 / 자세를 찾은 프레임 수 / 비율(0~1)
- com: 어깨·엉덩이 네 점의 평균을 무게중심(COM)으로 본 요약 (자세를 못 찾으면 null)
  - trajectory: [[시각(초), x, y], ...] 무게중심 궤적 (최대 120점으로 줄인 것)
  - path_length: 무게중심이 움직인 총 거리 (정규화 좌표 단위, 클수록 많이 움직임)
  - vertical_gain: 시작 높이 대비 가장 높이 올라간 양 (시작 y − 최소 y, 클수록 많이 상승)
  - vertical_range: 상하 이동 폭 (최대 y − 최소 y)
  - start / end: 시작·끝 무게중심 [x, y]
- joint_angles: 관절 각도(도)의 mean/min/max — left_elbow, right_elbow(어깨-팔꿈치-손목),
  left_knee, right_knee(엉덩이-무릎-발목), left_hip, right_hip(어깨-엉덩이-무릎).
  180도에 가까울수록 곧게 편 상태, 작을수록 많이 굽힌 상태.
- move_ratio: 무게중심 속도가 speed_threshold(정규화 좌표/초)를 넘는 구간 비율
  - dynamic: 동적으로 움직인 구간 비율(0~1), static: 홀드를 잡고 버틴 정적 구간 비율
  - speed_threshold: 동적/정적을 가른 속도 기준값"""


class CoachingError(Exception):
    """리포트 생성 실패. message 는 그대로 사용자에게 보여줄 수 있는 문장.

    retryable=True 인 오류(429/5xx/네트워크)만 태스크가 1회 재시도한다.
    """

    def __init__(self, code: str, message: str | None = None, *, retryable=False):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, ERROR_MESSAGES["unknown"])
        self.retryable = retryable
        super().__init__(f"{code}: {self.message}")


def is_configured() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def _client() -> anthropic.Anthropic:
    """모듈 함수로 둔다 — 테스트가 `analysis.coaching._client` 를 mock 한다."""
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# --- 프롬프트 ---------------------------------------------------------------


def _log_context(analysis: VideoAnalysis) -> dict:
    log = analysis.climb_log
    difficulty = log.difficulty
    memo = (log.memo or "").strip()
    if len(memo) > MEMO_MAX_CHARS:
        memo = memo[:MEMO_MAX_CHARS] + "…"
    return {
        "gym": log.gym.name if log.gym_id else None,
        "difficulty": (
            {"name": difficulty.name, "order": difficulty.order} if difficulty else None
        ),
        "is_success": log.is_success,
        "attempts": log.attempts,
        "memo": memo or None,
        "video_duration_seconds": (analysis.metrics or {}).get("duration"),
    }


def build_user_prompt(analysis: VideoAnalysis) -> str:
    metrics = analysis.metrics or {}
    context = _log_context(analysis)
    return "\n\n".join(
        [
            "다음 등반 기록의 자세 분석 결과로 코칭 리포트를 작성해 주세요.",
            "기록 정보 (difficulty.order 는 암장 내 난이도 순서, 클수록 어려움):\n"
            + json.dumps(context, ensure_ascii=False, indent=2),
            METRICS_GLOSSARY,
            "자세 분석 지표 (metrics):\n"
            + json.dumps(metrics, ensure_ascii=False, indent=2),
        ]
    )


# --- 생성 -------------------------------------------------------------------


def _translate_error(exc: anthropic.APIError) -> CoachingError:
    """SDK 예외 → CoachingError. 구체적인 클래스부터 확인한다."""
    if isinstance(exc, anthropic.AuthenticationError):
        return CoachingError("auth")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return CoachingError("auth")
    if isinstance(exc, anthropic.NotFoundError):
        return CoachingError("bad_request")
    if isinstance(exc, anthropic.BadRequestError):
        return CoachingError("bad_request")
    if isinstance(exc, anthropic.RateLimitError):
        return CoachingError("rate_limit", retryable=True)
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code >= 500:
            return CoachingError("server", retryable=True)
        return CoachingError("bad_request")
    if isinstance(exc, anthropic.APITimeoutError):
        return CoachingError("timeout", retryable=True)
    if isinstance(exc, anthropic.APIConnectionError):
        return CoachingError("connection", retryable=True)
    return CoachingError("unknown")


def _text_of(response) -> str:
    parts = [
        block.text
        for block in (response.content or [])
        if getattr(block, "type", None) == "text" and getattr(block, "text", "")
    ]
    return "\n".join(parts).strip()


def generate_report(analysis: VideoAnalysis) -> VideoAnalysis:
    """LLM 호출 → report_* 저장. 실패는 CoachingError 로 던진다 (호출자가 failed 처리)."""
    if not is_configured():
        raise CoachingError("auth")

    try:
        response = _client().messages.create(
            model=settings.COACHING_MODEL,
            max_tokens=settings.COACHING_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(analysis)}],
            output_config={"effort": settings.COACHING_EFFORT},
        )
    except anthropic.APIError as exc:
        raise _translate_error(exc) from exc

    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        logger.warning(
            "coaching: analysis %s refused (category=%s)",
            analysis.id,
            getattr(details, "category", None) if details else None,
        )
        raise CoachingError("refusal")

    text = _text_of(response)
    if not text:
        raise CoachingError("empty")
    if stop_reason == "max_tokens":
        # 잘린 리포트도 쓸모는 있으니 저장하되, 잘렸음을 본문 끝에 알린다.
        text += TRUNCATED_NOTE

    usage = getattr(response, "usage", None)
    analysis.report = text
    analysis.report_error = ""
    analysis.report_model = str(getattr(response, "model", "") or "")[:64]
    analysis.report_input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    analysis.report_output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    analysis.report_status = VideoAnalysis.ReportStatus.DONE
    analysis.report_generated_at = timezone.now()
    analysis.save(
        update_fields=[
            "report",
            "report_error",
            "report_model",
            "report_input_tokens",
            "report_output_tokens",
            "report_status",
            "report_generated_at",
            "updated_at",
        ]
    )
    notify_report_status(analysis)  # 완료 알림 (기록 작성자에게)
    return analysis
