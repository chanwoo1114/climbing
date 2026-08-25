from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    """모든 응답을 {"success", "data", "error"} 로 감싼다.

    에러 응답은 common.exceptions.envelope_exception_handler가 이미 형태를
    맞춰두므로 그대로 통과시킨다.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")

        if isinstance(data, dict) and set(data.keys()) == {"success", "data", "error"}:
            payload = data
        elif response is not None and response.status_code >= 400:
            payload = {"success": False, "data": None, "error": data}
        else:
            payload = {"success": True, "data": data, "error": None}

        return super().render(payload, accepted_media_type, renderer_context)
