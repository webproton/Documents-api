from rest_framework import serializers


class MessageSerializer(serializers.Serializer):
    """Generic response shape for {"message": "..."}."""

    message = serializers.CharField()
