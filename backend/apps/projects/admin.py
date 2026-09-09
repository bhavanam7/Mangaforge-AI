from django.contrib import admin

from .models import Project, StoryMessage, StorySession


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "is_deleted", "created_at", "updated_at")
    list_filter = ("status", "is_deleted")
    search_fields = ("title", "description", "owner__email", "owner__name")
    readonly_fields = ("id", "created_at", "updated_at", "deleted_at")


@admin.register(StorySession)
class StorySessionAdmin(admin.ModelAdmin):
    list_display = ("project", "owner", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("project__title", "owner__email")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StoryMessage)
class StoryMessageAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("content", "session__project__title")
    readonly_fields = ("id", "created_at")
