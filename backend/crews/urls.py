from django.urls import path

from crews.views import (
    CrewDetailView,
    CrewFeedView,
    CrewJoinView,
    CrewLeaveView,
    CrewListCreateView,
    CrewMemberDetailView,
    CrewMemberListView,
    CrewRankingView,
    CrewRecruitmentListView,
    CrewStatsView,
)

app_name = "crews"

urlpatterns = [
    path("", CrewListCreateView.as_view(), name="crew-list"),
    path("ranking/", CrewRankingView.as_view(), name="crew-ranking"),
    path("<int:pk>/", CrewDetailView.as_view(), name="crew-detail"),
    path("<int:pk>/members/", CrewMemberListView.as_view(), name="crew-members"),
    path(
        "<int:pk>/members/<int:user_id>/",
        CrewMemberDetailView.as_view(),
        name="crew-member-detail",
    ),
    path("<int:pk>/join/", CrewJoinView.as_view(), name="crew-join"),
    path("<int:pk>/leave/", CrewLeaveView.as_view(), name="crew-leave"),
    path("<int:pk>/feed/", CrewFeedView.as_view(), name="crew-feed"),
    path("<int:pk>/stats/", CrewStatsView.as_view(), name="crew-stats"),
    path(
        "<int:pk>/recruitments/",
        CrewRecruitmentListView.as_view(),
        name="crew-recruitments",
    ),
]
