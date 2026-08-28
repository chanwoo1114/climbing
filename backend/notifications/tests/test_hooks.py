"""각 도메인 서비스 훅이 올바른 받는 사람·종류·문구로 알림을 만드는지.

좋아요/댓글/팔로우는 실제 API 를, 모집/크루는 서비스 함수를 직접 호출한다.
채팅방 브로드캐스트가 섞이는 모집/크루는 InMemory 채널 레이어로 override.
"""

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from climbs.services import create_comment, like_log, unlike_log
from climbs.tests.helpers import create_gym, create_log
from community.services import (
    close_recruitment,
    join_recruitment,
    set_participation_status,
)
from community.tests.helpers import add_participant, create_recruit_post
from crews.services import join_crew, set_member_status
from crews.tests.helpers import add_member, create_crew
from notifications.models import Notification
from notifications.tests.helpers import IN_MEMORY_CHANNELS
from social.services import follow_user


def notifications_for(user, type=None):
    queryset = Notification.objects.filter(recipient=user).order_by("id")
    if type:
        queryset = queryset.filter(type=type)
    return list(queryset)


class LikeHookTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.log = create_log(cls.owner, cls.gym)
        cls.url = reverse("v1:climbs:log-like", args=[cls.log.id])

    def test_like_notifies_owner_once_even_when_toggled(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(self.url).status_code, 204)
        self.assertEqual(self.client.post(self.url).status_code, 204)  # 멱등 재호출
        self.client.delete(self.url)
        self.assertEqual(
            self.client.post(self.url).status_code, 204
        )  # 취소 후 재좋아요

        items = notifications_for(self.owner)
        self.assertEqual(len(items), 1)
        n = items[0]
        self.assertEqual(n.type, "like")
        self.assertEqual(n.actor_id, self.user.id)
        self.assertEqual((n.target_type, n.target_id), ("climb_log", self.log.id))
        self.assertEqual(n.message, "bravo님이 회원님의 기록을 좋아합니다")
        self.assertEqual(notifications_for(self.user), [])  # 행위자는 못 받는다

    def test_liking_own_log_does_not_notify(self):
        like_log(self.log, self.owner)
        unlike_log(self.log, self.owner)
        self.assertEqual(Notification.objects.count(), 0)


class CommentHookTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.user = create_verified_user(email="b@example.com", nickname="bravo")
        cls.third = create_verified_user(email="c@example.com", nickname="charlie")
        cls.gym = create_gym()
        cls.log = create_log(cls.owner, cls.gym)
        cls.url = reverse("v1:climbs:log-comments", args=[cls.log.id])

    def test_comment_notifies_log_owner_with_preview(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(self.url, {"content": "  멋진   기록이네요  "})
        self.assertEqual(res.status_code, 201)

        items = notifications_for(self.owner)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].type, "comment")
        self.assertEqual(items[0].actor_id, self.user.id)
        self.assertEqual(items[0].target_id, self.log.id)
        self.assertEqual(
            items[0].message,
            "bravo님이 회원님의 기록에 댓글을 남겼습니다: 멋진 기록이네요",
        )

    def test_reply_notifies_parent_author_and_log_owner(self):
        parent = create_comment(self.log, self.user, "첫 댓글")
        Notification.objects.all().delete()

        create_comment(self.log, self.third, "답글이에요", parent=parent)

        reply = notifications_for(self.user)
        self.assertEqual([n.type for n in reply], ["reply"])
        self.assertEqual(
            reply[0].message,
            "charlie님이 회원님의 댓글에 답글을 남겼습니다: 답글이에요",
        )
        self.assertEqual(
            (reply[0].target_type, reply[0].target_id), ("climb_log", self.log.id)
        )
        owner = notifications_for(self.owner)
        self.assertEqual([n.type for n in owner], ["comment"])
        self.assertEqual(owner[0].actor_id, self.third.id)

    def test_owner_replying_gets_nothing_and_commenter_gets_reply(self):
        parent = create_comment(self.log, self.user, "질문")
        Notification.objects.all().delete()

        create_comment(self.log, self.owner, "답변", parent=parent)

        self.assertEqual([n.type for n in notifications_for(self.user)], ["reply"])
        self.assertEqual(notifications_for(self.owner), [])

    def test_reply_to_own_comment_on_own_log_notifies_nobody(self):
        parent = create_comment(self.log, self.owner, "혼잣말")
        create_comment(self.log, self.owner, "혼잣말 2", parent=parent)
        self.assertEqual(Notification.objects.count(), 0)

    def test_reply_to_owner_comment_by_other_sends_single_reply(self):
        """부모 댓글 작성자 == 기록 작성자면 reply 하나만 (comment 중복 없음)."""
        parent = create_comment(self.log, self.owner, "제 기록입니다")
        create_comment(self.log, self.user, "대단해요", parent=parent)
        self.assertEqual([n.type for n in notifications_for(self.owner)], ["reply"])


class FollowHookTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = create_verified_user(email="a@example.com", nickname="alpha")
        cls.target = create_verified_user(email="b@example.com", nickname="bravo")

    def test_follow_notifies_target_once(self):
        self.client.force_authenticate(self.me)
        url = reverse("v1:social:follow", args=[self.target.id])
        self.assertEqual(self.client.post(url).status_code, 201)
        self.assertEqual(self.client.post(url).status_code, 201)  # 이미 팔로우 중

        items = notifications_for(self.target)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].type, "follow")
        self.assertEqual(items[0].actor_id, self.me.id)
        self.assertEqual(
            (items[0].target_type, items[0].target_id), ("user", self.me.id)
        )
        self.assertEqual(items[0].message, "alpha님이 회원님을 팔로우하기 시작했습니다")
        self.assertEqual(notifications_for(self.me), [])

    def test_refollow_after_unfollow_refreshes_existing_notification(self):
        """언팔→재팔 반복은 알림을 도배하지 않고 기존 한 줄을 갱신(읽지 않음으로)한다."""
        follow_user(follower=self.me, target_id=self.target.id)
        first = notifications_for(self.target)[0]
        first.is_read = True
        first.save(update_fields=["is_read"])

        self.client.force_authenticate(self.me)
        self.client.delete(reverse("v1:social:follow", args=[self.target.id]))
        follow_user(follower=self.me, target_id=self.target.id)

        items = notifications_for(self.target)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, first.id)
        self.assertFalse(items[0].is_read)


@override_settings(**IN_MEMORY_CHANNELS)
class RecruitmentHookTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = create_verified_user(email="a@example.com", nickname="alpha")
        cls.approved = create_verified_user(email="b@example.com", nickname="bravo")
        cls.pending = create_verified_user(email="c@example.com", nickname="charlie")
        cls.gym = create_gym()

    def setUp(self):
        self.post = create_recruit_post(
            self.author, self.gym, capacity=5, join_type="approval"
        )
        self.rec = self.post.recruitment

    def test_close_notifies_approved_members_only(self):
        add_participant(self.post, self.approved, status="approved")
        add_participant(self.post, self.pending, status="pending")

        close_recruitment(self.rec)

        items = notifications_for(self.approved)
        self.assertEqual([n.type for n in items], ["recruitment_closed"])
        self.assertEqual(items[0].actor_id, self.author.id)
        self.assertEqual(
            (items[0].target_type, items[0].target_id), ("post", self.post.id)
        )
        self.assertEqual(
            items[0].message,
            "'투어 모집' 모집이 마감되었습니다. 채팅방에서 인사를 나눠 보세요",
        )
        self.assertEqual(notifications_for(self.pending), [])
        self.assertEqual(notifications_for(self.author), [])

    def test_approve_and_reject_notify_participant(self):
        add_participant(self.post, self.approved, status="pending")
        add_participant(self.post, self.pending, status="pending")

        set_participation_status(self.rec, self.approved.id, "approved")
        set_participation_status(self.rec, self.pending.id, "rejected")

        ok = notifications_for(self.approved)
        self.assertEqual([n.type for n in ok], ["recruitment_approved"])
        self.assertEqual(ok[0].message, "'투어 모집' 모집 참여가 승인되었습니다")
        self.assertEqual((ok[0].target_type, ok[0].target_id), ("post", self.post.id))
        self.assertEqual(ok[0].actor_id, self.author.id)

        no = notifications_for(self.pending)
        self.assertEqual([n.type for n in no], ["recruitment_rejected"])
        self.assertEqual(no[0].message, "'투어 모집' 모집 참여가 거절되었습니다")

    def test_approving_twice_notifies_once(self):
        add_participant(self.post, self.approved, status="pending")
        set_participation_status(self.rec, self.approved.id, "approved")
        set_participation_status(self.rec, self.approved.id, "approved")
        self.assertEqual(len(notifications_for(self.approved)), 1)

    def test_instant_join_filling_capacity_sends_closed_to_members(self):
        post = create_recruit_post(
            self.author, self.gym, capacity=2, join_type="instant"
        )
        join_recruitment(post.recruitment, self.approved)  # 정원 도달 → 자동 마감
        items = notifications_for(self.approved)
        self.assertEqual([n.type for n in items], ["recruitment_closed"])
        self.assertEqual(notifications_for(self.author), [])


@override_settings(**IN_MEMORY_CHANNELS)
class CrewHookTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.staff = create_verified_user(email="b@example.com", nickname="bravo")
        cls.member = create_verified_user(email="c@example.com", nickname="charlie")
        cls.applicant = create_verified_user(email="d@example.com", nickname="delta")

    def _crew(self, join_type="instant"):
        crew = create_crew(self.owner, name="바위탐험대", join_type=join_type)
        add_member(crew, self.staff, role="staff")
        add_member(crew, self.member)
        Notification.objects.all().delete()
        return crew

    def test_instant_join_notifies_owner_and_staff(self):
        crew = self._crew()
        join_crew(crew, self.applicant)

        for manager in (self.owner, self.staff):
            items = notifications_for(manager)
            self.assertEqual([n.type for n in items], ["crew_joined"], manager)
            self.assertEqual(items[0].actor_id, self.applicant.id)
            self.assertEqual(
                (items[0].target_type, items[0].target_id), ("crew", crew.id)
            )
            self.assertEqual(
                items[0].message, "delta님이 바위탐험대 크루에 가입했습니다"
            )
        self.assertEqual(notifications_for(self.member), [])  # 일반 크루원은 제외
        self.assertEqual(notifications_for(self.applicant), [])

    def test_approval_join_notifies_managers_with_request_wording(self):
        crew = self._crew(join_type="approval")
        join_crew(crew, self.applicant)
        items = notifications_for(self.owner)
        self.assertEqual(
            items[0].message, "delta님이 바위탐험대 크루 가입을 신청했습니다"
        )
        self.assertEqual(len(notifications_for(self.staff)), 1)

    def test_approve_notifies_applicant(self):
        crew = self._crew(join_type="approval")
        add_member(crew, self.applicant, status="pending")
        set_member_status(crew, self.applicant.id, "active")

        items = notifications_for(self.applicant)
        self.assertEqual([n.type for n in items], ["crew_approved"])
        self.assertIsNone(items[0].actor_id)
        self.assertEqual((items[0].target_type, items[0].target_id), ("crew", crew.id))
        self.assertEqual(items[0].message, "바위탐험대 크루 가입이 승인되었습니다")

    def test_reject_notifies_applicant(self):
        crew = self._crew(join_type="approval")
        add_member(crew, self.applicant, status="pending")
        set_member_status(crew, self.applicant.id, "rejected")

        items = notifications_for(self.applicant)
        self.assertEqual([n.type for n in items], ["crew_rejected"])
        self.assertEqual(items[0].message, "바위탐험대 크루 가입이 거절되었습니다")

    def test_reject_via_api(self):
        crew = self._crew(join_type="approval")
        add_member(crew, self.applicant, status="pending")
        self.client.force_authenticate(self.owner)
        url = reverse("v1:crews:crew-member-detail", args=[crew.id, self.applicant.id])
        self.assertEqual(
            self.client.patch(url, {"status": "rejected"}).status_code, 200
        )
        self.assertEqual(
            [n.type for n in notifications_for(self.applicant)], ["crew_rejected"]
        )
