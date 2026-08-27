from django.urls import path

from social.views import FollowerListView, FollowingListView, FollowView

app_name = "social"

# config.urls 에서 prefix 없이 include 되므로 users/ 부터 전체 경로를 적는다.
urlpatterns = [
    path("users/<int:pk>/follow/", FollowView.as_view(), name="follow"),
    path("users/<int:pk>/followers/", FollowerListView.as_view(), name="followers"),
    path("users/<int:pk>/following/", FollowingListView.as_view(), name="following"),
]
