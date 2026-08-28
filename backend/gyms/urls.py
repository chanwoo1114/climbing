from django.urls import path

from gyms.views import (
    GymDetailView,
    GymDifficultyDetailView,
    GymDifficultyListView,
    GymFacilityReplaceView,
    GymImageCreateView,
    GymImageDeleteView,
    GymImageOrderView,
    GymListView,
    GymManagedListView,
    GymManagerDeleteView,
    GymManagerListCreateView,
    GymPointListView,
    GymPriceReplaceView,
    GymReviewListCreateView,
)

app_name = "gyms"

urlpatterns = [
    path("", GymListView.as_view(), name="list"),
    path("points/", GymPointListView.as_view(), name="points"),
    path("managed/", GymManagedListView.as_view(), name="managed"),
    path("<int:pk>/", GymDetailView.as_view(), name="detail"),
    path(
        "<int:gym_id>/difficulties/",
        GymDifficultyListView.as_view(),
        name="difficulties",
    ),
    path(
        "<int:gym_id>/difficulties/<int:difficulty_id>/",
        GymDifficultyDetailView.as_view(),
        name="difficulty-detail",
    ),
    path("<int:gym_id>/images/", GymImageCreateView.as_view(), name="images"),
    path("<int:gym_id>/images/order/", GymImageOrderView.as_view(), name="image-order"),
    path(
        "<int:gym_id>/images/<int:image_id>/",
        GymImageDeleteView.as_view(),
        name="image-detail",
    ),
    path("<int:gym_id>/prices/", GymPriceReplaceView.as_view(), name="prices"),
    path(
        "<int:gym_id>/facilities/", GymFacilityReplaceView.as_view(), name="facilities"
    ),
    path("<int:gym_id>/managers/", GymManagerListCreateView.as_view(), name="managers"),
    path(
        "<int:gym_id>/managers/<int:user_id>/",
        GymManagerDeleteView.as_view(),
        name="manager-detail",
    ),
    path("<int:gym_id>/reviews/", GymReviewListCreateView.as_view(), name="reviews"),
]
