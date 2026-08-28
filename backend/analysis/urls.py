from django.urls import path

from analysis.views import (
    VideoAnalysisDetailView,
    VideoAnalysisListCreateView,
    VideoAnalysisReportView,
)

app_name = "analysis"

# config.urls 에서 "analyses/" 프리픽스로 include 된다.
urlpatterns = [
    path("", VideoAnalysisListCreateView.as_view(), name="analysis-list"),
    path("<int:pk>/", VideoAnalysisDetailView.as_view(), name="analysis-detail"),
    path(
        "<int:pk>/report/",
        VideoAnalysisReportView.as_view(),
        name="analysis-report",
    ),
]
