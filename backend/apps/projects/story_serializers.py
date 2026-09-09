from rest_framework import serializers

from .models import StoryMessage, StorySession


class StoryMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoryMessage
        fields = ("id", "role", "content", "created_at")
        read_only_fields = ("id", "role", "created_at")


class StorySessionSerializer(serializers.ModelSerializer):
    messages = StoryMessageSerializer(many=True, read_only=True)

    class Meta:
        model = StorySession
        fields = ("id", "project", "status", "created_at", "updated_at", "messages")
        read_only_fields = fields
