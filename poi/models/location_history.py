from django.contrib.gis.db.models import Q
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from model_utils.models import TimeStampedModel

from accounting.models import Customer
from poi.models import Location
from vehicle.models import Vehicle


class LocationHistoryQuerySet(models.QuerySet):
    def for_customer(self, customer: Customer):
        return self.filter(location__fc_owner=customer)

    def entered(self, start, end):
        return self.filter(duration__startswith__range=(start, end))

    def exited(self, start, end):
        return self.filter(duration__endswith__range=(start, end))


class LocationHistory(TimeStampedModel):
    duration = DateTimeRangeField()
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, db_index=True
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, db_index=True
    )
    created_by_replace = models.BooleanField(default=False)
    updated_by_replace = models.BooleanField(default=False)

    objects = LocationHistoryQuerySet.as_manager()

    class Meta:
        ordering = ("-duration",)
        constraints = [
            models.UniqueConstraint(
                name="allow_only_one_open_history_per_vehicle",
                fields=["vehicle"],
                condition=Q(
                    duration__endswith__isnull=True,
                    duration__startswith__isnull=False,
                ),
            ),
            ExclusionConstraint(
                name="dont_overlap",
                index_type="GIST",
                expressions=[
                    ("duration", RangeOperators.OVERLAPS),
                    ("vehicle", RangeOperators.EQUAL),
                ],
            ),
        ]

    def __str__(self):
        return f"Location history {self.pk} - {self.vehicle.pk}"

    def clean(self):
        if (
            self.vehicle
            and not self.get_duration_upper()
            and self.is_vehicle_inside
        ):
            raise ValidationError(
                {
                    "vehicle": "Allowed only one opened Location History per vehicle"
                }
            )

    def get_duration_lower(self):
        return getattr(self.duration, "lower", None)

    def get_duration_upper(self):
        return getattr(self.duration, "upper", None)

    @property
    def is_active(self):
        return not bool(self.get_duration_upper())

    def duration_in_seconds(self, start=None, end=None):
        # Lower Time
        lower = self.get_duration_lower()
        lower = start if start and start >= lower else lower
        # Upper Time
        upper = self.get_duration_upper() or timezone.now()
        upper = end if end and end <= upper else upper

        if lower and upper:
            return max((upper - lower).total_seconds(), 0)
        return 0

    def _is_duration_inside(self, duration):
        if not duration:
            return False

        lower = getattr(duration, "lower", None)
        upper = getattr(duration, "upper", None)

        try:
            return (
                self.get_duration_lower() < lower
                and self.get_duration_upper() > upper
            )
        except TypeError:
            return False

    @property
    def vehicle_location(self):
        if not self.get_duration_upper():
            return self.location

    @property
    def is_vehicle_inside(self):
        return self.vehicle.locationhistory_set.filter(
            duration__endswith__isnull=True
        ).exists()
