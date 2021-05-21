import pytz

from core.tests.base import FCTestCase
from datetime import datetime, timedelta
from psycopg2._range import DateTimeTZRange

from authentication.baker_recipes import UserRecipe
from poi.models import Location, LocationHistory
from poi.baker_recipes import LocationTypeRecipe
from poi.tests.geojson_locations import CHARLOTTE_GEOMETRY
from vehicle.baker_recipes import VehicleRecipe


class LocationTestCase(FCTestCase):
    databases = "__all__"

    def setUp(self):
        super().setUp()

        self.user = UserRecipe.make()
        self.customer = self.user.customer
        self.type = LocationTypeRecipe.make(customer=self.customer)
        self.vehicle = VehicleRecipe.make(customer=self.customer)
        self.datetime_now = datetime.now().replace(tzinfo=pytz.UTC)

    def test_create_a_location_history(self):
        loc = Location(
            area=CHARLOTTE_GEOMETRY, fc_owner=self.customer, type=self.type
        )
        loc.save()
        loc_history = LocationHistory(
            location=loc,
            duration=DateTimeTZRange(self.datetime_now, None),
            vehicle=self.vehicle,
        )
        loc_history.save()

        self.assertEqual(loc_history.vehicle_location, loc)
        self.assertEqual(
            loc_history.duration, DateTimeTZRange(self.datetime_now, None)
        )
        self.assertEqual(loc_history.vehicle, self.vehicle)

    def test_create_a_location_history_with_left_status(self):
        loc = Location(
            area=CHARLOTTE_GEOMETRY, fc_owner=self.customer, type=self.type
        )
        loc.save()
        loc_history = LocationHistory(
            location=loc,
            duration=DateTimeTZRange(self.datetime_now, self.datetime_now),
            vehicle=self.vehicle,
        )
        loc_history.save()

        self.assertIsNone(loc_history.vehicle_location)

    def test_location_history_duration_in_seconds(self):
        day_seconds = 86400
        start = self.datetime_now
        end = self.datetime_now + timedelta(days=1)
        loc = Location(
            area=CHARLOTTE_GEOMETRY, fc_owner=self.customer, type=self.type
        )
        loc.save()
        loc_history = LocationHistory(
            location=loc,
            duration=DateTimeTZRange(start, end),
            vehicle=self.vehicle,
        )
        loc_history.save()
        # No changes
        self.assertEqual(loc_history.duration_in_seconds(), day_seconds)
        # When Filters more then start and end
        self.assertEqual(
            loc_history.duration_in_seconds(
                start - timedelta(seconds=1), end + timedelta(seconds=1)
            ),
            day_seconds,
        )
        # When Filters less then start
        self.assertEqual(
            loc_history.duration_in_seconds(start + timedelta(seconds=1), end),
            day_seconds - 1,
        )
        # When Filters less then end
        self.assertEqual(
            loc_history.duration_in_seconds(start, end - timedelta(seconds=1)),
            day_seconds - 1,
        )
        # When Filters both less then start and end
        self.assertEqual(
            loc_history.duration_in_seconds(
                start + timedelta(seconds=1), end - timedelta(seconds=1)
            ),
            day_seconds - 2,
        )
        # When Filters equal
        self.assertEqual(loc_history.duration_in_seconds(start, start), 0)
        self.assertEqual(loc_history.duration_in_seconds(end, end), 0)
        # When Filters not correct
        self.assertEqual(loc_history.duration_in_seconds(end, start), 0)
