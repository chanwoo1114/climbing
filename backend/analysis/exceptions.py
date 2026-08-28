"""analysis 도메인 API 예외 — common.exceptions 의 envelope 핸들러가 code/message 로 감싼다."""

from rest_framework import status
from rest_framework.exceptions import APIException


class VideoRequired(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "분석할 영상이 없습니다. 기록에 영상을 먼저 올려 주세요."
    default_code = "video_required"


class CoachingNotConfigured(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "AI 코칭 리포트 기능이 아직 설정되지 않았습니다."
    default_code = "coaching_not_configured"


class AnalysisNotDone(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "자세 분석이 완료된 뒤 리포트를 만들 수 있습니다."
    default_code = "analysis_not_done"


class ReportInProgress(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "리포트를 생성하는 중입니다. 잠시 후 결과를 확인해 주세요."
    default_code = "report_in_progress"
