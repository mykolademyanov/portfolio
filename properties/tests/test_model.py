from decimal import Decimal

from django.test import TestCase
from moneyed import Money

from pgr_django.properties.models import Property
from pgr_django.properties.tests.baker_recipes import PropertyRecipe
from pgr_django.utils.properties_parser import BUY_TYPE, RENT_TYPE


class PropertyTestCase(TestCase):

    def test_calculate_and_set_price_avg_for_buy_properties(self):
        prop = Property(
            buy_rent=BUY_TYPE,
            price_min=Money(amount=Decimal("3.00")),
            price_max=Money(amount=Decimal("7.00"))
        )
        prop.calculate_and_set_price_avg()
        self.assertEqual(prop.calculated_price_avg, Decimal("5.00"))

    def test_create_property_price_avg_calculation_for_buy_properties(self):
        prop = PropertyRecipe.make(
            buy_rent=BUY_TYPE,
            price_min=Money(amount=Decimal("3.00")),
            price_max=Money(amount=Decimal("7.00"))
        )
        self.assertEqual(prop.calculated_price_avg, Decimal("5.00"))

    def test_update_property_price_avg_calculation_for_buy_properties(self):
        prop = PropertyRecipe.make(
            buy_rent=BUY_TYPE,
            price_min=Money(amount=Decimal("3.00")),
            price_max=Money(amount=Decimal("7.00"))
        )
        prop.price_min = Money(amount=Decimal("4.00"))
        prop.price_max = Money(amount=Decimal("8.00"))
        prop.save()
        self.assertEqual(prop.calculated_price_avg, Decimal("6.00"))

    def test_calculate_price_avg_based_on_price_for_buy_properties(self):
        prop = PropertyRecipe.make(
            buy_rent=BUY_TYPE,
            price=Money(amount=Decimal("2.00")),
            price_min=None,
            price_max=Money(amount=Decimal("7.00"))
        )
        self.assertEqual(prop.calculated_price_avg, Decimal("2.00"))

    def test_calculate_and_set_price_avg_for_rent_properties(self):
        prop = Property(
            buy_rent=RENT_TYPE,
            monthly_hoa_fee_min=Money(amount=Decimal("3.00")),
            monthly_hoa_fee_max=Money(amount=Decimal("7.00"))
        )
        prop.calculate_and_set_price_avg()
        self.assertEqual(prop.calculated_price_avg, Decimal("5.00"))

    def test_create_property_price_avg_calculation_for_rent_properties(self):
        prop = PropertyRecipe.make(
            buy_rent=RENT_TYPE,
            monthly_hoa_fee_min=Money(amount=Decimal("3.00")),
            monthly_hoa_fee_max=Money(amount=Decimal("7.00"))
        )
        self.assertEqual(prop.calculated_price_avg, Decimal("5.00"))

    def test_update_property_price_avg_calculation_for_rent_properties(self):
        prop = PropertyRecipe.make(
            buy_rent=RENT_TYPE,
            monthly_hoa_fee_min=Money(amount=Decimal("3.00")),
            monthly_hoa_fee_max=Money(amount=Decimal("7.00"))
        )
        prop.monthly_hoa_fee_min = Money(amount=Decimal("4.00"))
        prop.monthly_hoa_fee_max = Money(amount=Decimal("8.00"))
        prop.save()
        self.assertEqual(prop.calculated_price_avg, Decimal("6.00"))

    def test_calculate_price_avg_based_on_price_for_rent_properties(self):
        prop = PropertyRecipe.make(
            buy_rent=RENT_TYPE,
            monthly_hoa_fee=Money(amount=Decimal("2.00")),
            monthly_hoa_fee_min=None,
            monthly_hoa_fee_max=Money(amount=Decimal("7.00"))
        )
        self.assertEqual(prop.calculated_price_avg, Decimal("2.00"))
