from datetime import datetime, timedelta
from unittest import skip

import pytz
from model_bakery import seq
from psycopg2._range import DateTimeTZRange
from rest_framework import status
from rest_framework.test import APIClient

from accounting.baker_recipes import CustomerRecipe
from authentication.baker_recipes import UserRecipe, UserGroupRecipe
from core.local import local_state
from core.tests.base import FCTestCase
from poi.baker_recipes import LocationRecipe, LocationHistoryRecipe
from telemetry.baker_recipes import ReadingRecipe
from telemetry.models.bt.reading import Reading
from tracker.baker_recipes import TrackerInstallRecipe
from utils.dates import NON_AWARE_TEST_NOW
from vehicle.baker_recipes import VehicleRecipe, VehicleGroupRecipe


class LocationApiTestCase(FCTestCase):
    databases = "__all__"

    def setUp(self):
        super().setUp()

        self.client = APIClient()
        self.user = UserRecipe.make()
        local_state.customer = self.user.customer
        self.client.force_authenticate(self.user)

    def tearDown(self):
        local_state.clear()

    def test_get_only_current_customers_location_histories(self):
        location = LocationRecipe.make(fc_owner=self.user.customer)
        location_other = LocationRecipe.make(fc_owner=CustomerRecipe.make())
        location_history = LocationHistoryRecipe.make(location=location)
        LocationHistoryRecipe.make(location=location_other)

        res = self.client.get("/api/location-history/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        self.assertCountEqual(
            [location_history.pk], [row["id"] for row in result]
        )
        result_obj = result[0]
        self.assertEqual(location_history.pk, result_obj["id"])
        self.assertCountEqual(
            result_obj.keys(), ["id", "duration", "location", "vehicle"]
        )

    def test_get_filtered_location_histories(self):
        location = LocationRecipe.make(fc_owner=self.user.customer)
        group = VehicleGroupRecipe.make(customer=self.user.customer)
        vehicle = VehicleRecipe.make(
            customer=self.user.customer, groups=[group]
        )
        location_history = LocationHistoryRecipe.make(
            vehicle=vehicle, location=location
        )
        LocationHistoryRecipe.make(location=location)

        res = self.client.get(
            "/api/location-history/",
            {
                "location": location_history.location.pk,
                "vehicle": vehicle.pk,
                "vehicle_group": group.pk,
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        self.assertCountEqual(
            [location_history.pk], [row["id"] for row in result]
        )

    def test_get_filtered_location_histories_by_time_range(self):
        location = LocationRecipe.make(fc_owner=self.user.customer)
        test_date_start_iso = "2020-01-01T10:00:00"
        test_date_end_iso = "2020-01-01T15:00:00"
        test_date = datetime.strptime(
            test_date_start_iso, "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=pytz.UTC)

        location_history = LocationHistoryRecipe.make(
            location=location,
            duration=DateTimeTZRange(test_date, test_date + timedelta(days=1)),
        )
        LocationHistoryRecipe.make(
            location=location,
            duration=DateTimeTZRange(
                test_date + timedelta(days=2), test_date + timedelta(days=3)
            ),
        )

        res = self.client.get(
            "/api/location-history/",
            {
                "duration__range_lower": test_date_start_iso,
                "duration__range_upper": test_date_end_iso,
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        self.assertCountEqual(
            [location_history.pk],
            [row["id"] for row in result if row["id"] == location_history.pk],
        )


class TestLocationHistoryReadingApi(FCTestCase):
    databases = "__all__"

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        self.start_time = NON_AWARE_TEST_NOW
        self.user = UserRecipe.make()
        UserGroupRecipe.make(
            visible_all_vehicles=True,
            users=[self.user],
            customer=self.user.customer,
        )
        self.customer = self.user.customer
        local_state.customer = self.user.customer

        vehicle = VehicleRecipe.make(customer=self.customer)
        TrackerInstallRecipe.make(vehicle=vehicle)

        ReadingRecipe.make(
            _quantity=2,
            vehicle_id=vehicle.id,
            status=Reading.STATUS_CHOICES.valid,
            movement_type=Reading.MOVEMENT_TYPES.traveling,
            datetime=seq(self.start_time, timedelta(seconds=10)),
        )

        ReadingRecipe.make(
            _quantity=1,
            vehicle_id=vehicle.id,
            status=Reading.STATUS_CHOICES.valid,
            movement_type=Reading.MOVEMENT_TYPES.stopped,
            datetime=seq(
                self.start_time + timedelta(minutes=1), timedelta(seconds=10)
            ),
        )

        ReadingRecipe.make(
            _quantity=2,
            vehicle_id=vehicle.id,
            status=Reading.STATUS_CHOICES.valid,
            movement_type=Reading.MOVEMENT_TYPES.traveling,
            datetime=seq(
                self.start_time + timedelta(minutes=2), timedelta(seconds=10)
            ),
        )

        ReadingRecipe.make(
            _quantity=3,
            vehicle_id=vehicle.id,
            status=Reading.STATUS_CHOICES.valid,
            movement_type=Reading.MOVEMENT_TYPES.stopped,
            datetime=seq(
                self.start_time + timedelta(minutes=3), timedelta(seconds=10)
            ),
        )

        ReadingRecipe.make(
            _quantity=8,
            vehicle_id=vehicle.id,
            status=Reading.STATUS_CHOICES.valid,
            movement_type=Reading.MOVEMENT_TYPES.traveling,
            datetime=seq(
                self.start_time + timedelta(minutes=3, seconds=40),
                timedelta(seconds=10),
            ),
        )

        self.readings = list(Reading.objects.all(vehicle_id=vehicle.id))[::-1]

        location = LocationRecipe.make(fc_owner=self.user.customer)
        self.location_history = LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(
                self.start_time + timedelta(seconds=11),
                self.start_time + timedelta(minutes=3),
            ),
        )
        self.opened_location_history = LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(
                self.start_time + timedelta(minutes=3, seconds=40),
                None,
            ),
        )

        self.client.force_authenticate(self.user)

    def test_readings_action(self):
        response = self.client.get(
            f"/api/location-history/{self.location_history.pk}/readings/"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_readings_action_post_fails(self):
        response = self.client.post(
            f"/api/location-history/{self.location_history.pk}/readings/",
            data={},
        )
        self.assertEqual(
            status.HTTP_405_METHOD_NOT_ALLOWED, response.status_code
        )

    def test_readings_action_returns_readings(self):
        # Not Filtered  STTSSS - 6
        #     Filtered  STTS   - 5
        response = self.client.get(
            f"/api/location-history/{self.location_history.pk}/readings/"
        )
        self.assertEqual(len(response.data), 4)

    def test_readings_action_returns_readings_descending_order(self):
        response = self.client.get(
            f"/api/location-history/{self.location_history.pk}/readings/"
        )
        dates = [row["datetime"] for row in response.data]
        self.assertEqual(dates, sorted(dates))

    def test_readings_action_expand(self):
        response = self.client.get(
            f"/api/location-history/{self.location_history.pk}/readings/",
            {
                "expand": True,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_readings_action_returns_readings_expand(self):
        # Not Filtered  T STTSSS T - 8
        #     Filtered  T STTS   T - 6
        response = self.client.get(
            f"/api/location-history/{self.location_history.pk}/readings/",
            {
                "expand": True,
            },
        )
        self.assertEqual(len(response.data), 6)
        for i in response.data:
            if i == response.data[0]:
                self.assertEqual(i["expanded"], True)
                self.assertEqual(i["id"], self.readings[-1].pk)
            elif i == response.data[-1]:
                self.assertEqual(i["expanded"], True)
                self.assertEqual(i["id"], self.readings[7].pk)
            else:
                self.assertEqual(i["expanded"], False)

    def test_readings_action_returns_readings_expand_duration_none(self):
        response = self.client.get(
            f"/api/location-history/{self.opened_location_history.pk}/readings/",
            {
                "expand": True,
            },
        )
        self.assertEqual(len(response.data), 9)
        for i in response.data:
            if i == response.data[0]:
                self.assertEqual(i["expanded"], True)
                self.assertEqual(i["id"], self.readings[11].pk)
            else:
                self.assertEqual(i["expanded"], False)
