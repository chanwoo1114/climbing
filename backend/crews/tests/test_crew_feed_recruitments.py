"""크루 피드(크루원 공개 기록, is_feed_public 권한)와 크루 주최 모집(Recruitment.crew)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from community.models import Recruitment
from community.tests.helpers import create_recruit_post, future_iso
from crews.tests.helpers import add_member, create_crew, create_gym, create_log


class CrewFeedTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.member = create_verified_user(email="b@example.com", nickname="bravo")
        cls.applicant = create_verified_user(email="c@example.com", nickname="charlie")
        cls.outsider = create_verified_user(email="d@example.com", nickname="delta")
        cls.gym = create_gym()

    def setUp(self):
        self.crew = create_crew(self.owner)
        add_member(self.crew, self.member)
        add_member(self.crew, self.applicant, status="pending")
        self.url = reverse("v1:crews:crew-feed", args=[self.crew.id])

        self.owner_log = create_log(self.owner, self.gym, memo="크루장 공개")
        self.member_log = create_log(self.member, self.gym, memo="크루원 공개")
        create_log(self.member, self.gym, memo="비공개", is_shared=False)
        create_log(self.applicant, self.gym, memo="대기자 공개")
        create_log(self.outsider, self.gym, memo="외부인 공개")

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_members_see_shared_logs_of_active_members_only(self):
        self.client.force_authenticate(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual(
            [log["id"] for log in results], [self.member_log.id, self.owner_log.id]
        )
        self.assertIn("like_count", results[0])
        self.assertIn("is_liked", results[0])

    def test_private_feed_is_forbidden_for_outsiders_and_pending(self):
        for user in (self.outsider, self.applicant):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_public_feed_is_open_to_anyone(self):
        self.crew.is_feed_public = True
        self.crew.save(update_fields=["is_feed_public", "updated_at"])
        self.client.force_authenticate(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]["results"]), 2)

    def test_unknown_crew_is_404(self):
        self.client.force_authenticate(self.member)
        response = self.client.get(reverse("v1:crews:crew-feed", args=[99999]))
        self.assertEqual(response.status_code, 404)


class CrewRecruitmentTests(APITestCase):
    """모집글에 crew 를 붙이는 쪽(community)과 크루별 모집 목록(crews) 을 함께 본다."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = create_verified_user(email="a@example.com", nickname="alpha")
        cls.member = create_verified_user(email="b@example.com", nickname="bravo")
        cls.outsider = create_verified_user(email="c@example.com", nickname="charlie")
        cls.gym = create_gym()
        cls.posts_url = reverse("v1:community:post-list")

    def setUp(self):
        self.crew = create_crew(self.owner)
        add_member(self.crew, self.member)
        self.url = reverse("v1:crews:crew-recruitments", args=[self.crew.id])

    def recruit_payload(self, **recruitment):
        return {
            "category": "recruit",
            "title": "크루 투어",
            "content": "같이 가요",
            "recruitment": {
                "gym": self.gym.id,
                "meet_at": future_iso(),
                "capacity": 4,
                **recruitment,
            },
        }

    def test_member_creates_crew_recruitment(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            self.posts_url, self.recruit_payload(crew=self.crew.id), format="json"
        )
        self.assertEqual(response.status_code, 201)
        rec = response.json()["data"]["recruitment"]
        self.assertEqual(rec["crew"], {"id": self.crew.id, "name": "테스트크루"})
        self.assertEqual(Recruitment.objects.get(pk=rec["id"]).crew_id, self.crew.id)

    def test_personal_recruitment_has_null_crew(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            self.posts_url, self.recruit_payload(), format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["data"]["recruitment"]["crew"])

    def test_non_member_cannot_host_for_crew(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.post(
            self.posts_url, self.recruit_payload(crew=self.crew.id), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "not_crew_member")

        add_member(self.crew, self.outsider, status="pending")
        response = self.client.post(
            self.posts_url, self.recruit_payload(crew=self.crew.id), format="json"
        )
        self.assertEqual(response.json()["error"]["code"], "not_crew_member")

    def test_unknown_crew_is_field_error(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            self.posts_url, self.recruit_payload(crew=99999), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("crew", response.json()["error"]["fields"]["recruitment"])

    def test_patch_can_attach_and_detach_crew(self):
        post = create_recruit_post(self.member, self.gym)
        url = reverse("v1:community:post-detail", args=[post.id])
        self.client.force_authenticate(self.member)

        response = self.client.patch(
            url, {"recruitment": {"crew": self.crew.id}}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["recruitment"]["crew"]["id"], self.crew.id
        )

        response = self.client.patch(
            url, {"recruitment": {"crew": None}}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["recruitment"]["crew"])

    def test_crew_recruitment_list(self):
        crew_post = create_recruit_post(self.member, self.gym, content="크루 모집")
        Recruitment.objects.filter(post=crew_post).update(crew=self.crew)
        create_recruit_post(self.member, self.gym, content="개인 모집")
        other = create_crew(self.owner, name="다른크루")
        other_post = create_recruit_post(self.owner, self.gym, content="다른 크루 모집")
        Recruitment.objects.filter(post=other_post).update(crew=other)

        self.client.force_authenticate(self.outsider)  # 목록은 누구나
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual([p["id"] for p in results], [crew_post.id])
        self.assertEqual(results[0]["recruitment"]["crew"]["name"], "테스트크루")
        self.assertIn("preview", results[0])

    def test_crew_recruitment_list_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_deleted_crew_reads_as_personal(self):
        post = create_recruit_post(self.member, self.gym)
        Recruitment.objects.filter(post=post).update(crew=self.crew)
        self.crew.delete()
        self.client.force_authenticate(self.member)
        response = self.client.get(reverse("v1:community:post-detail", args=[post.id]))
        self.assertIsNone(response.json()["data"]["recruitment"]["crew"])
