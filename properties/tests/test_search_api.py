from itertools import cycle

from django.test import TestCase
from moneyed import Money
from rest_framework import status
from rest_framework.test import APIClient

from pgr_django.properties.constants import (
    STATUS_ACTIVE, STATUS_INACTIVE, STATUS_SOLD
)
from pgr_django.properties.models import Property
from pgr_django.properties.tests.baker_recipes import PropertyRecipe


class SearchAPITestCase(TestCase):

    def setUp(self) -> None:
        self.client = APIClient()
        PropertyRecipe.make(
            country="United States",
            region="Nevada",
            city="Las Vegas",
            address=None,
            status=cycle([STATUS_ACTIVE, STATUS_INACTIVE, STATUS_SOLD]),
            _quantity=3
        )

    def test_default_status_filters(self):
        active_property = Property.objects.get(status=STATUS_ACTIVE)
        response = self.client.get(
            "/properties/search"
            f"?countries=UNITED STATES"
            f"&cities=Las Vegas"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["id"], active_property.id)

    def test_agent_profile_statuses_filters(self):
        sold_property = Property.objects.get(status=STATUS_SOLD)
        response = self.client.get(
            "/properties/search"
            f"?countries=UNITED STATES"
            f"&cities=Las Vegas"
            f"&status=sold"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["id"], sold_property.id)

    def test_required_fields_in_response(self):
        response = self.client.get(
            "/properties/search"
            f"?countries=UNITED STATES"
            f"&cities=Las Vegas"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(
            set(response.data["items"][0].keys()),
            {
                'id',
                'photos',
                'price',
                'price_currency',
                'price_min',
                'price_max',
                'price_min_currency',
                'price_max_currency',
                'monthly_hoa_fee',
                'monthly_hoa_fee_currency',
                'monthly_hoa_fee_min',
                'monthly_hoa_fee_max',
                'monthly_hoa_fee_min_currency',
                'monthly_hoa_fee_max_currency',
                'country',
                'city',
                'street',
                'region',
                'baths',
                'baths_min',
                'baths_max',
                'beds',
                'beds_min',
                'beds_max',
                'lot_size',
                'lot_size_min',
                'lot_size_max',
                'agent',
                'buy_rent',
                'location'
            }
        )

    def test_price_filter_min_max_prices(self):
        PropertyRecipe.make(
            country="United States",
            region="Nevada",
            city="Las Vegas",
            address=None,
            price_min=cycle([Money("4.00"), Money("8.00")]),
            price_max=cycle([Money("8.00"), Money("12.00")]),
            status=STATUS_ACTIVE
        )
        response = self.client.get(
            "/properties/search"
            f"?countries=UNITED STATES"
            f"&cities=Las Vegas"
            f"&minprice=5"
            f"&maxprice=7"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 1)
        resp_prop = response.data["items"][0]
        self.assertEqual(resp_prop["price_min"], "4.00")
        self.assertEqual(resp_prop["price_max"], "8.00")

    def test_price_filter_price_field_filled(self):
        PropertyRecipe.make(
            country="United States",
            region="Nevada",
            city="Las Vegas",
            address=None,
            price=cycle([Money("4.00"), Money("8.00")]),
            status=STATUS_ACTIVE
        )
        response = self.client.get(
            "/properties/search"
            f"?countries=UNITED STATES"
            f"&cities=Las Vegas"
            f"&minprice=3"
            f"&maxprice=5"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 1)
        resp_prop = response.data["items"][0]
        self.assertEqual(resp_prop["price"], "4.00")
