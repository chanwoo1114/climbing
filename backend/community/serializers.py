from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from community.models import (
    RECRUIT_CAPACITY_MAX,
    RECRUIT_CAPACITY_MIN,
    Participation,
    Post,
    PostComment,
    Recruitment,
)
from community.services import MAX_IMAGES, approved_count, create_post, update_post
from crews.exceptions import NotCrewMember
from crews.models import Crew
from crews.serializers import CrewSummarySerializer
from crews.services import is_active_member
from gyms.models import Gym

TITLE_MAX_LENGTH = 100
CONTENT_MAX_LENGTH = 5000
PREVIEW_LENGTH = 200
COMMENT_MAX_LENGTH = 500


class PostUserSerializer(serializers.ModelSerializer):
    """작성자/참여자 요약. image 는 프로필에서 (select_related user__profile 전제)."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "nickname", "image")
        read_only_fields = fields

    def get_image(self, obj) -> str | None:
        try:
            return obj.profile.image or None
        except User.profile.RelatedObjectDoesNotExist:
            return None


class PostGymSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gym
        fields = ("id", "name")
        read_only_fields = fields


# --- 모집 ---------------------------------------------------------------------


class RecruitmentSerializer(serializers.ModelSerializer):
    """읽기 전용. approved_count(작성자 제외 승인 인원)·my_participation_status 는
    services.annotated_posts 의 주석값을 PostSerializer 가 옮겨 담는다."""

    gym = PostGymSerializer(read_only=True)
    approved_count = serializers.IntegerField(
        read_only=True, help_text="승인된 참여자 수 (작성자 제외). 정원은 작성자 포함"
    )
    my_participation_status = serializers.CharField(read_only=True, allow_null=True)
    chat_room_id = serializers.IntegerField(read_only=True, allow_null=True)
    crew = serializers.SerializerMethodField(
        help_text="크루 주최 모집이면 {id, name}, 개인 모집이면 null"
    )

    class Meta:
        model = Recruitment
        fields = (
            "id",
            "gym",
            "meet_at",
            "capacity",
            "join_type",
            "status",
            "approved_count",
            "my_participation_status",
            "chat_room_id",
            "crew",
        )
        read_only_fields = fields

    def get_crew(self, obj) -> dict | None:
        crew = obj.crew if obj.crew_id else None
        # FK 는 삭제분도 따라가므로 soft delete 된 크루는 개인 모집처럼 보여준다.
        if crew is None or crew.is_deleted:
            return None
        return CrewSummarySerializer(crew).data


class RecruitmentWriteSerializer(serializers.ModelSerializer):
    """모집글 작성/수정 시 nested 로 받는 입력."""

    gym = serializers.PrimaryKeyRelatedField(queryset=Gym.objects.all())
    capacity = serializers.IntegerField(
        min_value=RECRUIT_CAPACITY_MIN,
        max_value=RECRUIT_CAPACITY_MAX,
        error_messages={
            "min_value": f"정원은 {RECRUIT_CAPACITY_MIN}명 이상이어야 합니다.",
            "max_value": f"정원은 {RECRUIT_CAPACITY_MAX}명 이하여야 합니다.",
        },
    )

    crew = serializers.PrimaryKeyRelatedField(
        queryset=Crew.objects.all(),
        allow_null=True,
        required=False,
        error_messages={"does_not_exist": "존재하지 않는 크루입니다."},
        help_text="크루 주최 모집이면 크루 id (활동 중인 크루원만). 생략/null 이면 개인 모집",
    )

    class Meta:
        model = Recruitment
        fields = ("gym", "meet_at", "capacity", "join_type", "crew")

    def validate_meet_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("모임 일시는 현재 이후여야 합니다.")
        return value

    def validate_crew(self, crew):
        if crew is None:
            return crew
        if not is_active_member(crew, self.context["request"].user):
            raise NotCrewMember("가입한 크루만 주최 크루로 지정할 수 있습니다.")
        return crew


# --- 게시글 -------------------------------------------------------------------


class PostSerializer(serializers.ModelSerializer):
    """상세용 읽기 전용. comment_count 등은 services.annotated_posts 주석값."""

    user = PostUserSerializer(read_only=True)
    gym = PostGymSerializer(read_only=True, allow_null=True)
    images = serializers.SerializerMethodField()
    comment_count = serializers.IntegerField(read_only=True)
    recruitment = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "user",
            "category",
            "title",
            "content",
            "gym",
            "images",
            "comment_count",
            "view_count",
            "recruitment",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_images(self, obj) -> list[str]:
        return [image.image for image in obj.images.all()]

    def get_recruitment(self, obj) -> dict | None:
        try:
            recruitment = obj.recruitment
        except Recruitment.DoesNotExist:
            return None
        recruitment.approved_count = getattr(obj, "recruitment_approved_count", None)
        if recruitment.approved_count is None:
            recruitment.approved_count = approved_count(recruitment)
        recruitment.my_participation_status = getattr(
            obj, "my_participation_status", None
        )
        return RecruitmentSerializer(recruitment, context=self.context).data


class PostListSerializer(PostSerializer):
    """목록용 — 본문 대신 200자 preview."""

    preview = serializers.SerializerMethodField()

    class Meta(PostSerializer.Meta):
        fields = tuple(f for f in PostSerializer.Meta.fields if f != "content") + (
            "preview",
        )
        read_only_fields = fields

    def get_preview(self, obj) -> str:
        return obj.content[:PREVIEW_LENGTH]


class PostWriteSerializer(serializers.ModelSerializer):
    """생성/수정 입력. 응답은 PostSerializer 로 다시 내려준다.

    - category=recruit 면 recruitment 필수, free 면 금지. category 는 수정 불가
    - images 는 URL 문자열 목록 (presigned URL 업로드 결과), 전체 교체 방식
    """

    title = serializers.CharField(
        max_length=TITLE_MAX_LENGTH,
        error_messages={
            "blank": "제목을 입력해 주세요.",
            "max_length": f"제목은 {TITLE_MAX_LENGTH}자 이하여야 합니다.",
        },
    )
    content = serializers.CharField(
        max_length=CONTENT_MAX_LENGTH,
        error_messages={
            "blank": "내용을 입력해 주세요.",
            "max_length": f"내용은 {CONTENT_MAX_LENGTH}자 이하여야 합니다.",
        },
    )
    gym = serializers.PrimaryKeyRelatedField(
        queryset=Gym.objects.all(), allow_null=True, required=False
    )
    images = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        max_length=MAX_IMAGES,
        error_messages={
            "max_length": f"이미지는 {MAX_IMAGES}장까지 첨부할 수 있습니다."
        },
    )
    recruitment = RecruitmentWriteSerializer(required=False)

    class Meta:
        model = Post
        fields = ("category", "title", "content", "gym", "images", "recruitment")

    def validate(self, attrs):
        post = self.instance
        if post is None:
            category = attrs.get("category", Post.Category.FREE)
            has_recruitment = attrs.get("recruitment") is not None
            if category == Post.Category.RECRUIT and not has_recruitment:
                raise serializers.ValidationError(
                    {"recruitment": "모집글에는 모집 정보가 필요합니다."}
                )
            if category == Post.Category.FREE and has_recruitment:
                raise serializers.ValidationError(
                    {"recruitment": "자유글에는 모집 정보를 넣을 수 없습니다."}
                )
            return attrs

        if "category" in attrs and attrs["category"] != post.category:
            raise serializers.ValidationError(
                {"category": "게시글 종류는 변경할 수 없습니다."}
            )
        recruitment = attrs.get("recruitment")
        if recruitment:
            if not post.is_recruit:
                raise serializers.ValidationError(
                    {"recruitment": "자유글에는 모집 정보를 넣을 수 없습니다."}
                )
            new_capacity = recruitment.get("capacity")
            if new_capacity is not None:
                members = approved_count(post.recruitment) + 1
                if new_capacity < members:
                    raise serializers.ValidationError(
                        {
                            "recruitment": {
                                "capacity": (
                                    f"이미 {members}명이 참여 중이라 "
                                    "정원을 그보다 줄일 수 없습니다."
                                )
                            }
                        }
                    )
        return attrs

    def create(self, validated_data):
        return create_post(self.context["request"].user, **validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("category", None)
        return update_post(instance, **validated_data)


# --- 댓글 ---------------------------------------------------------------------


class PostCommentSerializer(serializers.ModelSerializer):
    user = PostUserSerializer(read_only=True)
    content = serializers.CharField(
        max_length=COMMENT_MAX_LENGTH,
        error_messages={
            "blank": "댓글 내용을 입력해 주세요.",
            "max_length": f"댓글은 {COMMENT_MAX_LENGTH}자 이하여야 합니다.",
        },
    )
    parent = serializers.PrimaryKeyRelatedField(
        queryset=PostComment.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = PostComment
        fields = ("id", "user", "content", "parent", "created_at")
        read_only_fields = ("id", "user", "created_at")

    def validate_parent(self, parent):
        if parent is None:
            return parent
        post = self.context["post"]
        if parent.post_id != post.id:
            raise serializers.ValidationError(
                "같은 게시글의 댓글에만 답글을 달 수 있습니다."
            )
        if parent.parent_id is not None:
            raise serializers.ValidationError("답글에는 다시 답글을 달 수 없습니다.")
        return parent


# --- 참여 ---------------------------------------------------------------------


class ParticipationSerializer(serializers.ModelSerializer):
    user = PostUserSerializer(read_only=True)

    class Meta:
        model = Participation
        fields = ("id", "user", "status", "created_at")
        read_only_fields = fields


class ParticipationStatusSerializer(serializers.Serializer):
    """작성자의 승인/거절 입력."""

    status = serializers.ChoiceField(
        choices=[
            (Participation.Status.APPROVED, "승인"),
            (Participation.Status.REJECTED, "거절"),
        ],
        error_messages={"invalid_choice": "status 는 approved 또는 rejected 입니다."},
    )
