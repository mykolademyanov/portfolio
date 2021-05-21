from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework_gis.filters import InBBoxFilter

from core.local import local_state
from poi import models
from poi.api import serializers
from poi.api.filters import LocationFilter, LocationHistoryFilter
from utils.dates import days_into_hours
from vehicle.models import Vehicle
from telemetry.api.filters import VehicleStateActiveDaysFilter
from tracker.models import VehicleState


class LocationViewSet(ModelViewSet):
    serializer_class = serializers.LocationSerializer
    bbox_filter_field = "area"
    filter_backends = (
        InBBoxFilter,
        DjangoFilterBackend,
    )
    bbox_filter_include_overlapping = True
    filter_class = LocationFilter

    def get_queryset(self):
        return models.Location.objects.for_customer(
            local_state.customer
        ).order_by("name")

    def perform_create(self, serializer):
        serializer.save(fc_owner=local_state.customer)

    @staticmethod
    def _filter_qs_by_params(params, qs):
        return LocationHistoryFilter(params, queryset=qs).qs

    def _filter_location_history(self, params, request):
        l_history = models.LocationHistory.objects.for_customer(
            local_state.customer
        ).filter(**params)
        return self._filter_qs_by_params(request.GET, l_history)

    @staticmethod
    def _filter_vehicle_state(lh_qs, params):
        vehicles = lh_qs.values_list("vehicle", flat=True)
        vs_qs = VehicleState.objects.filter(vehicle__in=vehicles)
        return VehicleStateActiveDaysFilter(params, queryset=vs_qs).qs

    @staticmethod
    def _prepare_history_context(l_history, request):
        return {"l_history": l_history, "params": request.GET}

    def _loc_vehicle_serializer(self, data, l_history, request):
        return serializers.LocationVehicleSerializer(
            data,
            many=True,
            context=self._prepare_history_context(l_history, request),
        )

    @action(detail=True)
    def histogram(self, request, pk=None):
        lower_qp_name = "duration__range_lower"
        upper_qp_name = "duration__range_upper"
        lower = request.GET.get(lower_qp_name)
        upper = request.GET.get(upper_qp_name)

        # Filter QS
        l_history = self._filter_location_history({"location": pk}, request)
        hours = days_into_hours(lower, upper)
        response = {}

        for hour in hours:
            start = hour["start_datetime"]
            end = hour["end_datetime"]
            params = {lower_qp_name: start, upper_qp_name: end}
            hour_qs = self._filter_qs_by_params(params, l_history)
            vs_hour_qs = self._filter_vehicle_state(hour_qs, params)
            _vs_duration = VehicleState.count_states_duration(
                vs_hour_qs, start, end
            )

            response[hour["start"]] = {
                "entered": hour_qs.entered(start, end).count(),
                "inside": hour_qs.count(),
                "exited": hour_qs.exited(start, end).count(),
                "traveling": _vs_duration["traveling"],
                "idling": _vs_duration["idling"],
                "stopped": _vs_duration["stopped"],
                "towed": _vs_duration["towed"],
                "total": _vs_duration["total"],
            }

        return Response(response)

    @action(detail=True)
    def vehicles(self, request, pk=None):
        # Filter QS
        l_history = self._filter_location_history({"location": pk}, request)
        data = Vehicle.objects.filter(id__in=l_history.values("vehicle_id"))

        # Paginate QS
        page = self.paginate_queryset(data)
        if page is not None:
            serializer = self._loc_vehicle_serializer(page, l_history, request)
            return self.get_paginated_response(serializer.data)

        serializer = self._loc_vehicle_serializer(data, l_history, request)
        return Response(serializer.data)

    @action(detail=True, url_path="vehicles/(?P<vehicle_pk>[0-9]+)")
    def get_vehicle(self, request, pk=None, vehicle_pk=None):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_pk)
        # Filter QS
        l_history = self._filter_location_history(
            {"location": pk, "vehicle": vehicle_pk}, request
        )
        serializer = serializers.LocationVehicleDetailsSerializer(
            {"vehicle": vehicle, "location_history": l_history},
            context=self._prepare_history_context(l_history, request),
        )
        return Response(serializer.data)
