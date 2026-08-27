from django.urls import re_path

from notifications.consumers import NotificationConsumer

# ws/notifications/?token=<access JWT>
websocket_urlpatterns = [
    re_path(r"^ws/notifications/$", NotificationConsumer.as_asgi()),
]
