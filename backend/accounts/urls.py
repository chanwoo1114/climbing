from django.urls import path

from accounts.views import MeView, UserDetailView, UserSearchView

app_name = "accounts"

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    # search/ 는 <int:pk>/ 보다 먼저 (숫자가 아니라 겹치진 않지만 의도를 분명히).
    path("search/", UserSearchView.as_view(), name="search"),
    path("<int:pk>/", UserDetailView.as_view(), name="detail"),
    # TODO(M2): {id}/logs — climbs 앱 ClimbLog 준비 후
    # {id}/follow, {id}/followers, {id}/following 은 social/urls.py 에 있다.
]
