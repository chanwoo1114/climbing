from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications import push, services
from notifications.exceptions import PushNotConfigured
from notifications.models import Notification
from notifications.serializers import (
    NotificationSerializer,
    NotificationSettingSerializer,
    PushPublicKeySerializer,
    PushSubscribeSerializer,
    PushSubscriptionSerializer,
    PushUnsubscribeSerializer,
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


@extend_schema(tags=["notifications"])
class NotificationSettingView(APIView):
    """내 알림 채널 설정 (푸시/이메일). GET 은 없으면 기본값으로 만들어 돌려준다."""

    @extend_schema(responses=NotificationSettingSerializer)
    def get(self, request):
        setting = services.get_or_create_setting(request.user)
        return Response(NotificationSettingSerializer(setting).data)

    @extend_schema(
        request=NotificationSettingSerializer, responses=NotificationSettingSerializer
    )
    def patch(self, request):
        serializer = NotificationSettingSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        setting = services.update_setting(request.user, **serializer.validated_data)
        return Response(NotificationSettingSerializer(setting).data)


def _require_push_configured() -> None:
    if not push.is_configured():
        raise PushNotConfigured()


@extend_schema(tags=["notifications"], responses={200: PushPublicKeySerializer})
class PushPublicKeyView(APIView):
    """VAPID 공개키 — 브라우저가 pushManager.subscribe 할 때 쓴다. 미설정이면 503."""

    def get(self, request):
        _require_push_configured()
        return Response({"public_key": settings.WEBPUSH_VAPID_PUBLIC_KEY})


@extend_schema(tags=["notifications"])
class PushSubscriptionView(APIView):
    """Web Push 구독 등록(POST, endpoint 기준 upsert) / 해지(DELETE, 멱등)."""

    @extend_schema(
        request=PushSubscribeSerializer, responses={201: PushSubscriptionSerializer}
    )
    def post(self, request):
        _require_push_configured()
        serializer = PushSubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subscription = services.subscribe_push(
            request.user,
            endpoint=data["endpoint"],
            p256dh=data["keys"]["p256dh"],
            auth=data["keys"]["auth"],
            user_agent=data.get("user_agent", ""),
        )
        return Response(
            PushSubscriptionSerializer(subscription).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=PushUnsubscribeSerializer, responses={204: None})
    def delete(self, request):
        serializer = PushUnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.unsubscribe_push(
            request.user, endpoint=serializer.validated_data["endpoint"]
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
