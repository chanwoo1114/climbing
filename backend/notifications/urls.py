from django.urls import path

from notifications.views import (
    NotificationDeleteView,
    NotificationListView,
    NotificationReadAllView,
    NotificationReadView,
    UnreadCountView,
)

app_name = "notifications"

# config.urls 에서 notifications/ prefix 로 include 된다.
urlpatterns = [
    path("", NotificationListView.as_view(), name="list"),
    path("unread-count/", UnreadCountView.as_view(), name="unread-count"),
    path("read-all/", NotificationReadAllView.as_view(), name="read-all"),
    path("<int:pk>/read/", NotificationReadView.as_view(), name="read"),
    path("<int:pk>/", NotificationDeleteView.as_view(), name="detail"),
]
