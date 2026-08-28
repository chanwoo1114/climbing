from rest_framework import serializers

from analysis.models import VideoAnalysis
from climbs.models import ClimbLog


class VideoAnalysisSerializer(serializers.ModelSerializer):
    """상태 + 결과 + AI 코칭 리포트. keypoints 는 크기 때문에 ?include=keypoints 일 때만."""

    climb_log = serializers.PrimaryKeyRelatedField(read_only=True)
    keypoints = serializers.JSONField(
        read_only=True,
        help_text="샘플링 프레임별 33 랜드마크. 상세 조회에서 ?include=keypoints 일 때만 포함",
    )
    report = serializers.CharField(
        read_only=True,
        help_text="AI 코칭 리포트 본문 (한국어 markdown). done 일 때만 채워짐",
    )

    class Meta:
        model = VideoAnalysis
        fields = (
            "id",
            "climb_log",
            "status",
            "error_message",
            "metrics",
            "keypoints",
            "processed_at",
            "retry_count",
            "report_status",
            "report",
            "report_error",
            "report_model",
            "report_input_tokens",
            "report_output_tokens",
            "report_generated_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def __init__(self, *args, include_keypoints: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        if not (include_keypoints or self.context.get("include_keypoints")):
            self.fields.pop("keypoints")


class VideoAnalysisRequestSerializer(serializers.Serializer):
    """POST analyses/ 입력 — 분석할 기록 id."""

    climb_log = serializers.PrimaryKeyRelatedField(
        queryset=ClimbLog.objects.all(),
        error_messages={
            "required": "분석할 기록을 선택해 주세요.",
            "does_not_exist": "존재하지 않는 기록입니다.",
            "incorrect_type": "기록 id 가 올바르지 않습니다.",
        },
    )
