from rest_framework.routers import DefaultRouter

from poi.api.location_types import LocationTypeViewSet
from poi.api.locations import LocationViewSet
from poi.api.location_history import LocationHistoryViewSet

router = DefaultRouter()
router.register(r"locations", LocationViewSet, basename="location")
router.register(r"location-types", LocationTypeViewSet, basename="types")
router.register(r"location-history", LocationHistoryViewSet, basename="history")

urlpatterns = [
    # path(
    #     "company/",
    #     CompanyMaintenanceListApiView.as_view(),
    #     name="company-maintenance",
    # ),
]
