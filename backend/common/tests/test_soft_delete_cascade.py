from django.test import TestCase

from accounts.models import UserProfile
from accounts.tests.helpers import create_verified_user
from climbs.models import ClimbLog, ClimbLogComment, ClimbLogLike
from climbs.tests.helpers import create_gym, create_log
from gyms.models import Gym


class SoftDeleteCascadeTests(TestCase):
    def setUp(self):
        self.user = create_verified_user(email="c@example.com", nickname="cascade")
        self.other = create_verified_user(email="d@example.com", nickname="liker")
        self.gym = create_gym()
        self.log = create_log(self.user, self.gym)
        self.comment = ClimbLogComment.objects.create(
            climb_log=self.log, user=self.other, content="굿"
        )
        self.like = ClimbLogLike.objects.create(climb_log=self.log, user=self.other)

    def test_log_delete_cascades_to_comments_and_likes(self):
        self.log.delete()
        self.assertFalse(ClimbLog.objects.filter(pk=self.log.pk).exists())
        self.assertFalse(ClimbLogComment.objects.filter(pk=self.comment.pk).exists())
        self.assertFalse(ClimbLogLike.objects.filter(pk=self.like.pk).exists())
        deleted = ClimbLogComment.all_objects.get(pk=self.comment.pk)
        self.assertTrue(deleted.is_deleted)
        # 부모와 같은 시각으로 기록된다
        parent = ClimbLog.all_objects.get(pk=self.log.pk)
        self.assertEqual(deleted.deleted_at, parent.deleted_at)

    def test_user_delete_cascades_two_levels(self):
        self.user.delete()
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
        self.assertFalse(ClimbLog.objects.filter(pk=self.log.pk).exists())
        # 남이 단 댓글도 기록과 함께 숨는다 (기록 → 댓글 2단계)
        self.assertFalse(ClimbLogComment.objects.filter(pk=self.comment.pk).exists())
        # 타인의 데이터는 그대로
        self.assertTrue(type(self.other).objects.filter(pk=self.other.pk).exists())

    def test_protect_relation_is_not_touched(self):
        # ClimbLog.gym 은 PROTECT — 암장을 지워도 기록은 남는다 (soft delete 라 DB 제약도 안 걸림)
        self.gym.delete()
        self.assertFalse(Gym.objects.filter(pk=self.gym.pk).exists())
        self.assertTrue(ClimbLog.objects.filter(pk=self.log.pk).exists())

    def test_queryset_delete_stays_bulk(self):
        ClimbLog.objects.filter(pk=self.log.pk).delete()
        self.assertFalse(ClimbLog.objects.filter(pk=self.log.pk).exists())
        # 문서화된 제약: 쿼리셋 delete 는 cascade 하지 않는다
        self.assertTrue(ClimbLogComment.objects.filter(pk=self.comment.pk).exists())
