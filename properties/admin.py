from django.contrib import admin
from django.contrib.gis.db import models
from django.template.loader import get_template
from mapwidgets.widgets import GooglePointFieldWidget
from django.conf import settings

from pgr_django.properties.forms import PropertyForm
from pgr_django.properties.models import (
    Property,
    PropertyPhoto,
    PropertyFile,
    PropertyDescTranslation,
    ScrapedPropertiesFile,
)
from pgr_django.users.constants import (
    USER_GROUP_AGENTS,
    USER_GROUP_BROKERS,
    USER_GROUP_CRM_ADMINS
)
from pgr_django.users.models import Agent
from pgr_django.utils.google_geocoding import (
    GoogleGeocoding,
    GoogleGeocodingException
)
from pgr_django.utils.google_street_view import (
    GoogleStreetView,
    GoogleStreetViewException
)
from .admin_filters import (
    PropertyHasAgentAdminFilter,
    PropertyFeaturedAdminFilter,
)


class PropertyPhotoInline(admin.TabularInline):
    model = PropertyPhoto

    fields = ("showphoto_thumbnail",)
    readonly_fields = ("showphoto_thumbnail",)
    max_num = 0

    def showphoto_thumbnail(self, instance):
        tpl = get_template("properties/show_thumbnail.html")
        return tpl.render({"photo": instance.photo})

    showphoto_thumbnail.short_description = "Thumbnail"


class PropertyFileInline(admin.TabularInline):
    model = PropertyFile

    fields = ("file", )


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    actions = ["silent_delete", "delete_scraped_only"]
    change_form_template = "admin/property_change_form.html"
    form = PropertyForm
    list_display = ["full_address", "status", "price", "get_agent"]
    search_fields = ["country", "region", "city", "zip_code", "street"]
    list_filter = [
        "status", PropertyHasAgentAdminFilter, "country", "free_marketing",
        PropertyFeaturedAdminFilter,
    ]
    autocomplete_fields = ["agent"]
    ordering = ["-created_at"]

    formfield_overrides = {
        models.PointField: {
            "widget": GooglePointFieldWidget
        }
    }

    fieldsets = (
        (
            None,
            {
                "fields":
                    (
                        "property_type", "price",
                        "price_min", "price_max",
                        "property_subtype", "monthly_hoa_fee",
                        "monthly_hoa_fee_min", "monthly_hoa_fee_max",
                        "status", "beds",
                        "beds_min", "beds_max",
                        "country", "baths",
                        "baths_min", "baths_max",
                        "region", "size",
                        "city", "lot_size",
                        'building_area', 'parking_space',
                        "district", "build_year",
                        "street", "amenities",
                        "zip_code", "tenancy",
                        "description_language", "description",
                        "location", "agent",
                        "photos", "buy_rent",
                        "grm", "cap_rate",
                        "website_link", "live_tour_link",
                        "subscription", "free_marketing",
                        "priority", "scraped",
                        "featured",
                    )
            }
        ),
    )

    class Media:
            css = {
                "all": ("css/custom_admin.css", )
            }

    inlines = [PropertyPhotoInline, PropertyFileInline]

    def silent_delete(self, request, queryset):
        queryset.delete()

    def delete_scraped_only(self, request, queryset):
        queryset = queryset.filter(scraped=True)
        while queryset.exists():
            ids = queryset[:25000].values_list("id", flat=True)
            queryset.filter(id__in=ids).delete()

    def get_agent(self, obj):
        return obj.agent

    get_agent.short_description = "Agent"
    get_agent.admin_order_field = "agent__agent_name"

    @staticmethod
    def __get_user_group(request):
        user_group = request.user.groups.filter(
            name__in=["Agents", "Brokers", "CRM_Admins"]).first()

        if user_group:
            return user_group.name

        return None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user_group = self.__get_user_group(request)
        if request.user.is_superuser or user_group == USER_GROUP_CRM_ADMINS:
            return qs
        else:
            if user_group == USER_GROUP_BROKERS:
                agents_pks = [
                    agent.pk for agent in Agent.objects.filter(
                        broker__user__id=request.user.pk)
                ]
                return qs.filter(agent__id__in=agents_pks)
            elif user_group == USER_GROUP_AGENTS:
                return qs.filter(agent__user__id=request.user.pk)

        return Property.objects.none()

    def get_form(self, request, obj=None, **kwargs):
        user_group = self.__get_user_group(request)
        if request.user.is_superuser or user_group == USER_GROUP_CRM_ADMINS:
            kwargs["form"] = PropertyForm
        else:
            if user_group == USER_GROUP_BROKERS:
                empty_choice = [(None, "-----")]
                _choices = empty_choice + [
                    (agent.pk, agent) for agent in Agent.objects.filter(
                        broker__user__id=request.user.pk)
                ]
                form = super().get_form(request, obj, **kwargs)
                form.base_fields["agent"].choices = _choices
                kwargs["form"] = form
            elif user_group == USER_GROUP_AGENTS:
                fields_list = list(self.fieldsets[0][1]["fields"])
                if "agent" in fields_list:
                    fields_list.remove("agent")
                self.fieldsets[0][1]["fields"] = tuple(fields_list)
                kwargs["form"] = PropertyForm

        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.agent:
            try:
                agent = Agent.objects.get(user__pk=request.user.pk)
                obj.agent = agent
            except (Agent.DoesNotExist, KeyError):
                pass

        address_fields = ["country", "region", "city",
                          "district", "zip_code", "street"]
        reverse = True
        for changed_field in form.changed_data:
            if changed_field in address_fields:
                reverse = False
                break

        # check it this property has raw initial address values,
        # if so - also try to geolocate by address instead of lat, lng pair
        # because for every raw initialized property these values are 0.0, 0.0,
        # which makes GoogleGeocoding flush all the address values upon the first save
        if reverse and obj.location.x == 0.0 and obj.location.y == 0.0:
            reverse = False

        # dirty hack for production
        if settings.WORKING_ENV == 'prod':
            obj.location.x, obj.location.y = obj.location.y, obj.location.x

        try:
            gg = GoogleGeocoding(obj, reverse=reverse)
            gg.save_geocoding_data()
        except GoogleGeocodingException:
            pass

        # address has been changed, we have to look for a new picture in google street view
        if not reverse or 'location' in form.changed_data:
            try:
                gs = GoogleStreetView(property_obj=obj, google_geocoding_obj=gg)
                gs.save_property_street_view_photo()
            except GoogleStreetViewException:
                pass

        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.save_photos(form.instance)


@admin.register(PropertyDescTranslation)
class PropertyDescTranslationAdmin(admin.ModelAdmin):
    list_display = "description_text",
    search_fields = "description_text",


@admin.register(ScrapedPropertiesFile)
class ScrapedPropertiesFileAdmin(admin.ModelAdmin):
    pass
