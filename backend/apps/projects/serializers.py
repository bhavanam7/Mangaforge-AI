from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    owner = serializers.UUIDField(source="owner_id", read_only=True)

    class Meta:
        model = Project
        fields = ("id", "owner", "title", "description", "cover_image", "status", "created_at", "updated_at")
        read_only_fields = ("id", "owner", "created_at", "updated_at")
