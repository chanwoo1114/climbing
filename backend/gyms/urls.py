from django.urls import path

from gyms.views import (
    GymDetailView,
    GymDifficultyListView,
    GymListView,
    GymPointListView,
    GymReviewListCreateView,
)

app_name = "gyms"

urlpatterns = [
    path("", GymListView.as_view(), name="list"),
    path("points/", GymPointListView.as_view(), name="points"),
    path("<int:pk>/", GymDetailView.as_view(), name="detail"),
    path(
        "<int:gym_id>/difficulties/",
        GymDifficultyListView.as_view(),
        name="difficulties",
    ),
    path("<int:gym_id>/reviews/", GymReviewListCreateView.as_view(), name="reviews"),
    # TODO(M2): {id}/betas
]
