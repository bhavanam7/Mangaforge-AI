import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Project(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cover_image = models.FileField(upload_to="project_covers/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("owner", "is_deleted")),
            models.Index(fields=("status", "is_deleted")),
        ]

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=("is_deleted", "deleted_at", "updated_at"))

    def __str__(self):
        return self.title


class StorySession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        FINALIZED = "finalized", "Finalized"

    class Stage(models.TextChoices):
        PROMPT_EVAL = "PROMPT_EVAL", "Prompt Evaluation"
        ENRICHED_CONTENT = "ENRICHED_CONTENT", "Enriched Content Generation"
        JSON_GENERATION = "JSON_GENERATION", "JSON Entity Extraction"
        CHARACTER_ENHANCEMENT = "CHARACTER_ENHANCEMENT", "Character Enhancement"
        BACKGROUND_ENHANCEMENT = "BACKGROUND_ENHANCEMENT", "Background Enhancement"
        SCENE_DIALOGUE_ENHANCEMENT = "SCENE_DIALOGUE_ENHANCEMENT", "Scene & Dialogue Enhancement"
        FINALIZED = "FINALIZED", "Finalized"

    # Stage transition lookup matrix to validate workflow progress
    ALLOWED_TRANSITIONS = {
        Stage.PROMPT_EVAL: [Stage.PROMPT_EVAL, Stage.ENRICHED_CONTENT],
        Stage.ENRICHED_CONTENT: [Stage.ENRICHED_CONTENT, Stage.JSON_GENERATION],
        Stage.JSON_GENERATION: [Stage.CHARACTER_ENHANCEMENT],
        Stage.CHARACTER_ENHANCEMENT: [Stage.CHARACTER_ENHANCEMENT, Stage.BACKGROUND_ENHANCEMENT],
        Stage.BACKGROUND_ENHANCEMENT: [Stage.BACKGROUND_ENHANCEMENT, Stage.SCENE_DIALOGUE_ENHANCEMENT],
        Stage.SCENE_DIALOGUE_ENHANCEMENT: [Stage.SCENE_DIALOGUE_ENHANCEMENT, Stage.FINALIZED],
        Stage.FINALIZED: [],
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="story_session")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_sessions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    
    # State tracking & content persistence fields
    stage = models.CharField(max_length=40, choices=Stage.choices, default=Stage.PROMPT_EVAL)
    enriched_content = models.TextField(default="", blank=True)
    json_output = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def transition_to(self, new_stage: str):
        if new_stage not in self.ALLOWED_TRANSITIONS.get(self.stage, []):
            raise ValueError(f"Invalid state transition from '{self.stage}' to '{new_stage}'")
        self.stage = new_stage

    def __str__(self):
        return f"Story session: {self.project.title} ({self.stage})"


class StoryMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(StorySession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("session", "created_at"))]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"