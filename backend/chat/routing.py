from django.urls import re_path

from chat.consumers import ChatConsumer

# ws/chat/{room_id}/?token=<access JWT> — docs/개발정의.md 6장
websocket_urlpatterns = [
    re_path(r"^ws/chat/(?P<room_id>\d+)/$", ChatConsumer.as_asgi()),
]
