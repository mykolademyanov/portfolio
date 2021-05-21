import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytz
from django.contrib.gis.geos import Polygon, Point
from django.test import override_settings
from django.utils import timezone
from model_bakery import seq
from psycopg2._range import NumericRange, DateTimeTZRange
from rest_framework import status
from rest_framework.test import APIClient

from accounting.baker_recipes import CustomerRecipe
from authentication.baker_recipes import UserRecipe
from core.local import local_state
from core.tests.base import FCTestCase
from crm.baker_recipes import CompanyRecipe, ContactRecipe
from poi.baker_recipes import (
    LocationTypeRecipe,
    LocationRecipe,
    LocationHistoryRecipe,
)
from poi.models import Location, LocationHistory
from poi.tests.geojson_locations import (
    BBOX_NORTH_CAROLINA,
    CHARLOTTE,
    CHARLOTTE_GEOMETRY,
    NORTH_CAROLINA_GEOMETRY,
    DANVILLE_POINT_GEOMETRY,
    CONCORD_POINT,
)
from telemetry.baker_recipes import ReadingRecipe
from telemetry.models.bt.reading import Reading
from utils.dates import NON_AWARE_TEST_NOW
from vehicle.baker_recipes import VehicleRecipe


class LocationApiTestCase(FCTestCase):
    databases = "__all__"

    def setUp(self):
        super().setUp()

        self.client = APIClient()
        self.user = UserRecipe.make()
        local_state.customer = self.user.customer
        self.client.force_authenticate(self.user)
        self.type = LocationTypeRecipe.make(customer=self.user.customer)

    def tearDown(self):
        local_state.clear()

    def test_list_location_ordering(self):
        LocationRecipe.make(name="peaches", fc_owner=self.user.customer)
        LocationRecipe.make(name="apples", fc_owner=self.user.customer)
        LocationRecipe.make(name="oranges", fc_owner=self.user.customer)
        res = self.client.get("/api/locations/")
        self.assertEqual(
            ["apples", "oranges", "peaches"],
            [obj["name"] for obj in res.data["results"]],
        )

    def test_get_only_current_customers_locations(self):
        location = LocationRecipe.make(name="mine", fc_owner=self.user.customer)
        LocationRecipe.make(name="other", fc_owner=CustomerRecipe.make())

        res = self.client.get("/api/locations/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        self.assertCountEqual([location.pk], [row["id"] for row in result])

    def test_get_location(self):
        location = LocationRecipe.make(name="mine", fc_owner=self.user.customer)
        res = self.client.get("/api/locations/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        result_obj = result[0]
        self.assertEqual(location.pk, result_obj["id"])
        self.assertCountEqual(
            result_obj.keys(),
            [
                "id",
                "name",
                "area",
                "description",
                "open_sunday",
                "open_monday",
                "open_tuesday",
                "open_wednesday",
                "open_thursday",
                "open_friday",
                "open_saturday",
                "radius",
                "time_of_operation",
                "timezone",
                "type",
                "max_speed",
                "driving_directions",
                "photo",
                "company",
                "primary_contact",
            ],
        )

    def test_get_location_in_bbox(self):
        location = LocationRecipe.make(
            name="North Carolina",
            fc_owner=self.user.customer,
            area=NORTH_CAROLINA_GEOMETRY,
        )
        LocationRecipe.make(
            name="Charlotte",
            fc_owner=self.user.customer,
            area=CHARLOTTE_GEOMETRY,
        )

        res = self.client.get("/api/locations/?in_bbox=" + BBOX_NORTH_CAROLINA)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        result_obj = result[0]
        self.assertEqual(location.pk, result_obj["id"])

    def test_get_location_in_bbox_bad_request(self):
        LocationRecipe.make(name="other", fc_owner=CustomerRecipe.make())
        res = self.client.get("/api/locations/?in_bbox=bad_qp")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_crm_contact_locations(self):
        contact = ContactRecipe.make(fc_owner=self.user.customer)
        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
            primary_contact=contact,
        )
        res = self.client.get("/api/locations/?contact=" + str(contact.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        result_obj = result[0]
        self.assertEqual(location.pk, result_obj["id"])

    def test_get_crm_contact_no_locations(self):
        contact = ContactRecipe.make(fc_owner=self.user.customer)
        LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
        )
        res = self.client.get("/api/locations/?contact=" + str(contact.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 0)

    def test_get_crm_company_locations(self):
        company = CompanyRecipe.make(fc_owner=self.user.customer)
        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
            company=company,
        )
        res = self.client.get("/api/locations/?company=" + str(company.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        result_obj = result[0]
        self.assertEqual(location.pk, result_obj["id"])

    def test_get_crm_company_no_locations(self):
        company = CompanyRecipe.make(fc_owner=self.user.customer)
        LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
        )
        res = self.client.get("/api/locations/?company=" + str(company.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 0)

    def test_create_minimal_location(self):
        name = "Ground Zero"
        res = self.client.post(
            "/api/locations/",
            data=dict(
                name=name,
                type=self.type.pk,
                area=json.dumps(
                    {
                        "type": "Point",
                        "coordinates": [-104.4140625, 40.97989806962013],
                    }
                ),
            ),
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        location = Location.objects.get()
        self.assertEqual(name, location.name)
        self.assertEqual(self.type.pk, location.type.pk)
        self.assertIsNone(location.primary_contact)
        self.assertIsNone(location.company)
        self.assertIsNone(location.description)
        self.assertIsNone(location.driving_directions)
        self.assertIsNone(location.max_speed)
        self.assertFalse(location.open_sunday)
        self.assertFalse(location.open_monday)
        self.assertFalse(location.open_tuesday)
        self.assertFalse(location.open_wednesday)
        self.assertFalse(location.open_thursday)
        self.assertFalse(location.open_friday)
        self.assertFalse(location.open_saturday)

    def test_create_point_location_form_post(self):
        company = CompanyRecipe.make(fc_owner=self.user.customer)
        contact = ContactRecipe.make(fc_owner=self.user.customer)
        name = "Ground Zero"
        res = self.client.post(
            "/api/locations/",
            data=dict(
                name=name,
                type=self.type.pk,
                company=company.pk,
                primary_contact=contact.pk,
                area=json.dumps(
                    {
                        "type": "Point",
                        "coordinates": [-104.4140625, 40.97989806962013],
                    }
                ),
            ),
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        location = Location.objects.get()
        self.assertEqual(name, location.name)
        self.assertEqual(self.type.pk, location.type.pk)
        self.assertEqual(contact.pk, location.primary_contact.pk)
        self.assertEqual(company.pk, location.company.pk)

    def test_create_location_with_time_of_operations_as_json(self):
        res = self.client.post(
            "/api/locations/",
            data=dict(
                name="Ground Zero",
                type=self.type.pk,
                time_of_operation={"lower": 100, "upper": 200},
                area={
                    "type": "Point",
                    "coordinates": [-104.4140625, 40.97989806962013],
                },
            ),
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        location = Location.objects.get()
        self.assertEqual(location.time_of_operation.lower, 100)
        self.assertEqual(location.time_of_operation.upper, 200)

    @patch("django.db.models.fields.files.ImageField.update_dimension_fields")
    @patch("utils.storage.PublicMediaStorage.save")
    @override_settings(PUBLIC_MEDIA_URL="http://media.test.com")
    def test_create_point_location_form_post_with_photo(self, mock_save, _):
        mock_save.return_value = "image.png"

        res = self.client.post(
            "/api/locations/",
            data=dict(
                name="Ground Zero",
                photo=open("utils/tests/image.png", "br"),
                type=self.type.pk,
                area=json.dumps(
                    {
                        "type": "Point",
                        "coordinates": [-104.4140625, 40.97989806962013],
                    }
                ),
            ),
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        loc: Location = Location.objects.get()

        self.assertEqual(loc.photo.url, "http://media.test.com/image.png")

    def test_create_point_location_json_post(self):
        res = self.client.post(
            "/api/locations/",
            data=dict(
                name="Ground Zero",
                type=self.type.pk,
                area={
                    "type": "Point",
                    "coordinates": [-104.4140625, 40.97989806962013],
                },
            ),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_create_circle_point_location_json_post(self):
        area_type = "Point"
        area_radius = 100.0
        res = self.client.post(
            "/api/locations/",
            data=dict(
                name="Ground Zero",
                type=self.type.pk,
                radius=area_radius,
                area={
                    "type": area_type,
                    "coordinates": [-104.4140625, 40.97989806962013],
                },
            ),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["area"]["type"], area_type)
        location = Location.objects.get(id=res.data["id"])
        self.assertEqual(location.radius, area_radius)
        self.assertEqual(type(location.area), Polygon)
        self.assertEqual(LocationHistory.objects.count(), 0)

    def test_set_customer_on_create(self):
        description = "THIS IS A TEST"
        name = "Ground Zero"
        res = self.client.post(
            "/api/locations/",
            data=dict(
                name=name,
                description=description,
                type=self.type.pk,
                area={
                    "type": "Point",
                    "coordinates": [-104.4140625, 40.97989806962013],
                },
            ),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        location = Location.objects.get(id=res.data["id"])
        self.assertEqual(location.fc_owner.id, self.user.customer.pk)
        self.assertEqual(location.name, name)
        self.assertEqual(location.description, description)

    def test_set_time_of_operation_on_create(self):
        description = "THIS IS A TEST"
        name = "Ground Zero"
        eight_am = 8 * 60 * 60
        five_pm = 17 * 60 * 60
        res = self.client.post(
            "/api/locations/",
            data=dict(
                name=name,
                description=description,
                type=self.type.pk,
                open_monday=False,
                open_tuesday=True,
                open_sunday=True,
                open_wednesday=False,
                open_thursday=True,
                open_friday=False,
                open_saturday=True,
                time_of_operation={"lower": eight_am, "upper": five_pm},
                timezone="UTC",
                area={
                    "type": "Point",
                    "coordinates": [-104.4140625, 40.97989806962013],
                },
            ),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        location = Location.objects.get(id=res.data["id"])
        self.assertEqual(location.fc_owner.id, self.user.customer.pk)
        self.assertEqual(location.name, name)
        self.assertEqual(location.open_monday, False)
        self.assertEqual(location.open_tuesday, True)
        self.assertEqual(location.open_sunday, True)
        self.assertEqual(location.open_wednesday, False)
        self.assertEqual(location.open_thursday, True)
        self.assertEqual(location.open_friday, False)
        self.assertEqual(location.open_saturday, True)
        self.assertEqual(
            [
                location.time_of_operation.lower,
                location.time_of_operation.upper,
            ],
            [eight_am, five_pm],
        )
        self.assertEqual(location.timezone.zone, "UTC")

    def test_driving_instructions_on_create(self):
        driving_directions = "Hello World"
        max_speed = 50
        res = self.client.post(
            "/api/locations/",
            data=dict(
                name="Ground Zero",
                description="Test",
                type=self.type.pk,
                max_speed=max_speed,
                driving_directions=driving_directions,
                area={
                    "type": "Point",
                    "coordinates": [-104.4140625, 40.97989806962013],
                },
            ),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        location = Location.objects.get(id=res.data["id"])
        self.assertEqual(location.fc_owner.id, self.user.customer.pk)
        self.assertEqual(location.driving_directions, driving_directions)
        self.assertEqual(location.max_speed, max_speed)

    def test_overlapping_fails(self):
        LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
            area=NORTH_CAROLINA_GEOMETRY,
        )
        res = self.client.post(
            "/api/locations/",
            data=dict(
                name="Ground Zero",
                description="Test",
                type=self.type.pk,
                area=CHARLOTTE,
            ),
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_updating_location(self):
        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
            area=NORTH_CAROLINA_GEOMETRY,
        )
        res = self.client.put(
            f"/api/locations/{location.pk}/",
            data=dict(
                name="Ground Zero",
                description="Test",
                type=self.type.pk,
                area=CHARLOTTE,
            ),
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        location.refresh_from_db()

        self.assertEqual(location.name, "Ground Zero")

    def test_updating_circle_location(self):
        location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
            area=DANVILLE_POINT_GEOMETRY,
            radius=100.0,
        )
        new_radius = 50.0
        res = self.client.put(
            f"/api/locations/{location.pk}/",
            data=dict(
                name="Ground Zero",
                description="Test",
                type=self.type.pk,
                area=CONCORD_POINT,
                radius=new_radius,
            ),
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        location.refresh_from_db()
        self.assertEqual(location.radius, new_radius)

    @patch("django.db.models.fields.files.ImageField.update_dimension_fields")
    @patch("utils.storage.PublicMediaStorage.open")
    @patch("utils.storage.PublicMediaStorage.save")
    @override_settings(PUBLIC_MEDIA_URL="http://media.test.com")
    def test_patching_location_photo(self, mock_save, mock_open, _):
        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
            area=NORTH_CAROLINA_GEOMETRY,
            time_of_operation=(100, 200),
        )
        location.refresh_from_db()
        self.assertEqual(location.time_of_operation, NumericRange(100, 200))
        image = open("utils/tests/image.png", "br")

        mock_save.return_value = "image.png"
        mock_open.return_value = image

        res = self.client.patch(
            f"/api/locations/{location.pk}/", data=dict(photo=image)
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(res.data["photo"], "http://media.test.com/image.png")

        location = Location.objects.get()
        self.assertEqual(location.time_of_operation, NumericRange(100, 200))

    def test_get_with_full_company_and_contact_object(self):
        company = CompanyRecipe.make(fc_owner=self.user.customer)
        contact = ContactRecipe.make(fc_owner=self.user.customer)
        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
            area=NORTH_CAROLINA_GEOMETRY,
            time_of_operation=(100, 200),
            company=company,
            primary_contact=contact,
        )
        res = self.client.get(f"/api/locations/{location.pk}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["company"]["id"], company.pk)
        self.assertEqual(res.data["company"]["name"], company.name)

        self.assertEqual(res.data["primary_contact"]["id"], contact.pk)
        self.assertEqual(
            res.data["primary_contact"]["first_name"], contact.first_name
        )
        self.assertEqual(
            res.data["primary_contact"]["last_name"], contact.last_name
        )

    def test_get_only_current_customers_location_vehicles(self):
        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
        )
        location_other: Location = LocationRecipe.make(
            name="other",
            fc_owner=CustomerRecipe.make(),
        )
        vehicle = VehicleRecipe.make(customer=self.user.customer)
        vehicle_other = VehicleRecipe.make(customer=CustomerRecipe.make())
        LocationHistoryRecipe.make(vehicle=vehicle, location=location)
        LocationHistoryRecipe.make(
            vehicle=vehicle_other, location=location_other
        )

        res = self.client.get(f"/api/locations/{location.pk}/vehicles/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)

    def test_get_location_vehicles(self):
        test_date = timezone.now()
        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
        )
        vehicle = VehicleRecipe.make(customer=self.user.customer)
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(
                test_date, test_date + timedelta(seconds=1)
            ),
        )
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(
                test_date + timedelta(seconds=1),
                test_date + timedelta(minutes=1),
            ),
        )
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(test_date + timedelta(minutes=1), None),
        )

        res = self.client.get(f"/api/locations/{location.pk}/vehicles/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        result_obj = result[0]
        self.assertEqual(vehicle.pk, result_obj["id"])
        self.assertCountEqual(
            result_obj.keys(),
            ["id", "total_inside_time", "ingress_count", "egress_count"],
        )
        self.assertEqual(result_obj["total_inside_time"], 60)
        self.assertEqual(result_obj["ingress_count"], 3)
        self.assertEqual(result_obj["egress_count"], 2)

    def test_get_location_vehicles_date_filter(self):
        test_date_start_iso = "2020-01-01T10:00:00"
        test_date_end_iso = "2020-01-02T10:00:00"
        test_date = datetime.strptime(
            test_date_start_iso, "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=pytz.UTC)

        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
        )
        vehicle = VehicleRecipe.make(customer=self.user.customer)
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(test_date, test_date + timedelta(days=1)),
        )
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(
                test_date + timedelta(days=2),
                test_date + timedelta(days=3),
            ),
        )
        res = self.client.get(
            f"/api/locations/{location.pk}/vehicles/",
            {
                "duration__range_lower": test_date_start_iso,
                "duration__range_upper": test_date_end_iso,
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        self.assertCountEqual(
            [vehicle.pk],
            [row["id"] for row in result if row["id"] == vehicle.pk],
        )

    def test_get_location_vehicles_date_changed_by_filter(self):
        test_date_start_iso = "2020-02-02T10:00:00"
        test_date_end_iso = "2020-02-02T10:01:00"
        test_date = datetime.strptime(
            test_date_start_iso, "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=pytz.UTC)

        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
        )
        vehicle = VehicleRecipe.make(customer=self.user.customer)
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(test_date, test_date + timedelta(days=1)),
        )

        res = self.client.get(
            f"/api/locations/{location.pk}/vehicles/",
            {
                "duration__range_lower": test_date_start_iso,
                "duration__range_upper": test_date_end_iso,
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data["results"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["total_inside_time"], 60)

    def test_get_location_vehicle(self):
        test_date = timezone.now()
        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
        )
        vehicle = VehicleRecipe.make(customer=self.user.customer)
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(
                test_date, test_date + timedelta(seconds=1)
            ),
        )
        location_history = LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(
                test_date + timedelta(seconds=1),
                test_date + timedelta(minutes=1),
            ),
        )

        res = self.client.get(
            f"/api/locations/{location.pk}/vehicles/{vehicle.pk}/"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data
        self.assertCountEqual(result.keys(), ["location_history", "vehicle"])
        self.assertEqual(len(result["location_history"]), 2)

        location_history_data = result["location_history"][0]
        vehicle_data = result["vehicle"]
        self.assertCountEqual(
            location_history_data.keys(),
            ["id", "duration", "location", "vehicle"],
        )
        self.assertCountEqual(
            vehicle_data.keys(),
            ["id", "total_inside_time", "ingress_count", "egress_count"],
        )
        self.assertEqual(location_history.pk, location_history_data["id"])
        self.assertEqual(vehicle.pk, vehicle_data["id"])

    def test_get_location_vehicle_date_filter(self):
        test_date_start_iso = "2020-01-01T11:00:00"
        test_date_end_iso = "2020-01-02T11:00:00"
        test_date = datetime.strptime(
            test_date_start_iso, "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=pytz.UTC)

        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
        )
        vehicle = VehicleRecipe.make(customer=self.user.customer)
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(test_date, test_date + timedelta(days=1)),
        )
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(
                test_date + timedelta(days=2),
                test_date + timedelta(days=3),
            ),
        )

        res = self.client.get(
            f"/api/locations/{location.pk}/vehicles/{vehicle.pk}/",
            {
                "duration__range_lower": test_date_start_iso,
                "duration__range_upper": test_date_end_iso,
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        location_history_data = res.data["location_history"]
        self.assertEqual(len(location_history_data), 1)

    def test_get_location_histogram(self):
        test_date = timezone.now()
        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
        )
        vehicle = VehicleRecipe.make(customer=self.user.customer)
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(
                test_date, test_date + timedelta(seconds=1)
            ),
        )
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(
                test_date + timedelta(seconds=1),
                test_date + timedelta(minutes=1),
            ),
        )

        res = self.client.get(f"/api/locations/{location.pk}/histogram/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_get_location_histogram_date_filter(self):
        from tracker.models import VehicleState
        from tracker.baker_recipes import vehicle_state_recipe

        test_date_start_iso = "2020-01-01T10:05:00"
        test_date_end_iso = "2020-01-02T10:05:00"
        test_date = datetime.strptime(
            test_date_start_iso, "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=pytz.UTC)

        location: Location = LocationRecipe.make(
            name="mine",
            fc_owner=self.user.customer,
        )
        vehicle = VehicleRecipe.make(customer=self.user.customer)
        vehicle_2 = VehicleRecipe.make(customer=self.user.customer)
        LocationHistoryRecipe.make(
            vehicle=vehicle,
            location=location,
            duration=DateTimeTZRange(test_date, test_date + timedelta(hours=1)),
        )
        vehicle_state_recipe(
            vehicle,
            test_date,
            duration=timedelta(minutes=65),
            type=VehicleState.TYPES.stopped,
        ).make()
        vehicle_state_recipe(
            vehicle_2,
            test_date,
            duration=timedelta(minutes=85),
            type=VehicleState.TYPES.traveling,
        ).make()
        LocationHistoryRecipe.make(
            vehicle=vehicle_2,
            location=location,
            duration=DateTimeTZRange(test_date, None),
        )
        res = self.client.get(
            f"/api/locations/{location.pk}/histogram/",
            {
                "duration__range_lower": test_date_start_iso,
                "duration__range_upper": test_date_end_iso,
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        result = res.data
        self.assertEqual(len(result), 25)
        self.assertEqual(
            result["2020-01-01T10:00:00.000000Z"],
            {
                "entered": 2,
                "inside": 2,
                "exited": 0,
                "traveling": 3600,
                "idling": 0,
                "stopped": 3600,
                "towed": 0,
                "total": 7200,
            },
        )
        self.assertEqual(
            result["2020-01-01T11:00:00.000000Z"],
            {
                "entered": 0,
                "inside": 2,
                "exited": 1,
                "traveling": 3600,
                "idling": 0,
                "stopped": 3600,
                "towed": 0,
                "total": 7200,
            },
        )
        self.assertEqual(
            result["2020-01-02T10:00:00.000000Z"],
            {
                "entered": 0,
                "inside": 1,
                "exited": 0,
                "traveling": 0,
                "idling": 0,
                "stopped": 0,
                "towed": 0,
                "total": 0,
            },
        )


class LocationApiVehiclesInsideTestCase(FCTestCase):
    databases = "__all__"

    def setUp(self):
        super().setUp()

        self.client = APIClient()
        self.user = UserRecipe.make()
        local_state.customer = self.user.customer
        self.client.force_authenticate(self.user)
        self.type = LocationTypeRecipe.make(customer=self.user.customer)
        self.vehicle = VehicleRecipe.make(customer=self.user.customer)

        self.start_time = NON_AWARE_TEST_NOW

        ReadingRecipe.make(
            _quantity=2,
            vehicle_id=self.vehicle.id,
            status=Reading.STATUS_CHOICES.valid,
            movement_type=Reading.MOVEMENT_TYPES.traveling,
            point=Point(-104.4140625, 40.97989806962013),
            datetime=seq(
                self.start_time + timedelta(minutes=2), timedelta(seconds=10)
            ),
        )

    def tearDown(self):
        local_state.clear()

    # FIXME: NOt sure why this test is failing yet.
    # def test_create_location_vehicle_inside(self):
    #     area_type = "Point"
    #     area_radius = 100.0
    #     res = self.client.post(
    #         "/api/locations/",
    #         data=dict(
    #             name="Ground Zero",
    #             type=self.type.pk,
    #             radius=area_radius,
    #             area={
    #                 "type": area_type,
    #                 "coordinates": [-104.4140625, 40.97989806962013],
    #             },
    #         ),
    #         format="json",
    #     )
    #     new_lh = LocationHistory.objects.first()
    #     self.assertEqual(res.status_code, status.HTTP_201_CREATED)
    #     self.assertEqual(LocationHistory.objects.count(), 1)
    #     self.assertEqual(
    #         new_lh.get_duration_lower(), Reading.objects.first().datetime
    #     )
    #     self.assertIsNone(new_lh.get_duration_upper())

    def test_create_location_vehicle_inside_with_lh(self):
        location = LocationRecipe.make(fc_owner=self.user.customer)
        location_history = LocationHistoryRecipe.make(
            location=location,
            vehicle=self.vehicle,
            duration=DateTimeTZRange(
                self.start_time - timedelta(minutes=2), None
            ),
        )
        area_type = "Point"
        area_radius = 100.0
        res = self.client.post(
            "/api/locations/",
            data=dict(
                name="Ground Zero",
                type=self.type.pk,
                radius=area_radius,
                area={
                    "type": area_type,
                    "coordinates": [-104.4140625, 40.97989806962013],
                },
            ),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(LocationHistory.objects.count(), 2)

        prev_lh = LocationHistory.objects.last()
        self.assertEqual(prev_lh.id, location_history.id)
        latest_reading_datetime = list(
            Reading.objects.all(vehicle_id=self.vehicle.pk)
        )[-1].datetime
        self.assertEqual(prev_lh.get_duration_upper(), latest_reading_datetime)

        new_lh = LocationHistory.objects.first()
        self.assertEqual(new_lh.get_duration_lower(), latest_reading_datetime)
        self.assertIsNone(new_lh.get_duration_upper())
