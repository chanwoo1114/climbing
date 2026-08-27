from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from social import services
from social.models import Follow
from social.serializers import UserSummarySerializer


@extend_schema(tags=["social"], request=None, responses={201: None, 204: None})
class FollowView(APIView):
    """팔로우(POST, 멱등) / 언팔로우(DELETE, 멱등). 자기 자신은 400."""

    def post(self, request, pk: int):
        services.follow_user(follower=request.user, target_id=pk)
        return Response(status=status.HTTP_201_CREATED)

    def delete(self, request, pk: int):
        services.unfollow_user(follower=request.user, target_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class _FollowListView(generics.ListAPIView):
    """Follow 행을 커서 페이지네이션하고, 한쪽 회원(user_attr)만 내려준다.

    회원이 아니라 Follow 행을 페이지네이션하는 이유: 목록 순서가 "팔로우한 시점"
    이어야 하는데 User.created_at 은 가입일이라 쓸 수 없다.
    """

    serializer_class = UserSummarySerializer
    user_attr = ""  # "follower" | "following"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # drf-spectacular 스키마 생성
            return Follow.objects.none()
        generics.get_object_or_404(User, pk=self.kwargs["pk"])
        return self.get_follow_queryset(self.kwargs["pk"])

    def get_follow_queryset(self, user_id: int):
        raise NotImplementedError

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        users = [getattr(follow, self.user_attr) for follow in page]
        context = {
            **self.get_serializer_context(),
            "following_ids": services.following_ids(
                request.user, [user.pk for user in users]
            ),
        }
        serializer = self.get_serializer(users, many=True, context=context)
        return self.get_paginated_response(serializer.data)

    def get_serializer(self, *args, **kwargs):
        # ListAPIView 기본 구현이 context 를 덮어쓰므로 명시한 context 를 우선한다.
        context = kwargs.pop("context", None) or self.get_serializer_context()
        return self.get_serializer_class()(*args, context=context, **kwargs)


@extend_schema(tags=["social"])
class FollowerListView(_FollowListView):
    """{id} 를 팔로우하는 회원 목록. 최근 팔로우 순."""

    user_attr = "follower"

    def get_follow_queryset(self, user_id: int):
        return services.followers_of(user_id)


@extend_schema(tags=["social"])
class FollowingListView(_FollowListView):
    """{id} 가 팔로우하는 회원 목록. 최근 팔로우 순."""

    user_attr = "following"

    def get_follow_queryset(self, user_id: int):
        return services.following_of(user_id)
