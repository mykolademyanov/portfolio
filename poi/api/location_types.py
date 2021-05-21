from rest_framework.viewsets import ModelViewSet

from core.local import local_state
from poi import models
from poi.api import serializers


class LocationTypeViewSet(ModelViewSet):
    serializer_class = serializers.LocationTypeSerializer

    def get_queryset(self):
        return models.LocationType.objects.for_customer(
            local_state.customer
        ).order_by("name")

    def perform_create(self, serializer):
        serializer.save(customer=local_state.customer, system=False)
