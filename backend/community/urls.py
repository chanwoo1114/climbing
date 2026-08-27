from django.urls import path

from community.views import (
    ParticipantListView,
    ParticipantUpdateView,
    PostCommentDeleteView,
    PostCommentListCreateView,
    PostDetailView,
    PostListCreateView,
    RecruitmentCancelView,
    RecruitmentCloseView,
    RecruitmentJoinView,
)

app_name = "community"

urlpatterns = [
    path("posts/", PostListCreateView.as_view(), name="post-list"),
    path("posts/<int:pk>/", PostDetailView.as_view(), name="post-detail"),
    path(
        "posts/<int:pk>/comments/",
        PostCommentListCreateView.as_view(),
        name="post-comments",
    ),
    path(
        "posts/<int:pk>/comments/<int:comment_id>/",
        PostCommentDeleteView.as_view(),
        name="post-comment-detail",
    ),
    path(
        "posts/<int:pk>/recruitment/join/",
        RecruitmentJoinView.as_view(),
        name="recruitment-join",
    ),
    path(
        "posts/<int:pk>/recruitment/cancel/",
        RecruitmentCancelView.as_view(),
        name="recruitment-cancel",
    ),
    path(
        "posts/<int:pk>/recruitment/participants/",
        ParticipantListView.as_view(),
        name="recruitment-participants",
    ),
    path(
        "posts/<int:pk>/recruitment/participants/<int:user_id>/",
        ParticipantUpdateView.as_view(),
        name="recruitment-participant-detail",
    ),
    path(
        "posts/<int:pk>/recruitment/close/",
        RecruitmentCloseView.as_view(),
        name="recruitment-close",
    ),
]
