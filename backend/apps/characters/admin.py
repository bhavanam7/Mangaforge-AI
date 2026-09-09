from django.contrib import admin

from .models import Character


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "surname", "project", "importance", "is_deleted", "created_at", "updated_at")
    list_filter = ("importance", "is_deleted")
    search_fields = ("name", "surname", "project__title", "project__owner__email")
    readonly_fields = ("id", "created_at", "updated_at", "deleted_at")
