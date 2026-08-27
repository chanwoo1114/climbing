from django.conf import settings
from django.db import models

from common.models import BaseModel


class Follow(BaseModel):
    """팔로우 관계 (follower → following).

    언팔로우는 hard delete 로 행을 지운다 — soft delete 로 남기면 같은 쌍의
    UNIQUE 제약 때문에 재팔로우가 막히고, 관계 자체엔 남길 내용도 없다.
    (혹시 soft delete 된 행이 있어도 services.follow_user 가 복구해서 재사용한다.)
    """

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following_set",
        db_comment="팔로우하는 쪽 회원 FK",
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follower_set",
        db_comment="팔로우 당하는 쪽 회원 FK",
    )

    class Meta:
        db_table_comment = "팔로우 관계 — follower 가 following 을 팔로우. 쌍 UNIQUE"
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"], name="social_follow_uniq"
            ),
            # 자기 자신 팔로우는 서비스에서도 막지만 DB 에서도 못박는다.
            models.CheckConstraint(
                condition=~models.Q(follower=models.F("following")),
                name="social_follow_no_self",
            ),
        ]

    def __str__(self):
        return f"{self.follower_id} → {self.following_id}"
