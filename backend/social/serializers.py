from rest_framework import serializers

from accounts.models import User


class UserSummarySerializer(serializers.ModelSerializer):
    """팔로워/팔로잉/검색 목록용 회원 요약.

    is_following 은 요청자 기준. 뷰가 context["following_ids"] 에 페이지 안의
    회원 중 팔로우 중인 id 집합을 넣어준다 (N+1 방지).
    """

    image = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "nickname", "image", "is_following")
        read_only_fields = fields

    def get_image(self, obj) -> str | None:
        # createsuperuser·admin 으로 만든 계정은 프로필이 없을 수 있다.
        profile = getattr(obj, "profile", None)
        return (profile.image or None) if profile else None

    def get_is_following(self, obj) -> bool:
        return obj.pk in self.context.get("following_ids", ())
