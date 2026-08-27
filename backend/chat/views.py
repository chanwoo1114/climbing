from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.models import ChatRoomMember, Message
from chat.serializers import (
    ChatRoomDetailSerializer,
    ChatRoomListSerializer,
    DirectRoomRequestSerializer,
    MessageCreateSerializer,
    MessageSerializer,
    ReadSerializer,
)
from chat.services import (
    get_membership,
    get_or_create_direct_room,
    leave_room,
    mark_read,
    my_memberships,
    room_members,
    room_messages,
    send_message,
)
from common.pagination import DefaultCursorPagination


def _get_membership_or_404(request, room_id) -> ChatRoomMember:
    """참여자가 아니면 방의 존재 자체를 숨긴다 (404)."""
    member = get_membership(room_id, request.user)
    if member is None:
        raise Http404("채팅방을 찾을 수 없습니다.")
    return member


class RoomCursorPagination(DefaultCursorPagination):
    """마지막 활동(마지막 메시지 시각, 없으면 생성 시각) 최신순."""

    ordering = "-last_activity_at"


class MessageCursorPagination(DefaultCursorPagination):
    """메시지는 id 역순(최신 먼저). 프론트는 받아서 뒤집어 그린다."""

    ordering = "-id"


@extend_schema(tags=["chat"])
class ChatRoomListView(generics.ListAPIView):
    """내 채팅방 목록 — 최근 활동순 커서 페이지네이션. 항목마다 마지막 메시지·안 읽은 수."""

    queryset = ChatRoomMember.objects.none()  # 스키마 생성용
    serializer_class = ChatRoomListSerializer
    pagination_class = RoomCursorPagination

    def get_queryset(self):
        return my_memberships(self.request.user)


@extend_schema(
    tags=["chat"],
    request=DirectRoomRequestSerializer,
    responses={200: ChatRoomListSerializer, 201: ChatRoomListSerializer},
)
class DirectRoomView(APIView):
    """1:1 방 찾기/만들기 — 있으면 200, 새로 만들면 201. 자기 자신은 400."""

    def post(self, request):
        serializer = DirectRoomRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        room, created = get_or_create_direct_room(
            request.user, serializer.validated_data["user_id"]
        )
        data = ChatRoomListSerializer(my_memberships(request.user).get(room=room)).data
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(data, status=code)


@extend_schema(tags=["chat"], responses=ChatRoomDetailSerializer)
class ChatRoomDetailView(APIView):
    """방 상세 + 참여자 목록. 참여자만 (아니면 404)."""

    def get(self, request, pk):
        _get_membership_or_404(request, pk)
        membership = my_memberships(request.user).get(room_id=pk)
        data = ChatRoomDetailSerializer(
            membership, context={"members": room_members(membership.room)}
        ).data
        return Response(data)


@extend_schema(
    tags=["chat"],
    parameters=[OpenApiParameter("cursor", str), OpenApiParameter("limit", int)],
)
class MessageListCreateView(generics.ListCreateAPIView):
    """메시지 목록(커서, 최신 먼저) + 전송. 전송은 WebSocket 접속자에게도 브로드캐스트."""

    queryset = Message.objects.none()  # 스키마 생성용
    pagination_class = MessageCursorPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MessageCreateSerializer
        return MessageSerializer

    def get_membership(self) -> ChatRoomMember:
        if not hasattr(self, "_membership"):
            self._membership = _get_membership_or_404(self.request, self.kwargs["pk"])
        return self._membership

    def get_queryset(self):
        return room_messages(self.get_membership().room)

    @extend_schema(request=MessageCreateSerializer, responses={201: MessageSerializer})
    def create(self, request, *args, **kwargs):
        member = self.get_membership()
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = send_message(
            member.room, request.user, serializer.validated_data["content"]
        )
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["chat"], request=ReadSerializer, responses={200: ReadSerializer})
class MarkReadView(APIView):
    """읽음 위치 갱신 — 뒤로는 가지 않는다. 응답: 갱신 후 last_read_message_id."""

    def post(self, request, pk):
        member = _get_membership_or_404(request, pk)
        serializer = ReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        last_read = mark_read(member, serializer.validated_data["message_id"])
        return Response({"message_id": last_read})


@extend_schema(tags=["chat"], request=None, responses={204: None})
class LeaveRoomView(APIView):
    """그룹 방 나가기 (1:1 은 400). 시스템 메시지 "OO님이 나갔습니다" 를 남긴다."""

    def delete(self, request, pk):
        leave_room(_get_membership_or_404(request, pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
