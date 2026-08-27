from django.urls import path

from common.views import PresignedUrlView

app_name = "common"

urlpatterns = [
    path("uploads/presigned-url/", PresignedUrlView.as_view(), name="presigned-url"),
]
