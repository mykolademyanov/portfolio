from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounting.baker_recipes import CustomerRecipe
from authentication.baker_recipes import UserRecipe
from core.local import local_state
from poi.baker_recipes import LocationTypeRecipe
from poi.models import LOCATION_TYPE_ICONS
from poi.models import LocationType


class LocationApiTestCase(TestCase):
    databases = "__all__"

    def setUp(self):
        self.client = APIClient()
        self.user = UserRecipe.make()
        local_state.customer = self.user.customer
        self.client.force_authenticate(self.user)

    def tearDown(self):
        local_state.clear()

    def test_create_type(self):
        res = self.client.post(
            "/api/location-types/",
            data=dict(
                name="Type1",
                icon=LOCATION_TYPE_ICONS.material_local_parking,
                color="#ffffff",
            ),
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_create_duplicate_type(self):
        LocationTypeRecipe.make(name="Type1", customer=local_state.customer)
        res = self.client.post(
            "/api/location-types/",
            data=dict(
                name="Type1",
                icon=LOCATION_TYPE_ICONS.material_local_parking,
                color="#ffffff",
            ),
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            res.data["name"][0], "Location Type with such name already exists."
        )

    def test_list_type(self):
        system = LocationTypeRecipe.make(system=True, name="system_type")
        my_type = LocationTypeRecipe.make(
            system=False, name="my", customer=self.user.customer
        )
        LocationTypeRecipe.make(
            system=False, name="other", customer=CustomerRecipe.make()
        )

        res = self.client.get("/api/location-types/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data["results"]
        self.assertEqual(len(results), 2)
        self.assertCountEqual(
            [system.pk, my_type.pk], [row["id"] for row in results]
        )

    def test_put_non_system_types(self):
        my_type: LocationType = LocationTypeRecipe.make(
            system=False, name="my", customer=self.user.customer
        )

        res = self.client.put(
            f"/api/location-types/{my_type.pk}/",
            data=dict(name="apples", color=my_type.color, icon=my_type.icon),
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        my_type.refresh_from_db()
        self.assertEqual(my_type.name, "apples")

    def test_patch_non_system_types(self):
        my_type: LocationType = LocationTypeRecipe.make(
            system=False, name="my", customer=self.user.customer
        )

        res = self.client.patch(
            f"/api/location-types/{my_type.pk}/", data=dict(name="apples")
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        my_type.refresh_from_db()
        self.assertEqual(my_type.name, "apples")

    def test_put_system_types(self):
        vt: LocationType = LocationTypeRecipe.make(system=True, name="system")

        res = self.client.put(
            f"/api/location-types/{vt.pk}/",
            data=dict(name="apples", color=vt.color, icon=vt.icon),
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        vt.refresh_from_db()
        self.assertEqual(vt.name, "system")

    def test_patch_system_types(self):
        vt: LocationType = LocationTypeRecipe.make(system=True, name="system")

        res = self.client.patch(
            f"/api/location-types/{vt.pk}/", data=dict(name="apples")
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        vt.refresh_from_db()
        self.assertEqual(vt.name, "system")

    def test_list_order(self):
        LocationTypeRecipe.make(
            system=False, name="other", customer=self.user.customer
        )

        LocationTypeRecipe.make(
            system=False, name="apple", customer=self.user.customer
        )

        LocationTypeRecipe.make(
            system=False, name="kiwi", customer=self.user.customer
        )

        res = self.client.get("/api/location-types/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            ["apple", "kiwi", "other"],
            [obj["name"] for obj in res.data["results"]],
        )
