from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from common.views import HealthView

api_v1 = [
    path("auth/", include("accounts.urls_auth")),
    path("users/", include("accounts.urls")),
    path("gyms/", include("gyms.urls")),
    path("", include("climbs.urls")),  # logs/, feed/
    path("", include("social.urls")),  # follow 관련
    path("", include("community.urls")),  # posts/, recruitment
    path("crews/", include("crews.urls")),
    path("chat/", include("chat.urls")),
    path("analyses/", include("analysis.urls")),
    path("", include("common.urls")),  # uploads/presigned-url
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthView.as_view(), name="health"),
    path("api/v1/", include((api_v1, "v1"))),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
