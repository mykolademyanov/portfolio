from rest_framework import serializers
from vehicle.models import Vehicle
from utils.dates import iso_to_datetime
from .location_history import LocationHistorySerializer


class LocationVehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ("id",)

    def _get_total_inside_time(self, qs):
        params = self.context["params"]
        start = iso_to_datetime(params.get("duration__range_lower"))
        end = iso_to_datetime(params.get("duration__range_upper"))
        duration_in_seconds = 0

        for history in qs:
            duration_in_seconds += history.duration_in_seconds(start, end)
        return int(duration_in_seconds)

    def to_representation(self, instance):
        qs = self.context["l_history"].filter(vehicle=instance)

        return {
            "id": instance.id,
            "total_inside_time": self._get_total_inside_time(qs),
            "ingress_count": qs.count(),
            "egress_count": qs.exclude(duration__endswith=None).count(),
        }


class LocationVehicleDetailsSerializer(serializers.ModelSerializer):
    location_history = LocationHistorySerializer(many=True)
    vehicle = LocationVehicleSerializer()

    class Meta:
        model = Vehicle
        fields = ("location_history", "vehicle")
