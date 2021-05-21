from colorful.fields import RGBColorField
from django.contrib.gis.db.models import Q
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import QuerySet
from model_utils import Choices
from model_utils.models import TimeStampedModel

from accounting.models import Customer

LOCATION_TYPE_ICONS = Choices(
    (
        "material#local_parking",
        "material_local_parking",
        "material#local_parking",
    ),
    ("material#restaurant", "material_restaurant", "material#restaurant"),
    ("material#home", "material_home", "material#home"),
    (
        "material#local_gas_station",
        "material_local_gas_station",
        "material#local_gas_station",
    ),
    (
        "material#business_center",
        "material_business_center",
        "material#business_center",
    ),
    ("material#swap_calls", "material_swap_calls", "material#swap_calls"),
    (
        "material#report_problem",
        "material_report_problem",
        "material#report_problem",
    ),
    ("custom#drop", "custom_drop", "custom#drop"),
    ("custom#working_yard", "custom_working_yard", "custom#working_yard"),
    ("custom#pick_up", "custom_pick_up", "custom#pick_up"),
    ("material#terrain", "material_terrain", "material#terrain"),
    ("material#favorite", "material_favorite", "material#favorite"),
    (
        "material#verified_user",
        "material_verified_user",
        "material#verified_user",
    ),
    (
        "material#assistant_photo",
        "material_assistant_photo",
        "material#assistant_photo",
    ),
    ("material#flash_on", "material_flash_on", "material#flash_on"),
    ("material#whatshot", "material_whatshot", "material#whatshot"),
    (
        "material#remove_circle",
        "material_remove_circle",
        "material#remove_circle",
    ),
    ("material#hotel", "material_hotel", "material#hotel"),
)


class LocationTypeQuerySet(QuerySet):
    def for_customer(self, customer: Customer):
        return self.filter(Q(customer=customer) | Q(system=True))


class LocationType(TimeStampedModel):
    color = RGBColorField()
    system = models.BooleanField(default=False)
    name = models.CharField(max_length=200)
    icon = models.CharField(
        choices=LOCATION_TYPE_ICONS,
        max_length=50,
        default=LOCATION_TYPE_ICONS.material_business_center,
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, null=True, blank=True
    )

    objects = LocationTypeQuerySet.as_manager()

    def clean(self):
        if self.system:
            if self.customer is not None:
                raise ValidationError(
                    {"system": "A system type can not be related to a customer"}
                )
        elif self.customer is None:
            raise ValidationError(
                {"customer": "This field is required, for non system types."}
            )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_system_name",
                fields=["name", "system"],
                condition=Q(system=True),
            ),
            models.UniqueConstraint(
                name="unique_customer_name",
                fields=["name", "customer"],
                condition=Q(system=False),
            ),
        ]
