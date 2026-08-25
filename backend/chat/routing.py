from django.urls import re_path  # noqa: F401

# ws/chat/{room_id}/ — docs/개발정의.md 6장
websocket_urlpatterns = [
    # TODO(M4): re_path(r"^ws/chat/(?P<room_id>\d+)/$", ChatConsumer.as_asgi()),
]
