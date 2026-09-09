import uuid

from django.db import models
from django.utils import timezone

from apps.projects.models import Project


class Character(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="characters")
    name = models.CharField(max_length=150)
    surname = models.CharField(max_length=150, blank=True)
    sex = models.CharField(max_length=50, blank=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    height_or_size = models.CharField(max_length=100, blank=True)
    hair_color = models.CharField(max_length=100, blank=True)
    eye_color = models.CharField(max_length=100, blank=True)
    clothing_style = models.CharField(max_length=200, blank=True)
    accessories = models.TextField(blank=True)
    personality = models.TextField(blank=True)
    clothing = models.TextField(blank=True)
    history = models.TextField(blank=True)
    importance = models.CharField(max_length=50, blank=True)
    reference_image = models.FileField(upload_to="character_references/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("project", "is_deleted")),
            models.Index(fields=("name", "is_deleted")),
        ]

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=("is_deleted", "deleted_at", "updated_at"))

    def __str__(self):
        return self.name
