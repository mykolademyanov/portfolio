from django.db.models import Q
from drf_extra_fields.fields import IntegerRangeField
from psycopg2._range import NumericRange
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.fields import (
    TimezoneField,
    OwnerFilteredPresentablePrimaryKeyRelatedField,
)
from core.local import local_state
from crm.models import Company, Contact
from poi import models
from poi.api.serializers import AreaSerializerField


class LocationCompany(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "name")


class LocationContact(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ("id", "first_name", "last_name")


class LocationSerializer(serializers.ModelSerializer):
    timezone = TimezoneField(required=False)
    time_of_operation = IntegerRangeField(
        default=NumericRange(lower=0, upper=86400),
        required=False,
        allow_null=True,
    )
    company = OwnerFilteredPresentablePrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        queryset=Company.objects.all(),
        presentation_serializer=LocationCompany,
    )

    primary_contact = OwnerFilteredPresentablePrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        queryset=Contact.objects.all(),
        presentation_serializer=LocationContact,
    )

    area = AreaSerializerField()

    def update(self, instance, validated_data):
        if self.partial:
            nr = validated_data.get("time_of_operation", NumericRange())
            if (nr.lower, nr.upper,) == (
                None,
                None,
            ) and "time_of_operation" in validated_data:
                validated_data.pop("time_of_operation")

        return super(LocationSerializer, self).update(instance, validated_data)

    class Meta:
        model = models.Location
        fields = (
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
            "time_of_operation",
            "timezone",
            "type",
            "max_speed",
            "driving_directions",
            "photo",
            "company",
            "primary_contact",
            "radius",
        )

    def validate(self, attrs):

        if "area" in attrs:
            qs = models.Location.objects.for_customer(local_state.customer)
            if self.instance:
                qs = qs.exclude(pk=self.instance.id)

            if qs.filter(area__relate=(attrs["area"], "2********")).exists():
                raise ValidationError(
                    {
                        "area": "Current location overlaps with an existing location"
                    }
                )
        return attrs


class LocationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.LocationType
        fields = ("id", "name", "color", "icon")

    @staticmethod
    def validate_name(name):
        if models.LocationType.objects.filter(
            Q(system=True) | Q(customer=local_state.customer), name=name
        ).exists():
            raise serializers.ValidationError(
                "Location Type with such name already exists."
            )
        return name

    def validate(self, attrs):
        if self.instance and self.instance.system:
            raise ValidationError("System location types can not be changed.")

        instance = models.LocationType(**attrs, customer=local_state.customer)
        instance.clean()
        return attrs
