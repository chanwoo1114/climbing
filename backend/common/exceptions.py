from rest_framework.views import exception_handler as drf_exception_handler


def _error_code(exc, response):
    code = getattr(exc, "default_code", None)
    return str(code) if code else f"http_{response.status_code}"


def _error_message(response):
    detail = response.data
    if isinstance(detail, dict):
        if "detail" in detail:
            return str(detail["detail"])
        # 필드 검증 에러 — 첫 필드의 첫 메시지를 대표 메시지로.
        for value in detail.values():
            if isinstance(value, (list, tuple)) and value:
                return str(value[0])
        return "요청을 처리할 수 없습니다."
    if isinstance(detail, (list, tuple)) and detail:
        return str(detail[0])
    return str(detail)


def envelope_exception_handler(exc, context):
    """{"success": false, "error": {"code", "message"}} 형태로 통일."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    error = {
        "code": _error_code(exc, response),
        "message": _error_message(response),
    }
    if isinstance(response.data, dict) and "detail" not in response.data:
        error["fields"] = response.data

    response.data = {"success": False, "data": None, "error": error}
    return response
