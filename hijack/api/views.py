import time

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework_jwt.serializers import (
    jwt_payload_handler,
    jwt_encode_handler,
)

from api.permissions import IsSuperUser
from hijack.api.serializers import HijackUserSerializer
from authentication.models import User


class HijackUserView(GenericAPIView):
    queryset = User.objects.all()
    serializer_class = HijackUserSerializer
    permission_classes = (IsSuperUser | IsAdminUser,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_payload = jwt_payload_handler(
            user=serializer.validated_data["user"],
            hijacked_by=self.request.user,
        )
        new_payload["orig_iat"] = time.time()

        return Response(
            {"token": jwt_encode_handler(new_payload)},
            status=status.HTTP_201_CREATED,
        )
