import typing as t
from django.db.models import F, Case, When, Value, DecimalField
from django.contrib.gis.geos import GEOSGeometry
from django.utils.encoding import force_text
from rest_framework import filters, status
from rest_framework.exceptions import APIException

from .constants import (
    STATUS_PENDING,
    STATUS_INACTIVE,
    STATUS_ACTIVE,
    STATUS_SOLD,
    STATUS_DELETED,
    MULTI_COUNTRY_NAMES,
)


class NoParametersException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Missing search params, use list instead?'


class BadParametersException(APIException):
    def __init__(self, detail, key, status_code):
        if status_code is not None:
            self.status_code = status_code
        if detail is not None:
            self.detail = f'\"{key}\": {force_text(detail)}'
        else:
            self.detail = f'{force_text(self.default_detail)}'


class BBox:
    """bbox=lon1,lat1,lon2,lat2 """

    def __init__(self, bbox: str):
        if not isinstance(bbox, str):
            raise ValueError("missing or invalid bbox input")

        try:
            self.lon1, self.lat1, self.lon2, self.lat2 = [float(x) for x in bbox.split(',')]
        except ValueError as e:
            raise ValueError(str(e))

        # TODO: temporary disable due reversed lat/lon coordinates
        # if not (-180 <= self.lon1 <= 180):
        #     raise ValueError("lon1 out of range")
        #
        # if not (-90 <= self.lat1 <= 90):
        #     raise ValueError("lat1 out of range")
        #
        # if not (-180 <= self.lon2 <= 180):
        #     raise ValueError("lon2 out of range")
        #
        # if not (-90 <= self.lat2 <= 90):
        #     raise ValueError("lat2 out of range")

    def as_linestring(self):
        """In spatial databases spatial coordinates are in x = longitude, and y = latitude."""
        return f"LINESTRING({self.lon1} {self.lat1}, {self.lon2} {self.lat2})"


class BboxGEOSGeometry(GEOSGeometry):
    def __init__(self, bbox: str):
        bbox = BBox(bbox)
        super().__init__(bbox.as_linestring(), srid=4326)


def validate_property_search_statuses(statuses: t.List):
    not_allowed = set(statuses).difference({STATUS_ACTIVE, STATUS_SOLD})
    if not_allowed:
        raise ValueError(f"invalid statuses {','.join(not_allowed)}")


def validate_property_search_my_statuses(statuses: t.List):
    not_allowed = set(statuses).difference({
        STATUS_PENDING,
        STATUS_ACTIVE,
        STATUS_SOLD,
        STATUS_DELETED,
        STATUS_INACTIVE
    })
    if not_allowed:
        raise ValueError(f"invalid statuses {not_allowed}")


BASE_SEARCH_FILTERS = {
    # type, type, Q, validator
    'countries': (list, str, 'country__upper__in', None),
    'cities': (list, str, 'city__upper__in', None),
    'postalCodes': (list, str, 'zip_code__in', None),
    'type': (list, str, 'property_type__in', None),
    'subtype': (list, str, 'property_subtype__in', None),
    'buyrent': (str, None, 'buy_rent__exact', None),
    'minprice': (float, None, 'price_avg__gte', None),
    'maxprice': (float, None, 'price_avg__lte', None),
    'minarea': (float, None, 'size__gte', None),
    'maxarea': (float, None, 'size__lte', None),
    'minbaths': (int, None, 'baths__gte', None),
    'maxbaths': (int, None, 'baths__lte', None),
    'minbeds': (int, None, 'beds__gte', None),
    'maxbeds': (int, None, 'beds__lte', None),
    'minyear': (int, None, 'build_year__gte', None),
    'maxyear': (int, None, 'build_year__lte', None),
    'bbox': (BboxGEOSGeometry, None, 'location__bboverlaps', None),
    'agent': (int, None, 'agent_id', None),
    'properties': (list, int, 'id__in', None),
}

SEARCH_FILTERS = BASE_SEARCH_FILTERS.copy()
SEARCH_FILTERS['status'] = (
    list, str, 'status__in', validate_property_search_statuses
)

SEARCH_MY_PROPERTIES_FILTERS = BASE_SEARCH_FILTERS.copy()
SEARCH_MY_PROPERTIES_FILTERS['status'] = (
    list, str, 'status__in', validate_property_search_my_statuses
)


class PropertySearchFilterBackend(filters.BaseFilterBackend):
    """
    Filter properties by fixed fields.
    """
    default_status_filter = {STATUS_ACTIVE}
    require_filters = True  # status filter excluded
    type_conversion = SEARCH_FILTERS

    def filter_queryset(self, request, queryset, view):
        queryset = queryset.annotate(
            price_avg=Case(
                When(
                    price_min__isnull=False,
                    price_max__isnull=False,
                    then=(F('price_min') + F('price_max')) / 2
                ),
                When(
                    price__isnull=False,
                    then=F('price')
                ),
                default=Value(0),
                output_field=DecimalField()
            )
        )
        filters_applied = False
        query_params = request.GET.dict().copy()
        if 'countries' in query_params:
            countries = query_params['countries']
            query_params['countries'] = MULTI_COUNTRY_NAMES.get(
                countries, countries
            )

        if 'status' not in query_params and self.default_status_filter:
            query_params['status'] = self.default_status_filter

        for key, value in query_params.items():
            field_def = self.type_conversion.get(key, None)
            if not field_def:
                continue
            main_type, secondary_type, drf_search_field, validator = field_def
            if main_type is list:
                if not isinstance(value, (list, set)):
                    split_vals = value.split(',')
                else:
                    split_vals = value
                try:
                    if '__upper' in drf_search_field:
                        search_val = [secondary_type(val).upper() for val in split_vals]
                    else:
                        search_val = [secondary_type(val) for val in split_vals]
                    if validator:
                        validator(search_val)
                except ValueError as e:
                    raise BadParametersException(f'Invalid parameter type in list: {str(e)}', key,
                                                 status_code=status.HTTP_400_BAD_REQUEST)
            else:
                try:
                    search_val = main_type(value)
                    if validator:
                        validator(search_val)
                except ValueError as e:
                    raise BadParametersException(f'Invalid parameter type: {str(e)}', key,
                                                 status_code=status.HTTP_400_BAD_REQUEST)
            if key != 'status':
                filters_applied = filters_applied or True

            queryset = queryset.filter(**{drf_search_field: search_val})

        if self.require_filters and not filters_applied:
            raise NoParametersException()

        return queryset


class PropertySearchMyPropertiesFilterBackend(PropertySearchFilterBackend):
    default_status_filter = None
    require_filters = False
    type_conversion = SEARCH_MY_PROPERTIES_FILTERS
