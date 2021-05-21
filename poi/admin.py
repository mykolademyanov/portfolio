from django.contrib import admin

# Register your models here.
from leaflet.admin import LeafletGeoAdmin

from accounting.admin import FCOwnerAutocompleteFilter
from admin_auto_filters.filters import AutocompleteFilter
from poi import models
from poi.models import LocationHistory
from vehicle.admin import VehicleAutoCompleteFilter


class LocationAutoCompleteFilter(AutocompleteFilter):
    title = "Location"
    field_name = "location"


@admin.register(models.Location)
class LocationAdmin(LeafletGeoAdmin):
    list_filter = (FCOwnerAutocompleteFilter,)
    search_fields = ("name", "fc_owner__name")
    list_display = ("name", "fc_owner", "created")
    autocomplete_fields = ("fc_owner", "type", "company", "primary_contact")
    fieldsets = (
        (None, {"fields": ("fc_owner", "name", "description")}),
        (
            "Location",
            {
                "fields": (
                    "type",
                    "time_of_operation",
                    (
                        "open_sunday",
                        "open_monday",
                        "open_tuesday",
                        "open_wednesday",
                        "open_thursday",
                        "open_friday",
                        "open_saturday",
                    ),
                    "radius",
                    "max_speed",
                    "area",
                )
            },
        ),
        ("Photo", {"fields": ("photo", ("photo_width", "photo_height"))}),
        ("Contact", {"fields": ("company", "primary_contact")}),
    )


@admin.register(models.LocationType)
class LocationTypeAdmin(admin.ModelAdmin):
    list_filter = ("system",)
    autocomplete_fields = ("customer",)
    search_fields = ("name", "customer")
    list_display = ("name", "customer", "system", "icon")


@admin.register(models.LocationHistory)
class LocationHistoryAdmin(admin.ModelAdmin):
    list_filter = (VehicleAutoCompleteFilter, LocationAutoCompleteFilter)
    autocomplete_fields = ("location", "vehicle")
    list_display = (
        "get_location_name",
        "vehicle_name",
        "ingress",
        "egress",
        "get_duration",
    )

    def get_duration(self, obj: LocationHistory):
        if not obj.duration.upper:
            return "inside"

        if not obj.duration.lower:
            return "Incomplete"

        return obj.duration.upper - obj.duration.lower

    get_duration.short_description = "Duration"

    def get_location_name(self, obj: LocationHistory):
        return obj.location.name

    get_location_name.short_description = "Location"
    get_location_name.admin_order_field = "location__name"

    def vehicle_name(self, obj: LocationHistory):
        return obj.vehicle.identifier

    vehicle_name.short_description = "Vehicle"
    vehicle_name.admin_order_field = "vehicle__name"

    def ingress(self, obj: LocationHistory):
        return obj.duration.lower

    ingress.short_description = "Ingress"
    ingress.admin_order_field = "duration__startswith"

    def egress(self, obj: LocationHistory):
        return obj.duration.upper

    egress.short_description = "Egress"
    egress.admin_order_field = "duration__endswith"
