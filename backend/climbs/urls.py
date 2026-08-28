from django.urls import path

from climbs.views import (
    ClimbBetaDetailView,
    ClimbLogCommentDeleteView,
    ClimbLogCommentListCreateView,
    ClimbLogDetailView,
    ClimbLogLikeView,
    ClimbLogListCreateView,
    FeedView,
    GymBetaListCreateView,
    GymBetaSectorListView,
    UserLogListView,
    UserStatsView,
)

app_name = "climbs"

urlpatterns = [
    path("logs/", ClimbLogListCreateView.as_view(), name="log-list"),
    path("logs/<int:pk>/", ClimbLogDetailView.as_view(), name="log-detail"),
    path("logs/<int:pk>/like/", ClimbLogLikeView.as_view(), name="log-like"),
    path(
        "logs/<int:pk>/comments/",
        ClimbLogCommentListCreateView.as_view(),
        name="log-comments",
    ),
    path(
        "logs/<int:pk>/comments/<int:comment_id>/",
        ClimbLogCommentDeleteView.as_view(),
        name="log-comment-detail",
    ),
    path("feed/", FeedView.as_view(), name="feed"),
    path("users/<int:user_id>/logs/", UserLogListView.as_view(), name="user-logs"),
    path("users/<int:user_id>/stats/", UserStatsView.as_view(), name="user-stats"),
    # 베타 영상 — gyms.urls 에 betas 라우트가 없어 여기로 흘러온다 (API 루트에 include).
    path("gyms/<int:gym_id>/betas/", GymBetaListCreateView.as_view(), name="gym-betas"),
    path(
        "gyms/<int:gym_id>/betas/sectors/",
        GymBetaSectorListView.as_view(),
        name="gym-beta-sectors",
    ),
    path("betas/<int:pk>/", ClimbBetaDetailView.as_view(), name="beta-detail"),
]
