import django_filters

from api.filters import DateTimeRangeFilterSet
from poi.models import LocationHistory


class LocationHistoryFilter(DateTimeRangeFilterSet):
    vehicle_group = django_filters.CharFilter(
        field_name="vehicle__groups",
        lookup_expr="exact",
    )

    class Meta:
        model = LocationHistory
        fields = {
            "vehicle": [
                "exact",
            ],
            "location": [
                "exact",
            ],
            "duration": [
                "range",
            ],
        }
