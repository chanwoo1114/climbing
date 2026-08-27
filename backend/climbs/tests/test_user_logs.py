from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.tests.helpers import create_verified_user
from climbs.tests.helpers import create_gym, create_log


class UserLogListTests(APITestCase):
    def setUp(self):
        self.owner = create_verified_user(email="o@example.com", nickname="owner")
        self.other = create_verified_user(email="x@example.com", nickname="other")
        gym = create_gym()
        self.shared = create_log(self.owner, gym, is_shared=True)
        self.private = create_log(self.owner, gym, is_shared=False)
        self.url = reverse("v1:climbs:user-logs", args=[self.owner.id])

    def _ids(self, response):
        return {item["id"] for item in response.json()["data"]["results"]}

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_other_sees_only_shared(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(response), {self.shared.id})

    def test_owner_sees_all(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self._ids(self.client.get(self.url)), {self.shared.id, self.private.id}
        )

    def test_unknown_user_404(self):
        self.client.force_authenticate(self.other)
        url = reverse("v1:climbs:user-logs", args=[999999])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_soft_deleted_user_404(self):
        self.owner.delete()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
