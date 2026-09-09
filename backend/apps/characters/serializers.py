from rest_framework import serializers

from .models import Character


class CharacterSerializer(serializers.ModelSerializer):
    project = serializers.UUIDField(source="project_id", read_only=True)

    class Meta:
        model = Character
        fields = (
            "id", "project", "name", "surname", "sex", "age", "height_or_size",
            "hair_color", "eye_color", "clothing_style", "accessories", "personality",
            "clothing", "history", "importance", "reference_image", "created_at", "updated_at",
        )
        read_only_fields = ("id", "project", "created_at", "updated_at")
