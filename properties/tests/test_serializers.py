from django.test import TestCase

from .baker_recipes import PropertyRecipe
from ..serializers import PropertyDetailSerializer


class TestPropertyDetailSerializer(TestCase):

    def setUp(self):
        self.prop = PropertyRecipe.make(
            country="United States",
            region="Nevada",
            city="Las Vegas",
            district="Clark County",
            street="6460 Racel Street",
            zip_code="89131",
            address=None,
        )

    def test_prop_without_address(self):
        """
        Test for checking whether property without address retrieve
        full_address. For old properties that don't have address field but
        should retrieve their location.
        """
        serializer = PropertyDetailSerializer(self.prop)
        serializer_data = serializer.data
        self.assertIsNone(self.prop.address)
        self.assertEqual(
            serializer_data.get('address'), self.prop.full_address
        )

    def test_prop_with_address(self):
        """Test for checking whether property with address retrieve address"""
        self.prop.address = "2173 W Live Oak Dr, Los Angeles, CA 90068"
        self.prop.save()
        serializer = PropertyDetailSerializer(self.prop)
        serializer_data = serializer.data
        self.assertIsNotNone(self.prop.address)
        self.assertEqual(
            serializer_data.get('address'), self.prop.address
        )
