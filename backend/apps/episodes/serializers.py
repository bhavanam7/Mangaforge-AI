from rest_framework import serializers

from .models import Episode


class EpisodeSerializer(serializers.ModelSerializer):
    project = serializers.UUIDField(source="project_id", read_only=True)

    class Meta:
        model = Episode
        fields = ("id", "project", "title", "summary", "episode_number", "status", "created_at", "updated_at")
        read_only_fields = ("id", "project", "created_at", "updated_at")

    def validate_episode_number(self, value):
        project = self.instance.project if self.instance else self.context.get("project")
        if project and Episode.objects.filter(project=project, episode_number=value, is_deleted=False).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("This episode number is already used in the project.")
        return value
