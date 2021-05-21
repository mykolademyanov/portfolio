from datetime import timedelta

from django.utils.timezone import now
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from core.local import local_state
from poi.api import serializers
from poi.api.filters import LocationHistoryFilter
from poi.models import LocationHistory
from telemetry.api.serializers import VehicleStateReadingSerializer
from telemetry.models.bt.reading import Reading


class LocationHistoryViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers.LocationHistorySerializer
    filter_backends = (DjangoFilterBackend,)
    filter_class = LocationHistoryFilter

    def get_queryset(self):
        return LocationHistory.objects.for_customer(local_state.customer)

    @staticmethod
    def _get_lower_expand(obj):
        if obj.get_duration_lower():
            return Reading.objects.first_active(
                lower={
                    "vehicle_id": obj.vehicle.pk,
                    "datetime": obj.get_duration_lower()
                    - timedelta(minutes=10),
                },
                upper={
                    "vehicle_id": obj.vehicle.pk,
                    "datetime": obj.get_duration_lower(),
                },
            )
        return None

    @staticmethod
    def _get_upper_expand(obj):
        if obj.get_duration_upper():
            return Reading.objects.last_active(
                lower={
                    "vehicle_id": obj.vehicle.pk,
                    "datetime": obj.get_duration_upper(),
                },
                upper={
                    "vehicle_id": obj.vehicle.pk,
                    "datetime": obj.get_duration_upper()
                    + timedelta(minutes=10),
                },
            )
        return None

    @staticmethod
    def _get_expanded_ids(lower, upper):
        return [
            getattr(lower, "pk", None),
            getattr(upper, "pk", None),
        ]

    @staticmethod
    def _exclude_not_traveling_readings(data) -> list:
        # Exclude not traveling readings
        _new_data = []
        _prev = None

        for reading in data:
            if reading.is_traveling or not _prev or _prev.is_traveling:
                _new_data.append(reading)

            _prev = reading

        return _new_data

    @action(detail=True, methods=["GET"])
    def readings(self, request, pk=None):
        obj: LocationHistory = self.get_object()

        data = list(
            Reading.objects.sorted_range(
                lower=dict(
                    vehicle_id=obj.vehicle.pk, datetime=obj.duration.lower
                ),
                upper=dict(
                    vehicle_id=obj.vehicle.pk,
                    datetime=obj.duration.upper or now() + timedelta(seconds=1),
                ),
            )
        )

        expand = request.GET.get("expand")
        context_data = {}
        if expand:
            lower_qs = self._get_lower_expand(obj)
            upper_qs = self._get_upper_expand(obj)
            context_data["expanded_ids"] = self._get_expanded_ids(
                lower_qs, upper_qs
            )
            if lower_qs:
                data.append(lower_qs)

            if upper_qs:
                data.append(upper_qs)

        data = self._exclude_not_traveling_readings(data)
        data = sorted(data, key=lambda obj: obj.datetime)
        return Response(
            VehicleStateReadingSerializer(
                instance=data, many=True, context=context_data
            ).data
        )
