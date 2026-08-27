from django.urls import path

from chat.views import (
    ChatRoomDetailView,
    ChatRoomListView,
    DirectRoomView,
    LeaveRoomView,
    MarkReadView,
    MessageListCreateView,
)

app_name = "chat"

urlpatterns = [
    path("rooms/", ChatRoomListView.as_view(), name="room-list"),
    path("rooms/direct/", DirectRoomView.as_view(), name="room-direct"),
    path("rooms/<int:pk>/", ChatRoomDetailView.as_view(), name="room-detail"),
    path(
        "rooms/<int:pk>/messages/",
        MessageListCreateView.as_view(),
        name="room-messages",
    ),
    path("rooms/<int:pk>/read/", MarkReadView.as_view(), name="room-read"),
    path("rooms/<int:pk>/leave/", LeaveRoomView.as_view(), name="room-leave"),
]
