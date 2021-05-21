from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.baker_recipes import UserRecipe
from poi.models import Location
from poi.baker_recipes import LocationTypeRecipe
from poi.tests.geojson_locations import (
    CHARLOTTE_GEOMETRY,
    NORTH_CAROLINA_GEOMETRY,
)


class LocationTestCase(TestCase):
    def setUp(self):
        self.user = UserRecipe.make()
        self.customer = self.user.customer
        self.type = LocationTypeRecipe.make(customer=self.customer)

    def test_create_a_location_point(self):
        loc = Location(area=Point(0, 0), fc_owner=self.customer, type=self.type)
        loc.save()

    def test_create_a_polygon(self):
        loc = Location(
            area=CHARLOTTE_GEOMETRY, fc_owner=self.customer, type=self.type
        )
        loc.save()

    def test_create_overlapping_polygon(self):
        loc = Location(
            name="North Carolina",
            area=NORTH_CAROLINA_GEOMETRY,
            fc_owner=self.customer,
            type=self.type,
        )
        loc.full_clean()
        loc.save()
        loc2 = Location(
            name="Charlotte",
            area=CHARLOTTE_GEOMETRY,
            fc_owner=self.customer,
            type=self.type,
        )
        self.assertRaises(ValidationError, loc2.full_clean)

    def test_updating_overlapping_polygon(self):
        loc = Location(
            name="North Carolina",
            area=NORTH_CAROLINA_GEOMETRY,
            fc_owner=self.customer,
            type=self.type,
        )
        loc.full_clean()
        loc.save()
        loc.area = CHARLOTTE_GEOMETRY
        loc.full_clean()
        loc.save()
