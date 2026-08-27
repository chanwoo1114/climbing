from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications import services
from notifications.models import Notification
from notifications.serializers import (
    NotificationSerializer,
    ReadAllSerializer,
    UnreadCountSerializer,
)


def _get_my_notification(request, pk) -> Notification:
    """내 알림만. 남의 알림은 존재 자체를 숨긴다 (404)."""
    return get_object_or_404(
        Notification.objects.select_related("actor__profile"),
        pk=pk,
        recipient=request.user,
    )


@extend_schema(
    tags=["notifications"],
    parameters=[
        OpenApiParameter(
            "unread", bool, description="true 면 읽지 않은 알림만", required=False
        )
    ],
)
class NotificationListView(generics.ListAPIView):
    """내 알림 목록 (커서, 최신순). ?unread=true 로 안 읽은 것만."""

    queryset = Notification.objects.none()  # 스키마 생성용
    serializer_class = NotificationSerializer

    def get_queryset(self):
        unread = self.request.query_params.get("unread", "").lower() in ("1", "true")
        return services.notifications_of(self.request.user, unread_only=unread)


@extend_schema(tags=["notifications"], responses=UnreadCountSerializer)
class UnreadCountView(APIView):
    """읽지 않은 알림 수 (헤더 뱃지용)."""

    def get(self, request):
        return Response({"count": services.unread_count(request.user)})


@extend_schema(tags=["notifications"], request=None, responses=NotificationSerializer)
class NotificationReadView(APIView):
    """알림 한 건 읽음 처리 (멱등). 갱신된 알림을 돌려준다."""

    def post(self, request, pk):
        notification = services.mark_read(_get_my_notification(request, pk))
        return Response(NotificationSerializer(notification).data)


@extend_schema(tags=["notifications"], request=None, responses=ReadAllSerializer)
class NotificationReadAllView(APIView):
    """내 알림 전체 읽음 처리. 갱신된 건수를 돌려준다."""

    def post(self, request):
        return Response({"updated": services.mark_all_read(request.user)})


@extend_schema(tags=["notifications"], responses={204: None})
class NotificationDeleteView(APIView):
    """알림 삭제 (soft)."""

    def delete(self, request, pk):
        _get_my_notification(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
