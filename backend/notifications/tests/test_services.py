"""notify() 규칙 — 본인 제외, 좋아요 중복 정리, 문구 길이, 커밋 후 전달, 실패 격리, 태스크."""

from unittest.mock import AsyncMock, MagicMock, patch

from django.db import transaction
from django.test import TestCase

from accounts.tests.helpers import create_verified_user
from climbs.tests.helpers import create_gym, create_log
from notifications.models import MESSAGE_MAX_LENGTH, Notification
from notifications.services import mark_read, notify, notify_like
from notifications.tasks import deliver_notification


class NotifyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.actor = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.log = create_log(cls.owner, cls.gym)

    def _notify(self, **overrides):
        kwargs = {
            "recipient": self.owner,
            "actor": self.actor,
            "type": Notification.Type.COMMENT,
            "target_type": Notification.TargetType.CLIMB_LOG,
            "target_id": self.log.id,
            "message": "댓글",
        }
        kwargs.update(overrides)
        return notify(**kwargs)

    def test_skips_self_notification(self):
        self.assertIsNone(self._notify(actor=self.owner))
        self.assertIsNone(self._notify(recipient=self.actor.id, actor=self.actor.id))
        self.assertEqual(Notification.objects.count(), 0)

    def test_accepts_user_or_id(self):
        n = self._notify(recipient=self.owner.id, actor=self.actor.id)
        self.assertEqual(n.recipient_id, self.owner.id)
        self.assertEqual(n.actor_id, self.actor.id)
        self.assertFalse(n.is_read)

    def test_message_is_truncated(self):
        n = self._notify(message="가" * 300)
        self.assertEqual(len(n.message), MESSAGE_MAX_LENGTH)
        self.assertTrue(n.message.endswith("…"))

    def test_like_is_deduped_and_refreshed(self):
        first = notify_like(self.log, self.actor)
        mark_read(first)
        second = notify_like(self.log, self.actor)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertFalse(second.is_read)
        self.assertIsNone(second.read_at)
        self.assertGreater(second.created_at, first.created_at)

    def test_deleted_like_notification_is_restored_on_relike(self):
        first = notify_like(self.log, self.actor)
        first.delete()
        self.assertEqual(Notification.objects.count(), 0)
        second = notify_like(self.log, self.actor)
        self.assertEqual(first.id, second.id)
        self.assertFalse(second.is_deleted)
        self.assertEqual(Notification.objects.count(), 1)

    def test_other_types_are_not_deduped(self):
        self._notify()
        self._notify()
        self.assertEqual(Notification.objects.count(), 2)

    def test_delivery_is_scheduled_after_commit(self):
        with patch("notifications.services.deliver_notification.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                n = self._notify()
                delay.assert_not_called()  # 커밋 전에는 큐에 넣지 않는다
        delay.assert_called_once_with(n.id)

    def test_failure_is_swallowed_and_transaction_stays_usable(self):
        with patch.object(
            Notification.objects, "create", side_effect=RuntimeError("boom")
        ):
            with transaction.atomic():
                self.assertIsNone(self._notify())
                # savepoint 로 격리됐으므로 같은 트랜잭션에서 계속 쿼리할 수 있다
                self.assertEqual(Notification.objects.count(), 0)

    def test_enqueue_failure_is_swallowed(self):
        with patch(
            "notifications.services.deliver_notification.delay",
            side_effect=RuntimeError("broker down"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                n = self._notify()
        self.assertIsNotNone(n)


class DeliverNotificationTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.actor = create_verified_user(email="b@example.com", nickname="bravo")
        cls.gym = create_gym()
        cls.log = create_log(cls.owner, cls.gym)

    def test_pushes_serialized_event_to_user_group(self):
        n = notify_like(self.log, self.actor)
        layer = MagicMock(group_send=AsyncMock())
        with patch("notifications.tasks.get_channel_layer", return_value=layer):
            deliver_notification(n.id)

        layer.group_send.assert_awaited_once()
        group, event = layer.group_send.await_args.args
        self.assertEqual(group, f"user_{self.owner.id}")
        self.assertEqual(event["type"], "notification")
        payload = event["notification"]
        self.assertEqual(payload["id"], n.id)
        self.assertEqual(payload["type"], "like")
        self.assertEqual(
            payload["actor"], {"id": self.actor.id, "nickname": "bravo", "image": None}
        )
        self.assertEqual(payload["target_type"], "climb_log")
        self.assertEqual(payload["target_id"], self.log.id)
        self.assertEqual(payload["message"], "bravo님이 회원님의 기록을 좋아합니다")
        self.assertFalse(payload["is_read"])
        self.assertIsInstance(payload["created_at"], str)

    def test_missing_or_deleted_notification_is_ignored(self):
        n = notify_like(self.log, self.actor)
        n.delete()
        layer = MagicMock(group_send=AsyncMock())
        with patch("notifications.tasks.get_channel_layer", return_value=layer):
            deliver_notification(n.id)
            deliver_notification(999999)
        layer.group_send.assert_not_awaited()

    def test_channel_layer_failure_does_not_raise(self):
        n = notify_like(self.log, self.actor)
        layer = MagicMock(group_send=AsyncMock(side_effect=RuntimeError("redis")))
        with patch("notifications.tasks.get_channel_layer", return_value=layer):
            deliver_notification(n.id)  # 예외 없음
