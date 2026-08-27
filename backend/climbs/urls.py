from django.urls import path

from climbs.views import (
    ClimbLogCommentDeleteView,
    ClimbLogCommentListCreateView,
    ClimbLogDetailView,
    ClimbLogLikeView,
    ClimbLogListCreateView,
    FeedView,
    UserLogListView,
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
]
