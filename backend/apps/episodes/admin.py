from django.contrib import admin

from .models import Episode


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ("episode_number", "title", "project", "status", "is_deleted", "updated_at")
    list_filter = ("status", "is_deleted")
    search_fields = ("title", "summary", "project__title", "project__owner__email")
    readonly_fields = ("id", "created_at", "updated_at", "deleted_at")