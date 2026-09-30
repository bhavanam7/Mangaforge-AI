import uuid

from django.db import models
from django.utils import timezone

from apps.projects.models import Project


class Episode(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="episodes")
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    episode_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("episode_number", "created_at")
        constraints = [
            models.UniqueConstraint(fields=("project", "episode_number"), condition=models.Q(is_deleted=False), name="unique_active_episode_order"),
        ]
        indexes = [
            models.Index(fields=("project", "is_deleted")),
            models.Index(fields=("project", "episode_number")),
        ]

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=("is_deleted", "deleted_at", "updated_at"))

    def __str__(self):
        return f"Episode {self.episode_number}: {self.title}"
