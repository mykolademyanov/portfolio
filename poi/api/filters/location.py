import django_filters
from poi.models import Location


class LocationFilter(django_filters.FilterSet):
    contact = django_filters.CharFilter(
        field_name="primary_contact",
    )

    class Meta:
        model = Location
        fields = {
            "primary_contact": [
                "exact",
            ],
            "company": [
                "exact",
            ],
        }
