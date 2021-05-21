from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from authentication.models import User
from authentication.baker_recipes import UserRecipe


class TestHijackApi(TestCase):
    databases = "__all__"

    def setUp(self):
        self.client = APIClient()
        self.user: User = UserRecipe.make(is_superuser=False, is_staff=False)
        self.customer = self.user.customer
        self.client.force_authenticate(self.user)

    def test_get_not_allowed(self):
        resp = self.client.get("/api/hijack/")
        self.assertEqual(status.HTTP_403_FORBIDDEN, resp.status_code)

    def test_superuser_can_hijack_user(self):
        self.user.is_superuser = True
        self.user.save()

        resp = self.client.post("/api/hijack/", dict(user=self.user.pk))
        self.assertEqual(status.HTTP_201_CREATED, resp.status_code)

    def test_is_staff_can_hijack_user(self):
        self.user.is_staff = True
        self.user.save()

        resp = self.client.post("/api/hijack/", dict(user=self.user.pk))
        self.assertEqual(status.HTTP_201_CREATED, resp.status_code)

    def test_required_permission(self):
        resp = self.client.post("/api/hijack/", dict(user=self.user.pk))
        self.assertEqual(status.HTTP_403_FORBIDDEN, resp.status_code)
