from abc import ABC

from rest_framework import serializers
from rest_framework_gis.fields import GeometryField
from utils.converter import point_to_polygon, polygon_to_point
from utils.dates import iso_to_datetime
from psycopg2._range import DateTimeTZRange


class AreaSerializerField(GeometryField):
    def get_attribute(self, instance):
        instance.area = polygon_to_point(instance.area, instance.radius)
        return super().get_attribute(instance)

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        radius = self.context["request"].data.get("radius")
        return point_to_polygon(data, radius)


class StatusSerializerField(serializers.Field, ABC):
    def get_attribute(self, instance):
        query_params = getattr(self.context["request"], "query_params", {})
        start = iso_to_datetime(query_params.get("duration_start"))
        end = iso_to_datetime(query_params.get("duration_end"))

        if start and end and start < end:
            instance.status = DateTimeTZRange(start, end)

        return super().get_attribute(instance)

    def to_representation(self, value):
        return value
