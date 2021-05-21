from rest_framework import serializers
from rest_framework.fields import CharField

from poi.models import LocationHistory


class LocationHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationHistory
        fields = (
            "id",
            "duration",
            "location",
            "vehicle",
        )
