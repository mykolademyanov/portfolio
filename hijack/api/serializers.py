from rest_framework import serializers
from authentication.models import User


class HijackUserSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
