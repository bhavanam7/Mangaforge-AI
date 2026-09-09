from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "role", "is_active", "is_deleted", "created_at")
    list_filter = ("role", "is_active", "is_deleted")
    search_fields = ("email", "name")
    readonly_fields = ("id", "created_at", "updated_at", "last_login")
    ordering = ("-created_at",)
