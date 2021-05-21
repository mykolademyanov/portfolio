import logging
from rest_framework import permissions
from rest_framework.exceptions import APIException

from pgr_django.utils.permissions import log_permission_deny
from .models import (
    Property,
    PropertyPhoto,
    UserSavedProperty
)

logger = logging.getLogger(__name__)


class PropertyAgentNotSet(APIException):
    default_detail = 'Property agent is not set'
    default_code = 'error'


class UserIsPropertyAgentOrBroker(permissions.BasePermission):
    """
    Object-level permission to only allow agent or it's broker to edit it.
    Assumes the model instance has an `agent` attribute.
    """

    @log_permission_deny
    def has_object_permission(self, request, view, obj: Property):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not (user or user.is_authenticated):
            return False

        if not obj.agent_id:
            raise PropertyAgentNotSet(detail=f'property id:{obj.id} has no agent assigned')

        user_agent = user.agent
        # Property agent must match user performing action or agent works for same broker
        # warning: if agent will set agent_id from other broker he will lose object IOU permissions!
        return bool(
            obj.agent_id == user.agent.id
            or (obj.agent.broker_id == user.agent.broker_id
                and user.agent.broker_id is not None)
        )


class UserIsPropertyPhotoAgentOrBroker(permissions.BasePermission):
    """
    Object-level permission to only allow agent or it's broker to edit it.
    Assumes the model instance has an `agent` attribute.
    """

    @log_permission_deny
    def has_object_permission(self, request, view, obj: PropertyPhoto):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not (user or user.is_authenticated):
            return False

        if not obj.property.agent_id:
            raise PropertyAgentNotSet(detail=f'property id:{obj.property.id} has no agent assigned')

        user_agent = user.agent
        # Property agent (Property to which PropertyPhoto is attached)
        # must match user performing action or agent works for same broker
        return bool(
            obj.property.agent_id == user.agent.id
            or obj.property.agent.broker_id == user.agent.broker_id
        )


class AlwaysDenyPermission(permissions.BasePermission):
    @log_permission_deny
    def has_permission(self, request, view):
        return False

    @log_permission_deny
    def has_object_permission(self, request, view, obj: PropertyPhoto):
        return False

