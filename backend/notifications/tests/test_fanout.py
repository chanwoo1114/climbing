"""푸시·이메일 팬아웃 — 실제 훅(좋아요/팔로우/모집 마감)을 타서 deliver_notification 까지 간다.

notify() 의 on_commit 은 captureOnCommitCallbacks(execute=True) 로 실행하고,
CELERY_TASK_ALWAYS_EAGER 라 태스크는 그 자리에서 돈다. WebSocket 은 InMemory 채널 레이어,
실제 발송(pywebpush)은 notifications.push._send_webpush 를 mock 으로 바꾼다.
메일은 locmem 백엔드의 mail.outbox 로 확인한다.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from pywebpush import WebPushException

from accounts.services import register_user
from accounts.tests.helpers import create_verified_user
from climbs.services import like_log
from climbs.tests.helpers import create_gym, create_log
from community.services import close_recruitment
from community.tests.helpers import add_participant, create_recruit_post
from notifications.models import Notification, NotificationSetting, PushSubscription
from notifications.tests.helpers import IN_MEMORY_CHANNELS
from social.services import follow_user

VAPID = {
    "WEBPUSH_VAPID_PUBLIC_KEY": "test-public-key",
    "WEBPUSH_VAPID_PRIVATE_KEY": "test-private-key",
    "WEBPUSH_VAPID_CLAIMS_EMAIL": "mailto:ops@example.com",
}
SEND = "notifications.push._send_webpush"


def gone(status_code=410) -> WebPushException:
    """푸시 서비스가 만료 구독에 돌려주는 응답을 흉내 낸 예외."""
    return WebPushException("gone", response=SimpleNamespace(status_code=status_code))


def subscribe(user, suffix) -> PushSubscription:
    return PushSubscription.objects.create(
        user=user,
        endpoint=f"https://push.example.com/send/{suffix}",
        p256dh=f"p256dh-{suffix}",
        auth=f"auth-{suffix}",
    )


@override_settings(**IN_MEMORY_CHANNELS, **VAPID)
class PushFanoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.actor = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.log = create_log(cls.owner, cls.gym)

    def setUp(self):
        self.phone = subscribe(self.owner, "phone")
        self.laptop = subscribe(self.owner, "laptop")
        subscribe(self.actor, "actor")  # 행위자 구독에는 가면 안 된다

    def _like(self):
        with self.captureOnCommitCallbacks(execute=True):
            like_log(self.log, self.actor)

    def test_sends_one_push_per_subscription_with_payload(self):
        with patch(SEND) as send:
            self._like()

        self.assertEqual(send.call_count, 2)
        subs = {call.args[0].pk for call in send.call_args_list}
        self.assertEqual(subs, {self.phone.pk, self.laptop.pk})

        n = Notification.objects.get(recipient=self.owner)
        payload = send.call_args_list[0].args[1]
        self.assertEqual(
            payload,
            {
                "id": n.id,
                "type": "like",
                "message": "bravo님이 회원님의 기록을 좋아합니다",
                "target_type": "climb_log",
                "target_id": self.log.id,
                "url": f"{settings.FRONTEND_BASE_URL}/logs/{self.log.id}",
                "created_at": n.created_at.isoformat(),
            },
        )
        self.phone.refresh_from_db()
        self.assertIsNotNone(self.phone.last_used_at)

    def test_follow_links_to_actor_profile(self):
        with patch(SEND) as send:
            with self.captureOnCommitCallbacks(execute=True):
                follow_user(follower=self.actor, target_id=self.owner.id)
        self.assertEqual(send.call_count, 2)
        payload = send.call_args.args[1]
        self.assertEqual(payload["type"], "follow")
        self.assertEqual(
            payload["url"], f"{settings.FRONTEND_BASE_URL}/users/{self.actor.id}"
        )

    def test_skips_when_push_disabled(self):
        NotificationSetting.objects.create(user=self.owner, push_enabled=False)
        with patch(SEND) as send:
            self._like()
        send.assert_not_called()
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 1)

    @override_settings(WEBPUSH_VAPID_PUBLIC_KEY="", WEBPUSH_VAPID_PRIVATE_KEY="")
    def test_skips_when_not_configured(self):
        with patch(SEND) as send:
            self._like()
        send.assert_not_called()

    def test_gone_subscription_is_removed_and_others_still_sent(self):
        def fake_send(subscription, payload):
            if subscription.pk == self.phone.pk:
                raise gone(410)

        with patch(SEND, side_effect=fake_send) as send:
            self._like()

        self.assertEqual(send.call_count, 2)
        self.assertFalse(PushSubscription.all_objects.filter(pk=self.phone.pk).exists())
        self.laptop.refresh_from_db()
        self.assertIsNotNone(self.laptop.last_used_at)

    def test_404_also_counts_as_gone(self):
        with patch(SEND, side_effect=gone(404)):
            self._like()
        self.assertEqual(PushSubscription.objects.filter(user=self.owner).count(), 0)

    def test_other_errors_keep_subscription_and_continue(self):
        with patch(SEND, side_effect=[RuntimeError("network"), None]) as send:
            self._like()  # 예외가 밖으로 나오지 않는다
        self.assertEqual(send.call_count, 2)
        self.assertEqual(PushSubscription.objects.filter(user=self.owner).count(), 2)
        self.assertEqual(
            PushSubscription.objects.filter(
                user=self.owner, last_used_at__isnull=False
            ).count(),
            1,
        )

    def test_webpush_error_with_5xx_keeps_subscription(self):
        with patch(SEND, side_effect=gone(500)):
            self._like()
        self.assertEqual(PushSubscription.objects.filter(user=self.owner).count(), 2)


@override_settings(**IN_MEMORY_CHANNELS, NOTIFICATION_EMAIL_ENABLED=True)
class EmailFanoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = create_verified_user(email="a@example.com", nickname="alpha")
        cls.member = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()

    def setUp(self):
        self.post = create_recruit_post(
            self.author, self.gym, capacity=5, join_type="approval"
        )
        mail.outbox.clear()

    def _close_with(self, member):
        add_participant(self.post, member, status="approved")
        with self.captureOnCommitCallbacks(execute=True):
            close_recruitment(self.post.recruitment)

    def test_recruitment_closed_emails_member_with_post_link(self):
        self._close_with(self.member)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["b@example.com"])
        self.assertTrue(message.subject.startswith("[Climbing] "))
        self.assertIn("모집이 마감되었습니다", message.subject)
        link = f"{settings.FRONTEND_BASE_URL}/posts/{self.post.id}"
        self.assertIn(link, message.body)
        self.assertIn("bravo님", message.body)
        self.assertIn("모집 마감", message.body)  # type label
        self.assertNotIn("{%", message.body)

        html, mime = message.alternatives[0]
        self.assertEqual(mime, "text/html")
        self.assertIn(link, html)
        self.assertIn("자세히 보기", html)

    def test_like_is_not_emailed(self):
        log = create_log(self.author, self.gym)
        with self.captureOnCommitCallbacks(execute=True):
            like_log(log, self.member)
        self.assertEqual(Notification.objects.filter(recipient=self.author).count(), 1)
        self.assertEqual(mail.outbox, [])

    def test_email_disabled_by_user_suppresses(self):
        NotificationSetting.objects.create(user=self.member, email_enabled=False)
        self._close_with(self.member)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(Notification.objects.filter(recipient=self.member).count(), 1)

    def test_unverified_email_suppresses(self):
        unverified = register_user(
            email="c@example.com", nickname="charlie", password="s3cure-pass!"
        )
        mail.outbox.clear()  # 가입 인증 메일 제외
        self._close_with(unverified)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(Notification.objects.filter(recipient=unverified).count(), 1)

    @override_settings(NOTIFICATION_EMAIL_ENABLED=False)
    def test_global_switch_off_suppresses(self):
        self._close_with(self.member)
        self.assertEqual(mail.outbox, [])

    def test_email_failure_does_not_break_delivery(self):
        with patch(
            "notifications.emails.send_email_task.delay", side_effect=RuntimeError
        ):
            self._close_with(self.member)  # 예외 없음
        self.assertEqual(Notification.objects.filter(recipient=self.member).count(), 1)
