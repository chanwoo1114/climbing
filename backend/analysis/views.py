from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from analysis.models import VideoAnalysis
from analysis.serializers import (
    VideoAnalysisRequestSerializer,
    VideoAnalysisSerializer,
)
from analysis.services import (
    owned_analyses,
    request_analysis,
    request_coaching_report,
    visible_analyses,
)

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


@extend_schema(tags=["analysis"])
class VideoAnalysisReportView(generics.GenericAPIView):
    """AI 코칭 리포트 생성 요청 — 기록 작성자만 (남의 분석은 404)."""

    serializer_class = VideoAnalysisSerializer

    def get_queryset(self):
        return owned_analyses(self.request.user)

    @extend_schema(
        request=None,
        responses={
            202: VideoAnalysisSerializer,
            409: OpenApiResponse(
                description=(
                    "analysis_not_done: 자세 분석이 done 이 아님 / "
                    "report_in_progress: 이미 pending·processing 인 리포트가 있음"
                )
            ),
            503: OpenApiResponse(
                description="coaching_not_configured: ANTHROPIC_API_KEY 미설정"
            ),
        },
        description=(
            "완료된(status=done) 자세 분석의 metrics 를 LLM 에 넣어 한국어 markdown "
            "코칭 리포트를 만든다. report_status 가 pending 으로 바뀌고 Celery 가 처리하며, "
            "결과는 GET analyses/{id}/ 의 report_status/report 로 폴링. "
            "none·done(재생성)·failed 에서 요청할 수 있다."
        ),
    )
    def post(self, request, *args, **kwargs):
        analysis = request_coaching_report(self.get_object())
        return Response(
            VideoAnalysisSerializer(analysis).data, status=status.HTTP_202_ACCEPTED
        )
