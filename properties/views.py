import logging
import typing as t
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.db.models import (
    Q,
    Subquery,
    Prefetch
)
from django.db.models.query import QuerySet
from django.db.utils import IntegrityError
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from django.contrib.gis.geos import fromstr, Polygon
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.filters import OrderingFilter
from rest_framework.generics import ListAPIView, get_object_or_404, CreateAPIView
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.parsers import (
    FormParser,
    MultiPartParser,
)
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import (
    GenericViewSet,
    ModelViewSet,
)

from pgr_django.users.models import Agent
from pgr_django.payments.models import PromoCode
from pgr_django.users.permissions import UserIsAgentOrBroker
from pgr_django.utils.drf_paginators import DefaultPagination, PropertiesPagination
from pgr_django.utils.google_translate import GoogleTranslate
from pgr_django.utils.stripe import Stripe
from .constants import (
    STATUS_DELETED,
    TYPE_SUBTYPE_MAP,
    STATUS_INACTIVE,
    STATUS_ACTIVE
)
from .filters import (
    PropertySearchFilterBackend,
    PropertySearchMyPropertiesFilterBackend,
)
from .models import (
    Property,
    PropertyPhoto,
    PropertyFile,
    UserSavedProperty,
)
from .permissions import (
    AlwaysDenyPermission,
    UserIsPropertyAgentOrBroker,
    UserIsPropertyPhotoAgentOrBroker,
)
from .serializers import (
    PropertyDetailSerializer,
    PropertyInsertUpdateSerializer,
    PropertyListSerializer,
    PropertyPhotoSerializer,
    PropertyPhotoUploadSerializer,
    PropertyFileSerializer,
    PropertyFileUploadSerializer,
    PropertySearchSerializer,
    PropertySearchMyPropertiesSerializer,
    UserSavedPropertySerializer,
    UserSavedPropertyPostSerializer,
    PropertiesFileUploadSerializer,
    PropertiesFileUpdateRentSerializer,
    PropertyLocationSerializer,
    PropertyLowDetailedSerializer,
)

logger = logging.getLogger(__name__)
SEARCH_RADIUS = 0.02


class PropertyConflictCreating(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = {
        'non_field_errors': _('Conflicting properties with the same exact address exist.'), 'objs': []
    }
    default_code = 'error'


class PropertyTypeSubtypeDoNotMap(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = {'non_field_errors': _('Property type and subtype do not match.')}
    default_code = 'error'


class PropertySearchAPIView(ListAPIView):
    pagination_class = DefaultPagination
    permission_classes = [AllowAny]
    queryset = Property.objects.prefetch_related('photos')
    serializer_class = PropertySearchSerializer
    filter_backends = (PropertySearchFilterBackend, OrderingFilter)
    ordering_fields = ['priority', 'status', 'id', 'price', 'price_max', 'price_avg', 'updated_at']
    ordering = ['status']

    @staticmethod
    def set_agents(page):
        """
        Manually load and set agents to optimize query time.
        """
        default_agent = Agent.default_agent()
        agent_ids = [property.agent_id for property in page]
        agents = {
            agent.id: agent
            for agent in Agent.objects.filter(id__in=agent_ids).select_related('broker')
        }
        for property in page:
            property.agent = agents.get(property.agent_id, default_agent)
        return page

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        page = self.set_agents(page)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @method_decorator(cache_page(60))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


properties_search_view = PropertySearchAPIView.as_view()


class PropertySearchMyPropertiesAPIView(ListAPIView):
    queryset = Property.objects.select_related(
        'agent', 'agent__user', 'agent__broker', 'payment', 'description_translation'
    ).prefetch_related('photos')
    permission_classes = [UserIsAgentOrBroker]
    serializer_class = PropertySearchMyPropertiesSerializer
    filter_backends = (PropertySearchMyPropertiesFilterBackend, OrderingFilter)
    ordering_fields = ['status', 'id', 'price_avg', 'price', 'size', 'baths', 'beds', 'build_year']
    ordering = ['status']

    def check_promocodes(self):
        codes = PromoCode.objects.filter(user=self.request.user, active=True)
        for code in codes:
            expiration_date = code.created + relativedelta(months=code.coupon.duration_in_months)
            if datetime.today().date() > expiration_date.date():
                code.active = False
                code.save()

    def get_queryset(self):
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.all()
        self.check_promocodes()
        agent = self.request.user.agent
        if agent.broker:
            agent_and_same_broker_agents = Agent.objects.filter(
                Q(id=agent.id) | Q(broker=agent.broker)
            )
            return queryset.filter(agent_id__in=Subquery(agent_and_same_broker_agents.values('id')))
        else:
            return queryset.filter(agent_id=agent.id)


properties_search_my_properties_view = PropertySearchMyPropertiesAPIView.as_view()


class PropertyListViewSet(ListModelMixin, GenericViewSet):
    queryset = Property.objects.select_related('agent').prefetch_related('photos')
    pagination_class = DefaultPagination
    serializer_class = PropertyListSerializer
    permission_classes = [AllowAny]
    filter_backends = (OrderingFilter,)
    ordering = ['pk']

    @method_decorator(cache_page(60))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


properties_list_view = PropertyListViewSet.as_view({'get': 'list'})

property_iou_permissions = {
    'create': [UserIsAgentOrBroker],
    'update': [UserIsAgentOrBroker, UserIsPropertyAgentOrBroker],
    'partial_update': [UserIsAgentOrBroker, UserIsPropertyAgentOrBroker],
}


class PropertyImportUpdateViewSet(CreateModelMixin, UpdateModelMixin, GenericViewSet):
    queryset = Property.objects.all()
    serializer_class = PropertyInsertUpdateSerializer
    response_serializer_class = PropertyDetailSerializer
    ordering = ['pk']

    def check_type_subtype_map(self, instance: t.Optional[Property],
                               property_type: str,
                               property_subtype: str) -> None:
        property_type = property_type or instance.property_type
        property_subtype = property_subtype or instance.property_subtype
        if property_subtype not in TYPE_SUBTYPE_MAP.get(property_type):
            raise PropertyTypeSubtypeDoNotMap()

    def get_permissions(self):
        permission_classes = property_iou_permissions.get(self.action, [AlwaysDenyPermission])
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        data = serializer.validated_data
        self.check_type_subtype_map(
            instance=None,
            property_type=data.get('property_type', None),
            property_subtype=data.get('property_subtype', None)
        )
        saved_instance = serializer.save()

        return saved_instance

    def perform_update(self, serializer):
        data = serializer.validated_data
        instance = self.get_object()  # type: Property
        if instance.subscription:
            if instance.status == STATUS_ACTIVE and data.get('status') == STATUS_INACTIVE:
                stripe = Stripe()
                stripe.deactivate_property_subscription(instance)
            elif instance.status == STATUS_INACTIVE and data.get('status') == STATUS_ACTIVE:
                stripe = Stripe()
                stripe.activate_property_subscription(instance)
            elif instance.status in [STATUS_ACTIVE, STATUS_INACTIVE] and data.get('status') == STATUS_DELETED:
                stripe = Stripe()
                stripe.deactivate_property_subscription(instance)

        self.check_type_subtype_map(
            instance=instance,
            property_type=data.get('property_type', None),
            property_subtype=data.get('property_subtype', None)
        )
        serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        saved_instance = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        p = GoogleTranslate(obj_for_translation=saved_instance)
        p.save_translation()
        response_serializer = self.response_serializer_class(saved_instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        p = GoogleTranslate(obj_for_translation=instance)
        p.save_translation()
        response_serializer = self.response_serializer_class(instance)
        return Response(response_serializer.data)


properties_create_view = PropertyImportUpdateViewSet.as_view({'post': 'create'})
properties_update_view = PropertyImportUpdateViewSet.as_view({'put': 'update'})
properties_partial_update_view = PropertyImportUpdateViewSet.as_view({'patch': 'partial_update'})


class PropertiesTypeSubtypeGETView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # As for now, there's not straight answer either we should fetch this from DB
        # or if the fixed/static constant approach is enough.
        return Response(TYPE_SUBTYPE_MAP)


properties_type_subtype_get_view = PropertiesTypeSubtypeGETView.as_view()

property_media_attachment_permissions = {
    'list': [AllowAny],
    'retrieve': [AllowAny],
    'destroy': [UserIsAgentOrBroker, UserIsPropertyPhotoAgentOrBroker],
    'partial_update': [UserIsAgentOrBroker, UserIsPropertyPhotoAgentOrBroker]
}


class PropertyMediaAttachmentViewSet(
    RetrieveModelMixin, ListModelMixin, DestroyModelMixin, UpdateModelMixin,
    GenericViewSet
):
    filter_backends = (OrderingFilter,)
    ordering_fields = ['id', 'created_at', 'order']
    ordering = ['order']

    def get_queryset(self):
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.all()
        return queryset.filter(property_id=self.kwargs['property_id'])

    def get_permissions(self):
        permission_classes = property_media_attachment_permissions.get(
            self.action, [AlwaysDenyPermission]
        )
        return [permission() for permission in permission_classes]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PropertyPhotoViewSet(PropertyMediaAttachmentViewSet):
    queryset = PropertyPhoto.objects.all()
    serializer_class = PropertyPhotoSerializer

    def perform_destroy(self, instance):
        instance.photo.delete(save=False)
        instance.delete()


property_photo_list_view = PropertyPhotoViewSet.as_view({'get': 'list'})
property_photo_detail_get_delete_view = PropertyPhotoViewSet.as_view({
    'get': 'retrieve',
    'delete': 'destroy'
})
property_photo_detail_patch_view = PropertyPhotoViewSet.as_view({
    'patch': 'partial_update'
})


class PropertyFileViewSet(PropertyMediaAttachmentViewSet):
    queryset = PropertyFile.objects.all()
    serializer_class = PropertyFileSerializer

    def perform_destroy(self, instance):
        instance.file.delete(save=False)
        instance.delete()


property_file_list_view = PropertyFileViewSet.as_view({'get': 'list'})
property_file_detail_get_delete_view = PropertyFileViewSet.as_view({
    'get': 'retrieve',
    'delete': 'destroy'
})
property_file_detail_patch_view = PropertyFileViewSet.as_view({
    'patch': 'partial_update'
})


class PropertyMediaAttachmentUploadView(CreateModelMixin, GenericViewSet):
    # MultiPartParser AND FormParser
    # https://www.django-rest-framework.org/api-guide/parsers/#multipartparser
    # "You will typically want to use both FormParser and MultiPartParser
    # together in order to fully support HTML form data."
    permission_classes = [UserIsAgentOrBroker, UserIsPropertyAgentOrBroker]
    parser_classes = [MultiPartParser, FormParser]
    queryset = Property.objects.all()
    lookup_url_kwarg = 'property_id'

    def create(self, request, *args, **kwargs):
        _property = self.get_object()  # needed to trigger permission's check
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attachment_instance = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        response_serializer = self.response_serializer_class(
            attachment_instance
        )

        return Response(
            response_serializer.data,status=status.HTTP_201_CREATED,
            headers=headers
        )

    def perform_create(self, serializer) -> PropertyPhoto:
        return serializer.save(property_id=self.kwargs['property_id'])


class PropertyPhotoUploadView(PropertyMediaAttachmentUploadView):
    serializer_class = PropertyPhotoUploadSerializer
    response_serializer_class = PropertyPhotoSerializer


property_photo_upload_view = PropertyPhotoUploadView.as_view({"post": "create"})


class PropertyFileUploadView(PropertyMediaAttachmentUploadView):
    serializer_class = PropertyFileUploadSerializer
    response_serializer_class = PropertyFileSerializer


property_file_upload_view = PropertyFileUploadView.as_view({"post": "create"})


class PropertiesCountAPIView(APIView):
    permission_classes = [AllowAny]
    queryset = Property.objects.exclude(
        status=STATUS_DELETED
    )

    def get_queryset(self):
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.all()
        return queryset

    @method_decorator(cache_page(60 * 60))  # 1h cache
    def get(self, request):
        count = self.get_queryset().count()
        return Response({'total': count})


properties_count_view = PropertiesCountAPIView.as_view()


class PropertyDetailViewSet(RetrieveModelMixin, GenericViewSet):
    queryset = Property.objects.select_related(
        'agent', 'agent__user', 'agent__broker', 'description_translation',
    ).prefetch_related(
        Prefetch('photos', queryset=PropertyPhoto.objects.order_by('order')),
        Prefetch('files', queryset=PropertyFile.objects.order_by('order')),
    )
    serializer_class = PropertyDetailSerializer
    permission_classes = [AllowAny]

    @method_decorator(cache_page(60))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


properties_detail_view = PropertyDetailViewSet.as_view({'get': 'retrieve'})


class UserSavedPropertyView(ModelViewSet):
    queryset = UserSavedProperty.objects.select_related('property')
    serializer_class = UserSavedPropertySerializer
    post_serializer_class = UserSavedPropertyPostSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = (OrderingFilter,)
    ordering_fields = ['id', 'created_at', 'last_status']
    ordering = ['pk']
    lookup_field = 'property_id'

    def get_queryset(self):
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.all()
        return queryset.filter(user_id=self.request.user.id)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        return obj

    def create(self, request, *args, **kwargs):
        serializer = self.post_serializer_class(data=request.data, context={"user_id": self.request.user.id})
        serializer.is_valid(raise_exception=True)
        try:
            instance = self.perform_create(serializer)
        except IntegrityError:
            return Response({'err': "duplicate"}, status=status.HTTP_409_CONFLICT)

        headers = self.get_success_headers(serializer.data)
        response_serializer = self.get_serializer(instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        return serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        property_updated_at = instance.property.updated_at
        property_status = instance.property.status
        serializer.save(
            last_status=property_status,
            last_updated_at=property_updated_at
        )


user_saved_properties_list = UserSavedPropertyView.as_view({
    'get': 'list',
    'post': 'create'
})
user_saved_properties_detail = UserSavedPropertyView.as_view({
    'get': 'retrieve',
    'delete': 'destroy',
    'patch': 'partial_update'
})


class PropertiesFileUploadView(CreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = PropertiesFileUploadSerializer


properties_file_upload_view = PropertiesFileUploadView.as_view()


class PropertiesFileUpdateRentView(CreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = PropertiesFileUpdateRentSerializer


properties_file_update_rent_view = PropertiesFileUpdateRentView.as_view()


class FeaturedPropertiesListView(ListModelMixin, GenericViewSet):
    serializer_class = PropertySearchSerializer
    queryset = Property.objects.filter(status=STATUS_ACTIVE).exclude(featured=None).order_by('-featured')
    permission_classes = [AllowAny]

    @method_decorator(cache_page(60*5))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


featured_properties_list_view = FeaturedPropertiesListView.as_view({
    'get': 'list'
})


class PropertiesAddressSearchView(ListModelMixin, GenericViewSet):
    serializer_class = PropertyLocationSerializer
    permission_classes = [AllowAny]
    queryset = Property.objects.all()
    pagination_class = PropertiesPagination

    def list(self, request, *args, **kwargs):
        query_params = request.query_params
        point = fromstr(query_params.get('location'), srid=4326)
        radius = query_params.get('radius') or SEARCH_RADIUS
        circle = point.buffer(float(radius))

        queryset = Property.objects.filter(
            location__within=circle,
            status=STATUS_ACTIVE
        ).values("id", "location")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


properties_address_search_view = PropertiesAddressSearchView.as_view({
    'get': 'list'
})


class PropertiesAreaSearch(ListModelMixin, GenericViewSet):
    serializer_class = PropertyLocationSerializer
    permission_classes = [AllowAny]
    queryset = Property.objects.all()
    pagination_class = PropertiesPagination

    def list(self, request, *args, **kwargs):
        query_params = request.query_params
        points = query_params.get('points')
        if points:
            area = self.create_polygon(query_params.get('points'))
        else:
            point = fromstr(query_params.get('location'), srid=4326)
            radius = query_params.get('radius') or SEARCH_RADIUS
            area = point.buffer(float(radius))

        queryset = Property.objects.filter(
            location__within=area,
            status=query_params.get("status", STATUS_ACTIVE)
        )
        queryset = self.get_filtered_queryset(queryset, query_params).values(
            "id", "location", "status"
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def create_polygon(coordinates) -> Polygon:
        """Takes boundary points with lat, lng and create polygon"""
        splitted_coords = map(float, coordinates.split(', '))
        points = list(splitted_coords)
        points = [(points[i], points[i+1]) for i in range(0, len(points), 2)]
        points.append(points[0])
        return Polygon(points)

    @staticmethod
    def get_filtered_queryset(queryset, query_params):
        buy_rent = query_params.get('buyrent')
        prop_type = query_params.get('type')
        prop_subtype = query_params.get('subtype')

        if buy_rent:
            queryset = queryset.filter(buy_rent=buy_rent)

        if prop_type:
            queryset = queryset.filter(property_type=prop_type)

        if prop_subtype:
            queryset = queryset.filter(property_subtype=prop_subtype)

        return queryset


properties_area_search = PropertiesAreaSearch.as_view({'get': 'list'})


class PropertyLowDetailedView(RetrieveModelMixin, GenericViewSet):
    serializer_class = PropertyLowDetailedSerializer
    permission_classes = [AllowAny]
    queryset = Property.objects.all()

    @method_decorator(cache_page(60*5))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


property_low_detailed_view = PropertyLowDetailedView.as_view(
    {'get': 'retrieve'}
)
