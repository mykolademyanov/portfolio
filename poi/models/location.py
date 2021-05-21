from functools import partial

from django.contrib.gis.db.models import GeometryField
from django.contrib.postgres.fields import IntegerRangeField
from django.contrib.postgres.validators import (
    RangeMinValueValidator,
    RangeMaxValueValidator,
)
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import QuerySet
from django.db.models.signals import post_save
from django.dispatch import receiver
from model_utils.models import TimeStampedModel
from psycopg2._range import NumericRange
from timezone_field import TimeZoneField

from accounting.models import Customer
from crm.models import Company, Contact
from poi.models import LocationType
from utils.images import AutoRotateImageField
from utils.storage import PublicMediaStorage, customer_upload_to


class LocationQuerySet(QuerySet):
    def for_customer(self, customer: Customer):
        return self.filter(fc_owner=customer)


class Location(TimeStampedModel):
    photo_width = models.PositiveSmallIntegerField(null=True, blank=True)
    photo_height = models.PositiveSmallIntegerField(null=True, blank=True)

    photo = AutoRotateImageField(
        storage=PublicMediaStorage(),
        upload_to=partial(customer_upload_to, "location_photos"),
        width_field="photo_width",
        height_field="photo_height",
        null=True,
        blank=True,
    )

    radius = models.FloatField(
        validators=[RangeMinValueValidator(0.0)], null=True, blank=True
    )
    area = GeometryField()
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    fc_owner = models.ForeignKey(
        Customer,
        related_name="locations",
        on_delete=models.CASCADE,
        verbose_name="Owner",
    )

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True
    )
    primary_contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, null=True, blank=True
    )
    type = models.ForeignKey(LocationType, on_delete=models.CASCADE)

    # Seconds representing open and close times.
    time_of_operation = IntegerRangeField(
        validators=[RangeMinValueValidator(0), RangeMaxValueValidator(86400)],
        default=NumericRange(0, 86400),
    )
    open_sunday = models.BooleanField(default=False)
    open_monday = models.BooleanField(default=False)
    open_tuesday = models.BooleanField(default=False)
    open_wednesday = models.BooleanField(default=False)
    open_thursday = models.BooleanField(default=False)
    open_friday = models.BooleanField(default=False)
    open_saturday = models.BooleanField(default=False)
    timezone = TimeZoneField(default="US/Eastern")

    # Driving Instructions
    max_speed = models.IntegerField(
        validators=[MaxValueValidator(100)], blank=True, null=True
    )
    driving_directions = models.TextField(blank=True, null=True)

    objects = LocationQuerySet.as_manager()

    def __str__(self):
        return f"{self.fc_owner.name} - {self.name}"

    def clean(self):
        if (
            Location.objects.exclude(pk=self.id)
            .filter(
                area__relate=(self.area, "2********"), fc_owner=self.fc_owner
            )
            .exists()
        ):
            raise ValidationError(
                {"area": "Current location overlaps with an existing location"}
            )


@receiver(post_save, sender=Location)
def create_lh_for_vehicles_inside(sender, instance, created, **kwargs):
    if created:
        for vehicle in instance.fc_owner.vehicles.all():
            reading = vehicle.last_reading

            # Check if any vehicle inside new Location
            if reading and instance.area.contains(reading.point):
                # End prev LH if exists
                vehicle.update_location_history(end_datetime=reading.datetime)

                # Create new LH
                vehicle.create_location_history(
                    location=instance, start_datetime=reading.datetime
                )
