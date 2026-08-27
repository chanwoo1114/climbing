from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from analysis.models import VideoAnalysis
from analysis.serializers import (
    VideoAnalysisRequestSerializer,
    VideoAnalysisSerializer,
)
from analysis.services import request_analysis, visible_analyses

INCLUDE_KEYPOINTS = "keypoints"


@extend_schema(tags=["analysis"])
class VideoAnalysisListCreateView(generics.ListCreateAPIView):
    """영상 분석 요청(POST) + 조회 가능한 분석 목록(GET, ?climb_log= 로 기록별 조회)."""

    queryset = VideoAnalysis.objects.none()  # 스키마 생성용 — 실제 조회는 get_queryset
    filterset_fields = ("climb_log",)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VideoAnalysisRequestSerializer
        return VideoAnalysisSerializer

    def get_queryset(self):
        return visible_analyses(self.request.user)

    @extend_schema(
        request=VideoAnalysisRequestSerializer,
        responses={
            202: VideoAnalysisSerializer,
            200: VideoAnalysisSerializer,
        },
        description=(
            "기록 작성자만 요청할 수 있고 영상(video_url)이 있어야 한다. "
            "기록당 1건 — 이미 대기/진행/완료된 분석이 있으면 200 으로 그대로 돌려주고, "
            "failed 면 초기화 후 다시 큐에 넣는다(202). 결과는 GET analyses/{id}/ 로 폴링."
        ),
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        analysis, enqueued = request_analysis(
            serializer.validated_data["climb_log"], request.user
        )
        data = VideoAnalysisSerializer(analysis).data
        code = status.HTTP_202_ACCEPTED if enqueued else status.HTTP_200_OK
        return Response(data, status=code)


@extend_schema(
    tags=["analysis"],
    parameters=[
        OpenApiParameter(
            "include",
            str,
            enum=[INCLUDE_KEYPOINTS],
            description="keypoints 를 응답에 포함하려면 include=keypoints (용량 큼)",
        )
    ],
)
class VideoAnalysisDetailView(generics.RetrieveAPIView):
    """분석 상태/결과 — 기록 작성자 또는 공개(is_shared) 기록이면 누구나."""

    serializer_class = VideoAnalysisSerializer

    def get_queryset(self):
        return visible_analyses(self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        include = self.request.query_params.get("include", "")
        context["include_keypoints"] = INCLUDE_KEYPOINTS in include.split(",")
        return context
