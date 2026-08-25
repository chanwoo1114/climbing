from django.urls import path

from accounts.views import MeView

app_name = "accounts"

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    # TODO(M1~M3): {id}, {id}/logs, {id}/follow, search?q=
]
